from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Protocol, TypeVar

import anyio
from pydantic import BaseModel

from app.errors import DependencyError, InvalidChartError, InvalidSymbolError
from app.prompts import (
    build_analysis_prompt,
    build_detection_prompt,
    build_follow_up_prompt,
    build_news_impact_prompt,
)
from app.schemas import (
    AnalysisContent,
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

    async def fetch_news(self, code: str, name: str | None = None) -> list[NewsItem]: ...


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
            content, provider_name, news, news_impact = await self._analyze_chart_and_news(
                context=context,
                image_path=image_path,
                symbol=symbol,
                timeframe=timeframe,
            )
            payload = _assemble_analysis_payload(
                content,
                validation,
                news_impact or _pending_news_impact(),
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
        payload = _normalize_news_impact(
            payload,
            news,
            context.include_news,
            context.response_language,
        )
        payload = _normalize_decision_labels(payload, context.response_language)
        return AnalysisResponse.create(
            provider=provider_name,
            symbol=symbol,
            timeframe=timeframe,
            included_news=context.include_news and bool(news),
            result=payload,
            news=news,
            agent_profiles=context.agent_customizations,
        )

    async def _analyze_chart_and_news(
        self,
        *,
        context: AnalysisRequestContext,
        image_path: Path,
        symbol: SymbolInfo,
        timeframe: str,
    ) -> tuple[AnalysisContent, str, list[NewsItem], NewsImpact | None]:
        chart_results: list[tuple[AnalysisContent, str]] = []
        news_results: list[tuple[list[NewsItem], NewsImpact | None]] = []

        async def analyze_chart() -> None:
            result = await self._complete(
                prompt=build_analysis_prompt(context, symbol, timeframe, []),
                image_path=image_path,
                response_model=AnalysisContent,
            )
            chart_results.append(result)

        async def analyze_news() -> None:
            news_results.append(
                await self._fetch_and_assess_news(
                    context=context,
                    image_path=image_path,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(analyze_chart)
            task_group.start_soon(analyze_news)

        payload, provider_name = chart_results[0]
        news, news_impact = news_results[0]
        return payload, provider_name, news, news_impact

    async def _fetch_and_assess_news(
        self,
        *,
        context: AnalysisRequestContext,
        image_path: Path,
        symbol: SymbolInfo,
        timeframe: str,
    ) -> tuple[list[NewsItem], NewsImpact | None]:
        try:
            news = await self.market_data.fetch_news(symbol.code, symbol.name)
        except DependencyError as error:
            LOGGER.warning(
                "Optional news enrichment failed; continuing chart-only symbol=%s reason=%s",
                symbol.code,
                type(error).__name__,
            )
            return [], None
        if not news:
            return [], None
        try:
            impact, _ = await self._complete(
                prompt=build_news_impact_prompt(context, symbol, timeframe, news),
                image_path=image_path,
                response_model=NewsImpact,
            )
        except Exception as error:  # noqa: BLE001 - optional enrichment must never fail the chart report
            LOGGER.warning(
                "Optional news assessment failed; continuing chart-only symbol=%s reason=%s",
                symbol.code,
                type(error).__name__,
            )
            return news, None
        return news, impact

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


def _assemble_analysis_payload(
    content: AnalysisContent,
    validation: ChartValidation,
    news_impact: NewsImpact,
) -> AnalysisPayload:
    content_values = {
        field_name: getattr(content, field_name)
        for field_name in AnalysisContent.model_fields
    }
    return AnalysisPayload.model_construct(
        **content_values,
        validation=validation,
        news_impact=news_impact,
    )


def _pending_news_impact() -> NewsImpact:
    return NewsImpact(
        collected_count=0,
        used_count=0,
        effect="none",
        summary="Server-side news assessment is pending.",
        used_titles=[],
    )


def _needs_metadata_recovery(validation: ChartValidation) -> bool:
    return validation.is_chart and validation.is_readable and (
        not (validation.detected_symbol or "").strip()
        or not (validation.detected_timeframe or "").strip()
    )


def _normalize_news_impact(
    payload: AnalysisPayload,
    news: list[NewsItem],
    include_news: bool,
    language: ResponseLanguage,
) -> AnalysisPayload:
    summaries = {
        "en-US": {
            "disabled": "News was not enabled, so only chart evidence was used.",
            "empty": "No relevant news was found, so only chart evidence was used.",
            "unused": "Collected news did not provide direct evidence that changed the chart decision.",
        },
        "en": {
            "disabled": "News was not enabled, so only chart evidence was used.",
            "empty": "No relevant news was found, so only chart evidence was used.",
            "unused": "Collected news did not provide direct evidence that changed the chart decision.",
        },
        "ko": {
            "disabled": "뉴스 옵션을 사용하지 않아 차트 이미지 근거만 반영했습니다.",
            "empty": "관련 뉴스가 없어 차트 이미지 근거만 반영했습니다.",
            "unused": "수집한 뉴스는 차트 판단을 바꿀 직접 근거로 사용하지 않았습니다.",
        },
        "ja": {
            "disabled": "ニュースを使用せず、チャートの根拠のみを反映しました。",
            "empty": "関連ニュースが見つからず、チャートの根拠のみを反映しました。",
            "unused": "収集したニュースはチャート判断を変える直接的な根拠にはなりませんでした。",
        },
        "de": {
            "disabled": "Nachrichten waren deaktiviert; berücksichtigt wurden nur Chart-Signale.",
            "empty": "Es wurden keine relevanten Nachrichten gefunden; berücksichtigt wurden nur Chart-Signale.",
            "unused": "Die gesammelten Nachrichten änderten die Chart-Entscheidung nicht direkt.",
        },
        "fr-FR": {
            "disabled": "Les actualités étaient désactivées ; seuls les éléments du graphique ont été utilisés.",
            "empty": "Aucune actualité pertinente n’a été trouvée ; seuls les éléments du graphique ont été utilisés.",
            "unused": "Les actualités collectées n’ont pas directement modifié la décision du graphique.",
        },
        "es-MX": {
            "disabled": "Las noticias estaban desactivadas; solo se usó la evidencia del gráfico.",
            "empty": "No se encontraron noticias relevantes; solo se usó la evidencia del gráfico.",
            "unused": "Las noticias recopiladas no cambiaron directamente la decisión del gráfico.",
        },
        "pt-BR": {
            "disabled": "As notícias estavam desativadas; apenas as evidências do gráfico foram usadas.",
            "empty": "Nenhuma notícia relevante foi encontrada; apenas as evidências do gráfico foram usadas.",
            "unused": "As notícias coletadas não alteraram diretamente a decisão do gráfico.",
        },
        "zh-Hant": {
            "disabled": "未啟用新聞，因此僅採用圖表證據。",
            "empty": "未找到相關新聞，因此僅採用圖表證據。",
            "unused": "收集的新聞未提供足以直接改變圖表判斷的證據。",
        },
        "id": {
            "disabled": "Berita tidak diaktifkan; hanya bukti grafik yang digunakan.",
            "empty": "Tidak ada berita relevan; hanya bukti grafik yang digunakan.",
            "unused": "Berita yang dikumpulkan tidak secara langsung mengubah keputusan grafik.",
        },
        "th": {
            "disabled": "ไม่ได้เปิดใช้ข่าว จึงใช้เฉพาะหลักฐานจากกราฟ",
            "empty": "ไม่พบข่าวที่เกี่ยวข้อง จึงใช้เฉพาะหลักฐานจากกราฟ",
            "unused": "ข่าวที่รวบรวมไม่ได้เปลี่ยนข้อสรุปจากกราฟโดยตรง",
        },
        "zh-Hans": {
            "disabled": "未启用新闻，因此仅采用图表证据。",
            "empty": "未找到相关新闻，因此仅采用图表证据。",
            "unused": "收集的新闻未提供足以直接改变图表判断的证据。",
        },
        "vi": {
            "disabled": "Tin tức chưa được bật; chỉ sử dụng bằng chứng từ biểu đồ.",
            "empty": "Không tìm thấy tin tức liên quan; chỉ sử dụng bằng chứng từ biểu đồ.",
            "unused": "Tin tức đã thu thập không trực tiếp làm thay đổi quyết định từ biểu đồ.",
        },
        "it": {
            "disabled": "Le notizie erano disattivate; sono state usate solo le evidenze del grafico.",
            "empty": "Non sono state trovate notizie pertinenti; sono state usate solo le evidenze del grafico.",
            "unused": "Le notizie raccolte non hanno modificato direttamente la decisione sul grafico.",
        },
        "tr": {
            "disabled": "Haberler etkin değildi; yalnızca grafik kanıtları kullanıldı.",
            "empty": "İlgili haber bulunamadı; yalnızca grafik kanıtları kullanıldı.",
            "unused": "Toplanan haberler grafik kararını doğrudan değiştirmedi.",
        },
        "es-ES": {
            "disabled": "Las noticias estaban desactivadas; solo se usó la evidencia del gráfico.",
            "empty": "No se encontraron noticias relevantes; solo se usó la evidencia del gráfico.",
            "unused": "Las noticias recopiladas no cambiaron directamente la decisión del gráfico.",
        },
        "fr-CA": {
            "disabled": "Les nouvelles étaient désactivées; seuls les éléments du graphique ont été utilisés.",
            "empty": "Aucune nouvelle pertinente n’a été trouvée; seuls les éléments du graphique ont été utilisés.",
            "unused": "Les nouvelles recueillies n’ont pas directement modifié la décision du graphique.",
        },
    }[language]

    if not include_news:
        impact = NewsImpact(
            collected_count=0,
            used_count=0,
            effect="none",
            summary=summaries["disabled"],
            used_titles=[],
        )
        quality = payload.data_quality.model_copy(update={"news": "unused"})
        return payload.model_copy(update={"news_impact": impact, "data_quality": quality})

    available_titles = {item.title for item in news}
    used_titles = list(dict.fromkeys(title for title in payload.news_impact.used_titles if title in available_titles))
    if not used_titles:
        impact = NewsImpact(
            collected_count=len(news),
            used_count=0,
            effect="none",
            summary=summaries["empty" if not news else "unused"],
            used_titles=[],
        )
        status = "empty" if not news else "unused"
        quality = payload.data_quality.model_copy(update={"news": status})
        return payload.model_copy(update={"news_impact": impact, "data_quality": quality})

    impact = payload.news_impact.model_copy(
        update={
            "collected_count": len(news),
            "used_count": len(used_titles),
            "used_titles": used_titles,
        }
    )
    quality = payload.data_quality.model_copy(update={"news": "included"})
    return payload.model_copy(update={"news_impact": impact, "data_quality": quality})


def _normalize_decision_labels(
    payload: AnalysisPayload,
    language: ResponseLanguage,
) -> AnalysisPayload:
    labels = {
        "en-US": {"bullish": "BUY", "bearish": "SELL", "observe": "WAIT"},
        "en": {"bullish": "BUY", "bearish": "SELL", "observe": "WAIT"},
        "ko": {"bullish": "매수", "bearish": "매도", "observe": "관망"},
        "ja": {"bullish": "買い", "bearish": "売り", "observe": "様子見"},
        "de": {"bullish": "KAUFEN", "bearish": "VERKAUFEN", "observe": "ABWARTEN"},
        "fr-FR": {"bullish": "ACHAT", "bearish": "VENTE", "observe": "ATTENDRE"},
        "es-MX": {"bullish": "COMPRAR", "bearish": "VENDER", "observe": "ESPERAR"},
        "pt-BR": {"bullish": "COMPRAR", "bearish": "VENDER", "observe": "AGUARDAR"},
        "zh-Hant": {"bullish": "買入", "bearish": "賣出", "observe": "觀望"},
        "id": {"bullish": "BELI", "bearish": "JUAL", "observe": "TUNGGU"},
        "th": {"bullish": "ซื้อ", "bearish": "ขาย", "observe": "รอดู"},
        "zh-Hans": {"bullish": "买入", "bearish": "卖出", "observe": "观望"},
        "vi": {"bullish": "MUA", "bearish": "BÁN", "observe": "CHỜ"},
        "it": {"bullish": "ACQUISTA", "bearish": "VENDI", "observe": "ATTENDI"},
        "tr": {"bullish": "AL", "bearish": "SAT", "observe": "BEKLE"},
        "es-ES": {"bullish": "COMPRAR", "bearish": "VENDER", "observe": "ESPERAR"},
        "fr-CA": {"bullish": "ACHAT", "bearish": "VENTE", "observe": "ATTENDRE"},
    }[language]
    dissent_thesis = {
        "en-US": "I withhold the consensus call until a confirmed retest; the visible opposing scenario remains valid.",
        "en": "I withhold the consensus call until a confirmed retest; the visible opposing scenario remains valid.",
        "ko": "확인된 재시험 전까지 합의 판단을 보류하며, 화면에 보이는 반대 시나리오는 아직 유효합니다.",
        "ja": "再テストが確認されるまで合意判断を保留し、画面上の反対シナリオはまだ有効と見ます。",
        "de": "Bis zu einem bestätigten Retest halte ich mich zurück; das sichtbare Gegenszenario bleibt gültig.",
        "fr-FR": "Je suspends le consensus jusqu’à un retest confirmé; le scénario opposé visible reste valable.",
        "es-MX": "Pospongo el consenso hasta confirmar un retesteo; el escenario opuesto visible sigue vigente.",
        "pt-BR": "Adio o consenso até um reteste confirmado; o cenário oposto visível continua válido.",
        "zh-Hant": "在確認重新測試前，我保留共識判斷；圖中可見的反向情境仍然有效。",
        "id": "Saya menahan keputusan konsensus sampai retest terkonfirmasi; skenario lawan yang terlihat masih valid.",
        "th": "ฉันขอรอการทดสอบซ้ำที่ยืนยันแล้วก่อน และมองว่าสถานการณ์ฝั่งตรงข้ามยังมีผลอยู่",
        "zh-Hans": "在确认重新测试前，我保留共识判断；图中可见的反向情景仍然有效。",
        "vi": "Tôi tạm hoãn kết luận đồng thuận cho đến khi có kiểm tra lại; kịch bản đối lập vẫn còn hiệu lực.",
        "it": "Sospendo il consenso fino a un retest confermato; lo scenario opposto visibile resta valido.",
        "tr": "Onaylı bir yeniden test gelene kadar uzlaşıyı bekletiyorum; görünen karşı senaryo hâlâ geçerli.",
        "es-ES": "Pospongo el consenso hasta confirmar un retesteo; el escenario opuesto visible sigue vigente.",
        "fr-CA": "Je suspends le consensus jusqu’à un nouveau test confirmé; le scénario opposé visible demeure valable.",
    }[language]

    def normalized_code(value: str) -> str:
        return value if value in {"bullish", "bearish"} else "observe"

    consensus_code = normalized_code(payload.consensus.stance_code)
    consensus = payload.consensus.model_copy(
        update={"stance_code": consensus_code, "title": labels[consensus_code]}
    )
    opinions = [
        opinion.model_copy(
            update={
                "stance_code": normalized_code(opinion.stance_code),
                "stance": labels[normalized_code(opinion.stance_code)],
            }
        )
        for opinion in payload.agent_opinions
    ]
    if len(opinions) > 1 and all(opinion.stance_code == consensus_code for opinion in opinions):
        dissent_index = next(
            (index for index, opinion in enumerate(opinions) if opinion.agent_id == "devil"),
            len(opinions) - 1,
        )
        dissent_code = "observe" if consensus_code in {"bullish", "bearish"} else "bearish"
        opinions[dissent_index] = opinions[dissent_index].model_copy(
            update={
                "stance_code": dissent_code,
                "stance": labels[dissent_code],
                "thesis": dissent_thesis,
            }
        )
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
