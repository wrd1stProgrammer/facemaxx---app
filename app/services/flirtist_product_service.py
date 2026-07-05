from __future__ import annotations

from datetime import UTC, datetime
from typing import assert_never
from uuid import uuid4

from app.schemas.flirtist import FlirtistLanguage, default_locale_for_language, normalize_flirtist_language
from app.schemas.flirtist_product import (
    FlirtistCoachChatRequest,
    FlirtistCoachChatResponse,
    FlirtistCoachMessage,
    FlirtistPreviewMessage,
    FlirtistProductSessionRequest,
    FlirtistProductSessionResponse,
    FlirtistReplyCoaching,
    FlirtistReplyOption,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.services.flirtist_product_ai import FlirtistProductAI, FlirtistProductAIError
from app.services.flirtist_product_analysis_fallback import analysis_card
from app.services.flirtist_product_coach import coach_answer, coach_suggestions, repair_coach_response
from app.services.flirtist_product_coach_memory import coach_memory_summary
from app.services.flirtist_product_image_storage import FlirtistProductImageStorage, FlirtistStoredImage
from app.services.flirtist_product_reply_pack_guard import ensure_complete_screenshot_reply_packs
from app.services.flirtist_product_reply_quality import repair_reply_coaching
from app.services.flirtist_product_repository import FlirtistProductRepository
from app.services.flirtist_product_reply_fallback import ensure_reply_packs, reply_coaching
from app.services.flirtist_product_transcript import clean_preview_messages, preview_messages
from app.services.flirtist_language_profile import analysis_title


class FlirtistProductService:
    def __init__(
        self,
        ai: FlirtistProductAI | None = None,
        image_storage: FlirtistProductImageStorage | None = None,
        repository: FlirtistProductRepository | None = None,
    ) -> None:
        self._ai = ai or FlirtistProductAI()
        self._image_storage = image_storage or FlirtistProductImageStorage()
        self._repository = repository or FlirtistProductRepository()

    def create_session(
        self,
        request: FlirtistProductSessionRequest,
        *,
        user_id: str | None = None,
        client_install_id: str | None = None,
    ) -> FlirtistProductSessionResponse:
        stored_image = (
            self._image_storage.store_session_image(
                request,
                user_id=user_id,
                client_install_id=client_install_id,
            )
            if _should_store_session_image(request)
            else None
        )
        fallback = _fallback_session(request, stored_image)
        response = self._ai.complete_session(
            request=request,
            fallback=fallback,
            image_url=_ai_image_url(request, stored_image),
        )
        if response.replyCoaching:
            language = _language(response.language, response.locale)
            content_kind = response.contentKind
            chat_preview = _authoritative_chat_preview(language, request) or clean_preview_messages(
                language,
                response.chatPreview,
            )
            ensure_complete_screenshot_reply_packs(request, response.replyCoaching)
            coaching = ensure_reply_packs(
                response.replyCoaching,
                language,
                chat_preview,
                content_kind=content_kind,
            )
            response = response.model_copy(
                update={
                    "title": _content_title(language, response),
                    "chatPreview": chat_preview,
                    "replyCoaching": repair_reply_coaching(coaching, language, chat_preview, content_kind=content_kind),
                }
            )
        if stored_image:
            response = response.model_copy(
                update={
                    "imageUrl": stored_image.url,
                    "imageStoragePath": stored_image.storage_path,
                }
            )
        persisted = self._repository.save_session(
            request=request,
            response=response,
            stored_image=stored_image,
            user_id=user_id,
            client_install_id=client_install_id,
        )
        return response.model_copy(update={"saved": True, "serverPersisted": persisted})

    def regenerate_reply(self, request: FlirtistReplyStyleRequest) -> FlirtistReplyStyleResponse:
        language = _language(request.language, request.locale)
        messages = preview_messages(language, request.context)
        fallback = FlirtistReplyStyleResponse(
            sessionId=request.sessionId or _new_id("flt"),
            replyCoaching=reply_coaching(
                language,
                request.style,
                messages,
                focus=request.focus,
                content_kind=request.contentKind,
            ),
        )
        response = self._ai.complete_style(request=request, fallback=fallback)
        coaching = ensure_reply_packs(
            response.replyCoaching,
            language,
            messages,
            excluded_texts=request.existingReplies,
            fill_missing=not request.existingReplies,
            content_kind=request.contentKind,
        )
        repaired = repair_reply_coaching(
            coaching,
            language,
            messages,
            excluded_texts=request.existingReplies,
            fill_missing=not request.existingReplies,
            content_kind=request.contentKind,
        )
        if request.existingReplies:
            _raise_if_regeneration_failed(request, repaired)
        return response.model_copy(update={"replyCoaching": repaired})

    def coach_chat(self, request: FlirtistCoachChatRequest) -> FlirtistCoachChatResponse:
        language = _language(request.language, request.locale)
        memory_summary = coach_memory_summary(language, request)
        fallback = FlirtistCoachChatResponse(
            sessionId=request.sessionId or _new_id("coach"),
            message=FlirtistCoachMessage(role="assistant", text=coach_answer(language, request)),
            suggestions=coach_suggestions(language, request),
            memorySummary=memory_summary,
        )
        response = self._ai.complete_coach_chat(request=request, fallback=fallback)
        repaired = repair_coach_response(language, request, response)
        return repaired.model_copy(update={"memorySummary": memory_summary})


def _fallback_session(
    request: FlirtistProductSessionRequest,
    stored_image: FlirtistStoredImage | None,
) -> FlirtistProductSessionResponse:
    language = _language(request.language, request.locale)
    chat_preview = preview_messages(language, request.text)
    base = {
        "sessionId": _new_id("flt"),
        "mode": request.mode,
        "source": request.source,
        "contentKind": "chat",
        "title": _title(language, request),
        "locale": _locale(language, request.locale),
        "language": language,
        "createdAt": datetime.now(tz=UTC).isoformat(),
        "saved": True,
        "serverPersisted": False,
        "imageUrl": stored_image.url if stored_image else None,
        "imageStoragePath": stored_image.storage_path if stored_image else None,
        "chatPreview": chat_preview,
    }
    match request.mode:
        case "reply_coach":
            return FlirtistProductSessionResponse(**base, replyCoaching=reply_coaching(language, "genuine", chat_preview))
        case "score_analysis":
            return FlirtistProductSessionResponse(**base, analysisCard=analysis_card(language, chat_preview))
        case unreachable:
            assert_never(unreachable)


def _should_store_session_image(request: FlirtistProductSessionRequest) -> bool:
    if not request.imageBase64:
        return False
    match request.source:
        case "screenshot":
            return True
        case "manual":
            return False
        case unreachable:
            assert_never(unreachable)


def _ai_image_url(
    request: FlirtistProductSessionRequest,
    stored_image: FlirtistStoredImage | None,
) -> str | None:
    if stored_image is None:
        return None
    match request.source:
        case "screenshot":
            return stored_image.url
        case "manual":
            return None
        case unreachable:
            assert_never(unreachable)


def _authoritative_chat_preview(
    language: FlirtistLanguage,
    request: FlirtistProductSessionRequest,
) -> list[FlirtistPreviewMessage] | None:
    if not request.text:
        return None
    match request.source:
        case "screenshot":
            return None
        case "manual":
            return preview_messages(language, request.text)
        case unreachable:
            assert_never(unreachable)


def _language(language: FlirtistLanguage | None, locale: str) -> FlirtistLanguage:
    return normalize_flirtist_language(language, locale)


def _content_title(language: FlirtistLanguage, response: FlirtistProductSessionResponse) -> str:
    if response.mode != "reply_coach" or response.contentKind != "bio":
        return response.title
    if language == "ko":
        return "프로필 첫 메시지"
    return "Profile opener ideas"


def _locale(language: FlirtistLanguage, locale: str) -> str:
    return default_locale_for_language(language, locale)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:18]}"


