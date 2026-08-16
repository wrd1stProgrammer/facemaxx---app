from __future__ import annotations

import logging
from pathlib import Path
import time
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
    NewsImpact,
    ResponseLanguage,
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
            detection_prompt = build_detection_prompt(context.response_language)
            validation, detection_provider = await self._complete(
                prompt=detection_prompt,
                image_path=image_path,
                response_model=ChartValidation,
            )
            if detection_provider == "codex_cli" and _needs_metadata_recovery(validation):
                validation = await self.fallback.complete(
                    prompt=detection_prompt,
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
            analysis_prompt = build_analysis_prompt(context, None, None, [])
            payload, provider_name = await self._complete(
                prompt=analysis_prompt,
                image_path=image_path,
                response_model=AnalysisPayload,
            )
            if provider_name == "codex_cli" and _needs_metadata_recovery(payload.validation):
                payload = await self.fallback.complete(
                    prompt=analysis_prompt,
                    image_path=image_path,
                    response_model=AnalysisPayload,
                )
                provider_name = "openai_fallback"
            symbol, timeframe = await self._resolve_chart_context(payload.validation)
        payload = _normalize_news_impact(payload, news, context.include_news)
        payload = _normalize_decision_labels(payload, context.response_language)
        return AnalysisResponse.create(
            provider=provider_name,
            symbol=symbol,
            timeframe=timeframe,
            included_news=context.include_news,
            result=payload,
            news=news,
            agent_profiles=context.agent_customizations,
        )

    async def _complete(
        self,
        *,
        prompt: str,
        image_path: Path | None,
        response_model: type[ResponseModel],
    ) -> tuple[ResponseModel, str]:
        started_at = time.monotonic()
        try:
            result = await self.codex.complete(
                prompt=prompt,
                image_path=image_path,
                response_model=response_model,
            )
            LOGGER.info(
                "Codex completion succeeded response_model=%s elapsed_seconds=%.2f",
                response_model.__name__,
                time.monotonic() - started_at,
            )
            return result, "codex_cli"
        except Exception as error:  # noqa: BLE001 - provider boundary must always fall back
            LOGGER.warning(
                "Codex completion failed; using OpenAI fallback response_model=%s reason=%s elapsed_seconds=%.2f",
                response_model.__name__,
                type(error).__name__,
                time.monotonic() - started_at,
            )
            fallback_started_at = time.monotonic()
            result = await self.fallback.complete(
                prompt=prompt,
                image_path=image_path,
                response_model=response_model,
            )
            LOGGER.info(
                "OpenAI fallback succeeded response_model=%s elapsed_seconds=%.2f",
                response_model.__name__,
                time.monotonic() - fallback_started_at,
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
        prompt = build_follow_up_prompt(request)
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
        raise InvalidChartError("missing_symbol", "이미지에서 종목 심볼을 확인할 수 없습니다.")
    if not (validation.detected_timeframe or "").strip():
        raise InvalidChartError("missing_timeframe", "이미지에서 차트 시간대를 확인할 수 없습니다.")


def _needs_metadata_recovery(validation: ChartValidation) -> bool:
    return validation.is_chart and validation.is_readable and (
        not (validation.detected_symbol or "").strip()
        or not (validation.detected_timeframe or "").strip()
    )


def _normalize_news_impact(
    payload: AnalysisPayload,
    news: list[NewsItem],
    include_news: bool,
) -> AnalysisPayload:
    if not include_news:
        impact = NewsImpact(
            collected_count=0,
            used_count=0,
            effect="none",
            summary="뉴스 옵션을 사용하지 않아 차트 이미지 근거만 반영했습니다.",
            used_titles=[],
        )
        return payload.model_copy(update={"news_impact": impact})

    available_titles = {item.title for item in news}
    used_titles = list(dict.fromkeys(title for title in payload.news_impact.used_titles if title in available_titles))
    if not used_titles:
        impact = NewsImpact(
            collected_count=len(news),
            used_count=0,
            effect="none",
            summary=(
                "관련 뉴스가 없어 차트 이미지 근거만 반영했습니다."
                if not news
                else "수집한 뉴스는 차트 판단을 바꿀 직접 근거로 사용하지 않았습니다."
            ),
            used_titles=[],
        )
        return payload.model_copy(update={"news_impact": impact})

    impact = payload.news_impact.model_copy(
        update={
            "collected_count": len(news),
            "used_count": len(used_titles),
            "used_titles": used_titles,
        }
    )
    return payload.model_copy(update={"news_impact": impact})


def _normalize_decision_labels(
    payload: AnalysisPayload,
    language: ResponseLanguage,
) -> AnalysisPayload:
    labels = {
        "en-US": {"bullish": "BUY", "bearish": "SELL", "observe": "WAIT", "neutral": "NEUTRAL"},
        "en": {"bullish": "BUY", "bearish": "SELL", "observe": "WAIT", "neutral": "NEUTRAL"},
        "ko": {"bullish": "매수", "bearish": "매도", "observe": "관망", "neutral": "중립"},
        "ja": {"bullish": "買い", "bearish": "売り", "observe": "様子見", "neutral": "中立"},
        "de": {"bullish": "KAUFEN", "bearish": "VERKAUFEN", "observe": "ABWARTEN", "neutral": "NEUTRAL"},
        "fr-FR": {"bullish": "ACHAT", "bearish": "VENTE", "observe": "ATTENDRE", "neutral": "NEUTRE"},
        "es-MX": {"bullish": "COMPRAR", "bearish": "VENDER", "observe": "ESPERAR", "neutral": "NEUTRAL"},
        "pt-BR": {"bullish": "COMPRAR", "bearish": "VENDER", "observe": "AGUARDAR", "neutral": "NEUTRO"},
        "zh-Hant": {"bullish": "買入", "bearish": "賣出", "observe": "觀望", "neutral": "中立"},
        "id": {"bullish": "BELI", "bearish": "JUAL", "observe": "TUNGGU", "neutral": "NETRAL"},
        "th": {"bullish": "ซื้อ", "bearish": "ขาย", "observe": "รอดู", "neutral": "เป็นกลาง"},
        "zh-Hans": {"bullish": "买入", "bearish": "卖出", "observe": "观望", "neutral": "中立"},
        "vi": {"bullish": "MUA", "bearish": "BÁN", "observe": "CHỜ", "neutral": "TRUNG LẬP"},
        "it": {"bullish": "ACQUISTA", "bearish": "VENDI", "observe": "ATTENDI", "neutral": "NEUTRALE"},
        "tr": {"bullish": "AL", "bearish": "SAT", "observe": "BEKLE", "neutral": "NÖTR"},
        "es-ES": {"bullish": "COMPRAR", "bearish": "VENDER", "observe": "ESPERAR", "neutral": "NEUTRAL"},
        "fr-CA": {"bullish": "ACHAT", "bearish": "VENTE", "observe": "ATTENDRE", "neutral": "NEUTRE"},
    }[language]
    consensus = payload.consensus.model_copy(update={"title": labels[payload.consensus.stance_code]})
    opinions = [
        opinion.model_copy(update={"stance": labels[opinion.stance_code]})
        for opinion in payload.agent_opinions
    ]
    return payload.model_copy(update={"consensus": consensus, "agent_opinions": opinions})


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
