from __future__ import annotations

import json

from app.schemas import AnalysisRequestContext, AnalysisResponse, NewsItem, SymbolInfo


def build_detection_prompt() -> str:
    return "\n".join(
        [
            "Inspect exactly one user-provided trading chart screenshot.",
            "Only validate the screenshot and identify the market symbol and chart timeframe visibly present in the image.",
            "detected_symbol must be an exchange-qualified market code such as NASDAQ:AAPL or BINANCE:BTCUSDT when it can be read reliably.",
            "detected_timeframe must be one of 1M, 5M, 15M, 30M, 1H, 2H, 4H, 6H, 12H, 1D, or 1W.",
            "Set symbol_matches true when a symbol is detected and false when it is absent; there is no user-entered symbol to compare.",
            "Do not guess a missing symbol, exchange, or timeframe. Use missing_symbol or missing_timeframe when absent or ambiguous.",
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
            "validation.detected_symbol must be exchange-qualified, for example NASDAQ:AAPL or BINANCE:BTCUSDT.",
            "validation.detected_timeframe must be one of 1M, 5M, 15M, 30M, 1H, 2H, 4H, 6H, 12H, 1D, or 1W.",
            "Do not guess missing or ambiguous market metadata; return missing_symbol or missing_timeframe instead.",
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