def _raise_if_regeneration_failed(
    request: FlirtistReplyStyleRequest,
    coaching: FlirtistReplyCoaching,
) -> None:
    replies = _unique_unblocked_replies(coaching.replies, request.existingReplies)
    if len(replies) < 4:
        raise FlirtistProductAIError(reason=_generation_failure_message(request.locale))


def _unique_unblocked_replies(
    replies: list[FlirtistReplyOption],
    blocked: list[str],
) -> list[FlirtistReplyOption]:
    blocked_texts = {_normalized_reply_text(text) for text in blocked}
    seen: set[str] = set()
    unique: list[FlirtistReplyOption] = []
    for reply in replies:
        normalized = _normalized_reply_text(reply.text)
        if not normalized or normalized in blocked_texts or normalized in seen:
            continue
        unique.append(reply)
        seen.add(normalized)
    return unique


def _generation_failure_message(locale: str) -> str:
    if locale.lower().startswith("ko"):
        return "생성에 실패했습니다. 다시 시도해 주세요."
    return "Generation failed. Please try again."


def _normalized_reply_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _title(language: FlirtistLanguage, request: FlirtistProductSessionRequest) -> str:
    if request.mode == "score_analysis":
        return analysis_title(language)
    if request.source == "screenshot":
        if language == "ko":
            return "스크린샷 답장 코칭"
        return "Screenshot reply coach"
    if language == "ko":
        return "텍스트 답장 코칭"
    return "Manual text reply coach"
