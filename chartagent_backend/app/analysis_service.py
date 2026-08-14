from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.errors import InvalidChartError, InvalidSymbolError
from app.prompts import build_analysis_prompt, build_detection_prompt, build_follow_up_prompt
from app.schemas import (
    AnalysisPayload,
    AnalysisRequestContext,
    AnalysisResponse,
    ChartValidation,
    FollowUpRequest,
    FollowUpPayload,
    FollowUpResponse,
    NewsItem,
    SymbolInfo,
)


LOGGER = logging.getLogger(__name__)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class StructuredProvider(Protocol):
    async def complete(
        self,
        *,
        prompt: str,
        image_path: Path | None,
        response_model: type[ResponseModel],
    ) -> ResponseModel: ...


class MarketData(Protocol):
    async def resolve_symbol(self, code: str) -> SymbolInfo | None: ...

    async def search_symbols(self, query: str) -> list[SymbolInfo]: ...

    async def fetch_news(self, code: str) -> list[NewsItem]: ...


class AnalysisService:
    def __init__(
        self,
        *,
        market_data: MarketData,
        codex: StructuredProvider,
        fallback: StructuredProvider,
    ) -> None:
        self.market_data = market_data
        self.codex = codex
        self.fallback = fallback

    async def analyze(self, *, context: AnalysisRequestContext, image_path: Path) -> AnalysisResponse:
        news: list[NewsItem] = []
        if context.include_news:
            validation, _ = await self._complete(
                prompt=build_detection_prompt(),
                image_path=image_path,
                response_model=ChartValidation,
            )
            symbol, timeframe = await self._resolve_chart_context(validation)
            news = await self.market_data.fetch_news(symbol.code)
            payload, provider_name = await self._complete(
                prompt=build_analysis_prompt(context, symbol, timeframe, news),
                image_path=image_path,
                response_model=AnalysisPayload,
            )
            _raise_for_invalid_chart(payload.validation)
        else:
            payload, provider_name = await self._complete(
                prompt=build_analysis_prompt(context, None, None, []),
                image_path=image_path,
                response_model=AnalysisPayload,
            )
            symbol, timeframe = await self._resolve_chart_context(payload.validation)
        return AnalysisResponse.create(
            provider=provider_name,
            symbol=symbol,
            timeframe=timeframe,
            included_news=context.include_news,
            result=payload,
            news=news,
        )

    async def _complete(
        self,
        *,
        prompt: str,
        image_path: Path | None,
        response_model: type[ResponseModel],
    ) -> tuple[ResponseModel, str]:
        try:
            result = await self.codex.complete(
                prompt=prompt,
                image_path=image_path,
                response_model=response_model,
            )
            return result, "codex_cli"
        except Exception as error:  # noqa: BLE001 - provider boundary must always fall back
            LOGGER.warning("Codex completion failed; using OpenAI fallback reason=%s", type(error).__name__)
            result = await self.fallback.complete(
                prompt=prompt,
                image_path=image_path,
                response_model=response_model,
            )
            return result, "openai_fallback"

    async def _resolve_chart_context(self, validation: ChartValidation) -> tuple[SymbolInfo, str]:
        _raise_for_invalid_chart(validation)
        detected_symbol = (validation.detected_symbol or "").strip().upper()
        timeframe = _normalize_timeframe(validation.detected_timeframe or "")
        if timeframe is None:
            raise InvalidChartError("missing_timeframe", "이미지에서 지원하는 차트 시간대를 확인할 수 없습니다.")
        symbol = await self.market_data.resolve_symbol(detected_symbol) if ":" in detected_symbol else None
        if symbol is None:
            candidates = await self.market_data.search_symbols(detected_symbol.split(":")[-1])
            symbol = _best_symbol_match(detected_symbol, candidates)
        if symbol is None:
            raise InvalidSymbolError(detected_symbol)
        return symbol, timeframe

    async def follow_up(self, *, request: FollowUpRequest) -> FollowUpResponse:
        prompt = build_follow_up_prompt(request.agent_id, request.question, request.analysis)
        try:
            response = await self.codex.complete(
                prompt=prompt,
                image_path=None,
                response_model=FollowUpPayload,
            )
            return FollowUpResponse(
                agent_id=request.agent_id,
                answer=response.answer,
                caveat=response.caveat,
                provider="codex_cli",
            )
        except Exception as error:  # noqa: BLE001 - provider boundary must always fall back
            LOGGER.warning("Codex follow-up failed; using OpenAI fallback reason=%s", type(error).__name__)
            response = await self.fallback.complete(
                prompt=prompt,
                image_path=None,
                response_model=FollowUpPayload,
            )
            return FollowUpResponse(
                agent_id=request.agent_id,
                answer=response.answer,
                caveat=response.caveat,
                provider="openai_fallback",
            )


def _raise_for_invalid_chart(validation: ChartValidation) -> None:
    if not validation.is_chart or not validation.is_readable:
        raise InvalidChartError(validation.reason_code, validation.message)
    if not (validation.detected_symbol or "").strip():
        raise InvalidChartError("missing_symbol", "이미지에서 거래소와 종목 심볼을 확인할 수 없습니다.")
    if not (validation.detected_timeframe or "").strip():
        raise InvalidChartError("missing_timeframe", "이미지에서 차트 시간대를 확인할 수 없습니다.")


def _normalize_timeframe(value: str) -> str | None:
    normalized = value.strip().upper().replace(" ", "")
    aliases = {
        "1MIN": "1M",
        "5MIN": "5M",
        "15MIN": "15M",
        "30MIN": "30M",
        "60M": "1H",
        "1HR": "1H",
        "D": "1D",
        "DAILY": "1D",
        "W": "1W",
        "WEEKLY": "1W",
    }
    normalized = aliases.get(normalized, normalized)
    supported = {"1M", "5M", "15M", "30M", "1H", "2H", "4H", "6H", "12H", "1D", "1W"}
    return normalized if normalized in supported else None


def _best_symbol_match(detected: str, candidates: list[SymbolInfo]) -> SymbolInfo | None:
    if not candidates:
        return None
    normalized = detected.upper()
    ticker = normalized.split(":")[-1]
    for candidate in candidates:
        if candidate.code.upper() == normalized:
            return candidate
    for candidate in candidates:
        if candidate.code.upper().split(":")[-1] == ticker:
            return candidate
    return candidates[0]
