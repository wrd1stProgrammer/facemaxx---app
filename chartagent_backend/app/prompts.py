from __future__ import annotations

import json

from app.schemas import AnalysisRequestContext, AnalysisResponse, NewsItem, SymbolInfo


def build_detection_prompt() -> str:
    return "\n".join(
        [
            "Inspect exactly one user-provided trading chart screenshot.",
            "Only validate the screenshot and identify the market symbol and chart timeframe visibly present in the image.",
            "Read the visible ticker exactly as shown. A TradingView ticker such as BTCUSD, BTCUSDT, AAPL, or TSLA is valid even when the exchange label is absent; the server resolves the exchange afterward.",
            "detected_timeframe must be one of 1M, 5M, 15M, 30M, 1H, 2H, 4H, 6H, 12H, 1D, or 1W.",
            "Set symbol_matches true when a symbol is detected and false when it is absent; there is no user-entered symbol to compare.",
            "Do not reject a readable ticker solely because its exchange is absent. Use missing_symbol only when no ticker can be read, and missing_timeframe only when no timeframe can be read.",
            "Write the validation message in concise natural Korean.",
        ]
    )


def build_analysis_prompt(
    context: AnalysisRequestContext,
    symbol: SymbolInfo | None,
    timeframe: str | None,
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
    market_context = (
        [
            f"Server-resolved symbol: {symbol.code} ({symbol.name}, {symbol.instrument_type}).",
            f"Image-detected timeframe: {timeframe}.",
            "Set validation.detected_symbol and validation.detected_timeframe to those same resolved values.",
        ]
        if symbol is not None and timeframe is not None
        else [
            "Read the symbol, exchange, and timeframe directly from the image before analyzing it.",
            "validation.detected_symbol may be the visible raw TradingView ticker such as BTCUSD or AAPL; the server resolves the exchange afterward.",
            "validation.detected_timeframe must be one of 1M, 5M, 15M, 30M, 1H, 2H, 4H, 6H, 12H, 1D, or 1W.",
            "Do not reject a readable ticker solely because its exchange is absent. Return missing_symbol only when no ticker can be read.",
        ]
    )
    return "\n".join(
        [
            "Analyze exactly one user-provided trading chart screenshot for a Korean mobile app.",
            f"News option enabled: {str(context.include_news).lower()}.",
            f"Active agent ids: {', '.join(context.active_agent_ids)}.",
            *market_context,
            "First validate that the image is a readable financial price chart and that its symbol and timeframe are visible.",
            "Set validation.symbol_matches true when a symbol is detected and false when it is absent; there is no user-entered symbol to compare.",
            "If invalid, fill validation accurately and keep the rest conservative but schema-valid.",
            "Use only visible chart evidence. Never invent exact prices, unseen indicators, live quotes, order flow, on-chain data, probabilities, or other timeframes.",
            "Structure levels may use relative descriptions such as 'visible recent high' when the number is not clearly readable.",
            "Treat consensus as a decision snapshot, not a vote: consensus.confidence is evidence strength, never market probability or agreement percentage.",
            "Write concise natural Korean. Each section must add new decision value instead of paraphrasing the same summary.",
            "Produce exactly one independent opinion for each active agent id and no opinion for inactive agents.",
            "Every agent_opinions.thesis must state that specialist's actual directional or conditional judgement, not merely say what the agent inspected.",
            "Specialist contracts:",
            "- trend: classify visible swing highs/lows and state the exact continuation or transition condition.",
            "- pattern: judge candle bodies/wicks and repeated boundaries; require breakout/re-entry/retest confirmation before naming completion.",
            "- momentum: compare visible candle expansion, rejection, pace, and visible volume only; never invent hidden indicators.",
            "- risk: identify visible support/resistance plus confirmation and invalidation levels; use relative labels when numbers are unreadable.",
            "- devil: give one concrete false-break or opposing scenario that would overturn the base judgement.",
            "Scenarios must cover a confirmation path, a wait/base path, and an invalidation path whenever the screenshot supports all three.",
            "Produce a short meeting script whose lines are grounded in those same specialist judgements, not new claims.",
            "News is optional supporting context, never a substitute for chart evidence.",
            f"Set news_impact.collected_count to {len(news_payload)}.",
            "news_impact.used_titles must contain only exact titles copied from InsightSentry news JSON, and used_count must equal its length.",
            "Set news_impact.effect to reinforced, softened, changed, or none and explain in Korean exactly how those used articles affected the chart judgement.",
            "If news is disabled, empty, irrelevant, or unused, set used_count to 0, used_titles to [], effect to none, and say that the chart judgement was unchanged.",
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
