from __future__ import annotations

from pathlib import Path

import pytest

from app.analysis_service import AnalysisService
from app.errors import InvalidChartError, InvalidSymbolError
from app.schemas import AnalysisPayload, AnalysisRequestContext, NewsItem, SymbolInfo


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
        context=AnalysisRequestContext(symbol_code="NASDAQ:AAPL", timeframe="1D", include_news=False, active_agent_ids=["trend", "pattern", "risk"]),
        image_path=tmp_path / "chart.png",
    )

    assert result.provider == "openai_fallback"
    assert fallback.calls == 1


@pytest.mark.anyio
async def test_invalid_symbol_stops_before_ai(tmp_path: Path, valid_payload: AnalysisPayload) -> None:
    fallback = FixedProvider(valid_payload)
    service = AnalysisService(market_data=FixedMarketData(None), codex=fallback, fallback=fallback)

    with pytest.raises(InvalidSymbolError):
        await service.analyze(
            context=AnalysisRequestContext(symbol_code="NOPE:VOID", timeframe="4H", include_news=False, active_agent_ids=["trend", "pattern", "risk"]),
            image_path=tmp_path / "chart.png",
        )

    assert fallback.calls == 0


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
            context=AnalysisRequestContext(symbol_code="NASDAQ:AAPL", timeframe="1D", include_news=False, active_agent_ids=["trend", "pattern", "risk"]),
            image_path=tmp_path / "chart.png",
        )

    assert raised.value.code == "not_chart"
