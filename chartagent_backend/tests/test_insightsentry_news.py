from __future__ import annotations

import time
from collections.abc import Callable

import pytest

from app.insightsentry import InsightSentryClient, _NewsRow, _select_recent_news


class _FakeInsightSentryClient(InsightSentryClient):
    def __init__(self, responder: Callable[[dict[str, str]], dict[str, object]]) -> None:
        self.responder = responder
        self.calls: list[dict[str, str]] = []

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, object]:
        assert path == "/v3/newsfeed"
        request_params = dict(params or {})
        self.calls.append(request_params)
        return self.responder(request_params)


def _news_rows(*, now: int, prefix: str, recent: int, prior: int) -> list[dict[str, object]]:
    return [
        {
            "title": f"{prefix}-recent-{index}",
            "published_at": now - 3_600 - index * 60,
            "related_symbols": ["COINBASE:BTCUSD"],
        }
        for index in range(recent)
    ] + [
        {
            "title": f"{prefix}-prior-{index}",
            "published_at": now - 90_000 - index * 60,
            "related_symbols": ["BINANCE:BTCUSDT"],
        }
        for index in range(prior)
    ]


def test_news_selection_keeps_ten_items_from_each_24_hour_bucket() -> None:
    now = 2_000_000_000
    rows = [
        _NewsRow(title=f"recent-{index}", published_at=now - index * 1_800)
        for index in range(12)
    ] + [
        _NewsRow(title=f"prior-{index}", published_at=now - 86_400 - index * 1_800)
        for index in range(12)
    ] + [
        _NewsRow(title="expired", published_at=now - 172_801),
        _NewsRow(title="recent-0", published_at=now - 300),
        _NewsRow(title="recent-0", published_at=now - 600),
    ]

    selected = _select_recent_news(rows, now_timestamp=now)

    assert len(selected) == 20
    assert [item.title for item in selected[:10]] == [f"recent-{index}" for index in range(10)]
    assert [item.title for item in selected[10:]] == [f"prior-{index}" for index in range(10)]
    assert len({item.title for item in selected}) == 20


def test_news_selection_accepts_millisecond_timestamps() -> None:
    now = 2_000_000_000
    selected = _select_recent_news(
        [_NewsRow(title="milliseconds", published_at=(now - 3_600) * 1_000)],
        now_timestamp=now,
    )

    assert [item.title for item in selected] == ["milliseconds"]


@pytest.mark.anyio
async def test_btc_news_search_uses_cross_exchange_symbol_aliases() -> None:
    now = int(time.time())

    def respond(params: dict[str, str]) -> dict[str, object]:
        if params.get("related_symbols") == "BITSTAMP:BTCUSD":
            return {"data": _news_rows(now=now, prefix="exact", recent=1, prior=0), "has_next": False}
        return {"data": _news_rows(now=now, prefix="broad", recent=12, prior=12), "has_next": False}

    client = _FakeInsightSentryClient(respond)
    news = await client.fetch_news("BITSTAMP:BTCUSD")

    assert len(news) == 20, "exchange-qualified filtering must not collapse BTC coverage to one story"
    assert "BITSTAMP:" not in client.calls[0]["related_symbols"]
    assert {"BTCUSD", "BTCUSDT", "XBTUSD"}.issubset(
        set(client.calls[0]["related_symbols"].split(","))
    )
    assert client.calls[0]["limit"] == "500"


@pytest.mark.anyio
async def test_news_search_follows_pages_until_both_24_hour_buckets_are_full() -> None:
    now = int(time.time())

    def respond(params: dict[str, str]) -> dict[str, object]:
        page = int(params["page"])
        if page == 1:
            return {"data": _news_rows(now=now, prefix="page-1", recent=10, prior=0), "has_next": True}
        return {"data": _news_rows(now=now, prefix="page-2", recent=0, prior=10), "has_next": False}

    client = _FakeInsightSentryClient(respond)
    news = await client.fetch_news("BITSTAMP:BTCUSD")

    assert len(news) == 20
    assert [call["page"] for call in client.calls] == ["1", "2"]


@pytest.mark.anyio
async def test_sparse_btc_symbol_results_fall_back_to_bitcoin_keywords() -> None:
    now = int(time.time())

    def respond(params: dict[str, str]) -> dict[str, object]:
        if "related_symbols" in params:
            return {"data": _news_rows(now=now, prefix="symbol", recent=1, prior=0), "has_next": False}
        assert params["keywords"] == "Bitcoin,BTC"
        return {"data": _news_rows(now=now, prefix="keyword", recent=10, prior=10), "has_next": False}

    client = _FakeInsightSentryClient(respond)
    news = await client.fetch_news("BITSTAMP:BTCUSD")

    assert len(news) == 20
    assert len(client.calls) == 2
    assert "related_symbols" in client.calls[0]
    assert "keywords" in client.calls[1]
