from __future__ import annotations

import pytest

from app.schemas import (
    AnalysisPayload,
    AnalysisScope,
    ChartValidation,
    Consensus,
    DataQuality,
    NewsImpact,
    TradePlan,
)


@pytest.fixture
def valid_payload() -> AnalysisPayload:
    return AnalysisPayload.model_construct(
        validation=ChartValidation(
            is_chart=True,
            is_readable=True,
            symbol_matches=True,
            detected_symbol="NASDAQ:AAPL",
            detected_timeframe="1D",
            reason_code="ok",
            message="차트를 읽을 수 있습니다.",
        ),
        consensus=Consensus(
            title="방향 확인 대기",
            stance_code="observe",
            confidence=68,
            summary="보이는 구조만으로는 돌파 확인이 더 필요합니다.",
        ),
        scope=AnalysisScope(visible=["캔들 구조"], unavailable=["실시간 시세"]),
        agent_opinions=[],
        scenarios=[],
        structure=[],
        meeting_script=[],
        data_quality=DataQuality(chart="good", price_axis="partial", timeframe="good", news="unused"),
        news_impact=NewsImpact(
            collected_count=0,
            used_count=0,
            effect="none",
            summary="뉴스를 사용하지 않았습니다.",
            used_titles=[],
        ),
        trade_plan=TradePlan(
            direction_code="observe",
            reference_price="63,000",
            entry="64,000",
            stop="65,000",
            target="62,000",
            risk_reward="최소 1:2",
            trigger="확인선 회복 뒤 재시험이 지지로 전환되는지 확인합니다.",
            rationale="현재는 확인 조건이 부족해 가격을 추격하지 않고 조건 충족을 기다립니다.",
        ),
        follow_up_suggestions=[],
    )


@pytest.fixture
def invalid_payload(valid_payload: AnalysisPayload) -> AnalysisPayload:
    return valid_payload.model_copy(
        update={
            "validation": ChartValidation(
                is_chart=False,
                is_readable=False,
                symbol_matches=False,
                detected_symbol=None,
                detected_timeframe=None,
                reason_code="not_chart",
                message="차트 이미지가 아닙니다.",
            )
        }
    )
