from __future__ import annotations

import json

from app.schemas import AnalysisRequestContext, AnalysisResponse, NewsItem, SymbolInfo


def build_analysis_prompt(
    context: AnalysisRequestContext,
    symbol: SymbolInfo,
    news: list[NewsItem],
) -> str:
    news_payload = [
        {
            "title": item.title,
            "source": item.source,
            "published_at": item.published_at,
            "related_symbols": item.related_symbols,
            "content_excerpt": item.relevance,
        }
        for item in news
    ]
    return "\n".join(
        [
            "Analyze exactly one user-provided trading chart screenshot for a Korean mobile app.",
            f"Requested symbol: {symbol.code} ({symbol.name}, {symbol.instrument_type}).",
            f"User-selected timeframe: {context.timeframe}.",
            f"News option enabled: {str(context.include_news).lower()}.",
            f"Active agent ids: {', '.join(context.active_agent_ids)}.",
            "First validate that the image is a readable financial price chart and that any visible symbol does not contradict the requested symbol.",
            "If invalid, fill validation accurately and keep the rest conservative but schema-valid.",
            "Use only visible chart evidence. Never invent exact prices, unseen indicators, live quotes, order flow, on-chain data, probabilities, or other timeframes.",
            "Structure levels may use relative descriptions such as 'visible recent high' when the number is not clearly readable.",
            "Write concise natural Korean. Produce exactly one independent opinion for each active agent id and no opinion for inactive agents.",
            "Produce a short meeting script whose lines are grounded in those same opinions, not new claims.",
            "News is supporting context only and must retain source/time metadata in the server response.",
            "InsightSentry news JSON:",
            json.dumps(news_payload, ensure_ascii=False),
        ]
    )


def build_follow_up_prompt(agent_id: str, question: str, analysis: AnalysisResponse) -> str:
    compact = {
        "symbol": analysis.symbol.model_dump(),
        "timeframe": analysis.timeframe,
        "consensus": analysis.result.consensus.model_dump(),
        "scope": analysis.result.scope.model_dump(),
        "agent_opinions": [item.model_dump() for item in analysis.result.agent_opinions],
        "structure": [item.model_dump() for item in analysis.result.structure],
    }
    return "\n".join(
        [
            "Answer one follow-up question in Korean as the selected ChartAgent specialist.",
            f"Selected agent id: {agent_id}.",
            f"User question: {question}",
            "Stay inside the evidence and limitations of the original screenshot analysis. Do not invent live prices or unseen data.",
            "Put the direct answer in answer and the most important limitation in caveat.",
            "Original analysis JSON:",
            json.dumps(compact, ensure_ascii=False),
        ]
    )
