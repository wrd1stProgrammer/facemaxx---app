import asyncio
import time
from types import SimpleNamespace

import pytest

from app.errors import ChartAgentError
from app.news_workspace import NewsWorkspace, NewsRequest, TranslationRequest, ChatRequest, NewsReport, Factor, Translation, NewsScenario


class Market:
    def __init__(self):
        self.calls = 0

    async def resolve_symbol(self, symbol):
        return SimpleNamespace(code=symbol, name="Apple", instrument_type="stock")

    async def fetch_latest_news(self, code, name):
        self.calls += 1
        await asyncio.sleep(0)
        return [SimpleNamespace(title="Apple earnings", source="Example", published_at=int(time.time()),
                                link="https://example.com/story", content="<p>Revenue increased.</p>")]


class Provider:
    def __init__(self):
        self.calls = 0
        self.source = ""

    async def complete(self, **kwargs):
        self.calls += 1
        if kwargs["response_model"] is Translation:
            return Translation(title="애플 실적", content="매출이 증가했다.")
        scenario = NewsScenario(strength=2, rationale="One relevant signal", transmission="Revenue supports earnings",
                            confirmation="Further growth", invalidation="Revenue reverses", source_ids=[self.source])
        return NewsReport(outlook="mixed", headline="Mixed", summary="Summary", horizon="Near term",
                          supportive=scenario, cautionary=scenario,
                          factors=[Factor(title="Revenue", explanation="Growth", source_ids=[self.source])],
                          upside_condition="Growth persists", downside_condition="Growth reverses", uncertainty="Incomplete")


@pytest.mark.anyio
async def test_feed_shares_underlying_ticker_across_exchanges_and_pairs(tmp_path):
    class CanonicalMarket(Market):
        async def resolve_symbol(self, symbol):
            raise AssertionError("News must not depend on exchange lookup")

        async def fetch_news_page(self, code, page, name="", instrument_type=""):
            self.calls += 1
            assert code == "SOXL"
            return [SimpleNamespace(title="SOXL news", source="Example",
                                    published_at=1792400000, link="https://example.com/soxl",
                                    content="SOXL fund news")], False

    market = CanonicalMarket()
    service = NewsWorkspace(market, Provider(), tmp_path / "cache.db")
    feeds = [await service.feed(symbol, page=1) for symbol in
             ("AMEX:SOXL", "BINANCE:SOXLUSDT", "BVL:SOXLUS", "SOXL")]
    assert market.calls == 1
    assert len({feed.id for feed in feeds}) == 1
    assert all(feed.symbol == "SOXL" for feed in feeds)


@pytest.mark.anyio
async def test_feed_coalesces_and_survives_new_service(tmp_path):
    market = Market()
    service = NewsWorkspace(market, Provider(), tmp_path / "cache.db")
    one, two = await asyncio.gather(service.feed("NASDAQ:AAPL"), service.feed("NASDAQ:AAPL"))
    assert one.id == two.id
    assert market.calls == 1
    assert one.articles[0].content == "Revenue increased."
    restarted = NewsWorkspace(market, Provider(), tmp_path / "cache.db")
    assert restarted.snapshot(one.id) == one


@pytest.mark.anyio
async def test_legacy_exchange_cursor_remains_usable(tmp_path):
    service = NewsWorkspace(Market(), Provider(), tmp_path / "cache.db")
    service.put("news-cursor:v1:NASDAQ:AAPL:2", {
        "remaining": [], "source_page": 2, "has_next": False, "seen": [],
    })
    feed = await service.feed("NASDAQ:AAPL", page=2)
    assert feed.symbol == "AAPL"
    assert feed.next_page is None


@pytest.mark.anyio
async def test_analysis_rejects_unknown_sources_without_caching(tmp_path):
    provider = Provider()
    service = NewsWorkspace(Market(), provider, tmp_path / "cache.db")
    feed = await service.feed("NASDAQ:AAPL")
    request = NewsRequest(feed_id=feed.id, language="ko")
    with pytest.raises(ChartAgentError, match="뉴스 근거"):
        await service.analyze(request)
    provider.source = feed.articles[0].id
    result = await service.analyze(request)
    assert result.factors[0].source_ids == [provider.source]
    assert await service.analyze(request) == result
    assert provider.calls == 2


@pytest.mark.anyio
async def test_translation_caches_per_language_and_requires_real_article(tmp_path):
    provider = Provider()
    service = NewsWorkspace(Market(), provider, tmp_path / "cache.db")
    feed = await service.feed("NASDAQ:AAPL")
    request = TranslationRequest(feed_id=feed.id, article_id=feed.articles[0].id, language="ko")
    await service.translate(request)
    await service.translate(request)
    assert provider.calls == 1
    await service.translate(request.model_copy(update={"language": "ja"}))
    assert provider.calls == 2
    with pytest.raises(ChartAgentError):
        await service.translate(request.model_copy(update={"article_id": "fake"}))


@pytest.mark.anyio
async def test_chat_requires_analyzed_snapshot_and_expiry(tmp_path):
    service = NewsWorkspace(Market(), Provider(), tmp_path / "cache.db")
    feed = await service.feed("NASDAQ:AAPL")
    with pytest.raises(ChartAgentError) as error:
        await service.chat(ChatRequest(feed_id=feed.id, agent_id="risk", question="Why?"))
    assert error.value.status_code == 409
    service.put("feed:" + feed.id, feed.model_dump(), -1)
    with pytest.raises(ChartAgentError) as error:
        service.snapshot(feed.id)
    assert error.value.status_code == 410


@pytest.mark.anyio
async def test_pages_and_article_analysis_are_isolated(tmp_path):
    class PagedMarket(Market):
        async def fetch_news_page(self, code, page, name="", instrument_type=""):
            return [
                SimpleNamespace(title=f"Article {page}-{index}", source="Example",
                                published_at=1792400000 - page * 100 - index,
                                link=f"https://example.com/{page}/{index}", content="Evidence")
                for index in range(10)
            ], page == 1

    provider = Provider()
    service = NewsWorkspace(PagedMarket(), provider, tmp_path / "cache.db")
    first = await service.feed("NASDAQ:AAPL", page=1)
    second = await service.feed("NASDAQ:AAPL", page=2)
    assert len(first.articles) == len(second.articles) == 10
    assert first.next_page == 2 and second.next_page is None
    assert not {a.id for a in first.articles} & {a.id for a in second.articles}
    request = NewsRequest(feed_id=first.id, article_id=first.articles[0].id, language="ko")
    assert len(service.scoped_feed(request).articles) == 1
    provider.source = first.articles[1].id
    with pytest.raises(ChartAgentError):
        await service.analyze(request)
    provider.source = first.articles[0].id
    await service.analyze(request)
    with pytest.raises(ChartAgentError) as error:
        await service.chat(ChatRequest(feed_id=first.id, article_id=first.articles[1].id,
                                       agent_id="risk", question="Why?"))
    assert error.value.status_code == 409
