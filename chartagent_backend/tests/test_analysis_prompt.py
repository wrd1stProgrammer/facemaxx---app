from __future__ import annotations

from app.prompts import build_analysis_prompt
from app.schemas import AnalysisRequestContext, NewsItem, SymbolInfo


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
    assert "news_impact.used_titles" in prompt
    assert "Set news_impact.collected_count to 1" in prompt
