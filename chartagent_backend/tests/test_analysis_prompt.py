from __future__ import annotations

from app.prompts import build_analysis_prompt, build_follow_up_prompt
from app.schemas import AnalysisRequestContext, AnalysisResponse, FollowUpHistoryItem, NewsItem, SymbolInfo


def test_analysis_prompt_requires_specific_agent_judgements_and_news_usage() -> None:
    prompt = build_analysis_prompt(
        AnalysisRequestContext(
            include_news=True,
            active_agent_ids=["trend", "pattern", "momentum", "risk", "devil"],
        ),
        SymbolInfo(code="NASDAQ:AAPL", name="Apple Inc.", instrument_type="stock"),
        "1D",
        [
            NewsItem(
                title="Apple supply update",
                source="InsightSentry",
                published_at=1_700_000_000,
                related_symbols=["NASDAQ:AAPL"],
                relevance="Supply chain context",
            )
        ],
    )

    assert "actual directional or conditional judgement" in prompt
    assert "visible swing highs/lows" in prompt
    assert "false-break or opposing scenario" in prompt
    assert "Lead with a decisive call" in prompt
    assert "Never output the English labels buy-side, sell-side, BUY, SELL, or WAIT" in prompt
    assert "매수 우위, 매도 우위, or 관망" in prompt
    assert "Do not dilute a supported call with stacked hedges" in prompt
    assert "Challenge another specialist directly" in prompt
    assert "news_impact.used_titles" in prompt
    assert "Set news_impact.collected_count to 1" in prompt
    assert "Evaluate every collected item" in prompt


def test_follow_up_prompt_includes_persisted_conversation_history(valid_payload) -> None:
    analysis = AnalysisResponse.create(
        provider="codex_cli",
        symbol=SymbolInfo(code="NASDAQ:AAPL", name="Apple Inc.", instrument_type="stock"),
        timeframe="1D",
        included_news=False,
        result=valid_payload,
        news=[],
    )

    prompt = build_follow_up_prompt(
        "risk",
        "그럼 무효화 조건은?",
        analysis,
        [
            FollowUpHistoryItem(
                agent_id="trend",
                question="현재 구조는?",
                answer="현재 보이는 구조에서는 매도 우위입니다.",
            )
        ],
    )

    assert "Conversation history JSON" in prompt
    assert "현재 구조는?" in prompt
    assert "현재 보이는 구조에서는 매도 우위입니다." in prompt
