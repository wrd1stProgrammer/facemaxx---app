from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.analysis_service import AnalysisService, _normalize_decision_labels, _normalize_news_impact
from app.errors import InvalidChartError, InvalidSymbolError
from app.schemas import AgentOpinion, AnalysisPayload, AnalysisRequestContext, NewsImpact, NewsItem, SymbolInfo, TradePlan


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


def test_decision_labels_are_one_word_in_response_language(valid_payload: AnalysisPayload) -> None:
    payload = valid_payload.model_copy(
        update={
            "agent_opinions": [
                AgentOpinion(
                    agent_id="trend",
                    stance_code="bearish",
                    stance="하락 압력 우세",
                    confidence=72,
                    thesis="최근 스윙 고점 회복 전까지 하락 구조가 유지됩니다.",
                    evidence=["고점 하락", "지지 재시험"],
                )
            ]
        }
    )

    normalized = _normalize_decision_labels(payload, "ko")

    assert normalized.consensus.title == "관망"
    assert normalized.agent_opinions[0].stance == "매도"


def test_decision_labels_are_localized_for_japanese(valid_payload: AnalysisPayload) -> None:
    normalized = _normalize_decision_labels(valid_payload, "ja")

    assert normalized.consensus.title == "様子見"
    assert all(item.stance in {"買い", "売り", "様子見", "中立"} for item in normalized.agent_opinions)


def test_trade_plan_rejects_current_price_as_entry() -> None:
    with pytest.raises(ValidationError):
        TradePlan(
            direction_code="bearish",
            reference_price="63,888",
            entry="63,888",
            stop="65,603",
            target="61,000",
            risk_reward="1:2",
            trigger="저항 재시험에서 다시 밀리는지 확인합니다.",
            rationale="현재가 추격 대신 확인된 저항 재시험에서 손익비를 확보합니다.",
        )


def test_trade_plan_rejects_weak_reward_to_risk() -> None:
    with pytest.raises(ValidationError):
        TradePlan(
            direction_code="bearish",
            reference_price="63,888",
            entry="65,200 재시험",
            stop="65,700",
            target="64,450",
            risk_reward="1:1.5",
            trigger="저항 재시험에서 다시 밀리는지 확인합니다.",
            rationale="현재가 추격 대신 확인된 저항 재시험에서 손익비를 확보합니다.",
        )


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
async def test_openai_recovers_metadata_omitted_by_codex(tmp_path: Path, valid_payload: AnalysisPayload) -> None:
    missing_metadata = valid_payload.model_copy(
        update={
            "validation": valid_payload.validation.model_copy(
                update={
                    "detected_symbol": None,
                    "reason_code": "missing_symbol",
                    "message": "이미지에서 거래소를 확정할 수 없습니다.",
                }
            )
        }
    )
    codex = FixedProvider(missing_metadata)
    fallback = FixedProvider(valid_payload)
    service = AnalysisService(
        market_data=FixedMarketData(SymbolInfo(code="NASDAQ:AAPL", name="Apple Inc.", instrument_type="stock")),
        codex=codex,
        fallback=fallback,
    )

    result = await service.analyze(
        context=AnalysisRequestContext(include_news=False, active_agent_ids=["trend", "pattern", "risk"]),
        image_path=tmp_path / "chart.png",
    )

    assert result.provider == "openai_fallback"
    assert codex.calls == 1
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
                collected_count=20,
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
