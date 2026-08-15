from __future__ import annotations

from app.prompts import build_analysis_prompt, build_follow_up_prompt
from app.schemas import (
    AnalysisRequestContext,
    AnalysisResponse,
    FollowUpHistoryItem,
    FollowUpRequest,
    SymbolInfo,
)


def test_analysis_prompt_builds_for_selected_response_language() -> None:
    prompt = build_analysis_prompt(
        AnalysisRequestContext(
            include_news=False,
            active_agent_ids=["trend", "pattern", "risk"],
            response_language="en",
        ),
        SymbolInfo(code="NASDAQ:AAPL", name="Apple Inc.", instrument_type="stock"),
        "1D",
        [],
    )

    assert isinstance(prompt, str)
    assert prompt


def test_follow_up_prompt_accepts_saved_history(valid_payload) -> None:
    analysis = AnalysisResponse.create(
        provider="codex_cli",
        symbol=SymbolInfo(code="NASDAQ:AAPL", name="Apple Inc.", instrument_type="stock"),
        timeframe="1D",
        included_news=False,
        result=valid_payload,
        news=[],
    )
    request = FollowUpRequest(
        agent_id="risk",
        question="그럼 무효화 조건은?",
        analysis=analysis,
        history=[
            FollowUpHistoryItem(
                agent_id="trend",
                question="현재 구조는?",
                answer="현재 보이는 구조에서는 매도 판단입니다.",
            )
        ],
        response_language="ko",
    )

    prompt = build_follow_up_prompt(request)

    assert isinstance(prompt, str)
    assert prompt
