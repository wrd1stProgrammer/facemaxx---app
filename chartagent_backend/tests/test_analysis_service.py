from __future__ import annotations

from pathlib import Path

import pytest

from app.analysis_service import AnalysisService, _normalize_news_impact
from app.errors import InvalidChartError, InvalidSymbolError
from app.schemas import AnalysisPayload, AnalysisRequestContext, NewsImpact, NewsItem, SymbolInfo


class FailingProvider:
    async def complete(self, *, prompt: str, image_path: Path, response_model: type[AnalysisPayload]) -> AnalysisPayload:
        raise RuntimeError("codex unavailable")


class FixedProvider:
    def __init__(self, payload: AnalysisPayload) -> None:
        self.payload = payload
        self.calls = 0

    async def complete(self, *, prompt: str, image_path: Path, response_model: type[AnalysisPayload]) -> AnalysisPayload:
        self.calls += 1
        return self.payload


class FixedMarketData:
    def __init__(self, symbol: SymbolInfo | None) -> None:
        self.symbol = symbol

    async def resolve_symbol(self, code: str) -> SymbolInfo | None:
        return self.symbol

    async def search_symbols(self, query: str) -> list[SymbolInfo]:
        return [self.symbol] if self.symbol is not None else []

    async def fetch_news(self, code: str) -> list[NewsItem]:
        return []


@pytest.mark.anyio
async def test_openai_is_always_used_after_codex_failure(tmp_path: Path, valid_payload: AnalysisPayload) -> None:
    fallback = FixedProvider(valid_payload)
    service = AnalysisService(
        market_data=FixedMarketData(SymbolInfo(code="NASDAQ:AAPL", name="Apple Inc.", instrument_type="stock")),
        codex=FailingProvider(),
        fallback=fallback,
    )

    result = await service.analyze(
        context=AnalysisRequestContext(include_news=False, active_agent_ids=["trend", "pattern", "risk"]),
        image_path=tmp_path / "chart.png",
    )

    assert result.provider == "openai_fallback"
    assert fallback.calls == 1


@pytest.mark.anyio
async def test_unresolved_detected_symbol_returns_typed_error(tmp_path: Path, valid_payload: AnalysisPayload) -> None:
    fallback = FixedProvider(valid_payload)
    service = AnalysisService(market_data=FixedMarketData(None), codex=fallback, fallback=fallback)

    with pytest.raises(InvalidSymbolError):
        await service.analyze(
            context=AnalysisRequestContext(include_news=False, active_agent_ids=["trend", "pattern", "risk"]),
            image_path=tmp_path / "chart.png",
        )

    assert fallback.calls == 1


@pytest.mark.anyio
async def test_ai_rejected_non_chart_returns_typed_error(tmp_path: Path, invalid_payload: AnalysisPayload) -> None:
    provider = FixedProvider(invalid_payload)
    service = AnalysisService(
        market_data=FixedMarketData(SymbolInfo(code="NASDAQ:AAPL", name="Apple Inc.", instrument_type="stock")),
        codex=provider,
        fallback=provider,
    )

    with pytest.raises(InvalidChartError) as raised:
        await service.analyze(
            context=AnalysisRequestContext(include_news=False, active_agent_ids=["trend", "pattern", "risk"]),
            image_path=tmp_path / "chart.png",
        )

    assert raised.value.code == "not_chart"


@pytest.mark.anyio
async def test_missing_image_timeframe_returns_typed_error(tmp_path: Path, valid_payload: AnalysisPayload) -> None:
    invalid_payload = valid_payload.model_copy(
        update={
            "validation": valid_payload.validation.model_copy(
                update={
                    "detected_timeframe": None,
                    "reason_code": "missing_timeframe",
                    "message": "이미지에서 시간대를 확인할 수 없습니다.",
                }
            )
        }
    )
    provider = FixedProvider(invalid_payload)
    service = AnalysisService(
        market_data=FixedMarketData(SymbolInfo(code="NASDAQ:AAPL", name="Apple Inc.", instrument_type="stock")),
        codex=provider,
        fallback=provider,
    )

    with pytest.raises(InvalidChartError) as raised:
        await service.analyze(
            context=AnalysisRequestContext(include_news=False, active_agent_ids=["trend", "pattern", "risk"]),
            image_path=tmp_path / "chart.png",
        )

    assert raised.value.code == "missing_timeframe"


def test_news_impact_keeps_only_titles_returned_by_insightsentry(valid_payload: AnalysisPayload) -> None:
    payload = valid_payload.model_copy(
        update={
            "news_impact": NewsImpact(
                collected_count=99,
                used_count=2,
                effect="reinforced",
                summary="차트의 상방 조건을 보조했습니다.",
                used_titles=["실제 기사", "존재하지 않는 기사"],
            )
        }
    )
    news = [
        NewsItem(
            title="실제 기사",
            source="InsightSentry",
            published_at=1_700_000_000,
            related_symbols=["NASDAQ:AAPL"],
            relevance="",
        )
    ]

    normalized = _normalize_news_impact(payload, news, include_news=True)

    assert normalized.news_impact.collected_count == 1
    assert normalized.news_impact.used_count == 1
    assert normalized.news_impact.used_titles == ["실제 기사"]
