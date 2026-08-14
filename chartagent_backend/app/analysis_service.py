from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.errors import AnalysisUnavailableError, InvalidChartError, InvalidSymbolError
from app.prompts import build_analysis_prompt, build_follow_up_prompt
from app.schemas import (
    AnalysisPayload,
    AnalysisRequestContext,
    AnalysisResponse,
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
        symbol = await self.market_data.resolve_symbol(context.symbol_code)
        if symbol is None:
            raise InvalidSymbolError(context.symbol_code)
        news = await self.market_data.fetch_news(symbol.code) if context.include_news else []
        prompt = build_analysis_prompt(context, symbol, news)
        provider_name: str = "codex_cli"
        try:
            payload = await self.codex.complete(
                prompt=prompt,
                image_path=image_path,
                response_model=AnalysisPayload,
            )
        except Exception as error:  # noqa: BLE001 - provider boundary must always fall back
            LOGGER.warning("Codex analysis failed; using OpenAI fallback reason=%s", type(error).__name__)
            provider_name = "openai_fallback"
            payload = await self.fallback.complete(
                prompt=prompt,
                image_path=image_path,
                response_model=AnalysisPayload,
            )
        _raise_for_invalid_chart(payload)
        return AnalysisResponse.create(
            provider=provider_name,
            symbol=symbol,
            timeframe=context.timeframe,
            included_news=context.include_news,
            result=payload,
            news=news,
        )

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


def _raise_for_invalid_chart(payload: AnalysisPayload) -> None:
    validation = payload.validation
    if validation.is_chart and validation.is_readable and validation.symbol_matches:
        return
    raise InvalidChartError(validation.reason_code, validation.message)
