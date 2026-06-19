from __future__ import annotations

from datetime import UTC, datetime
from typing import assert_never
from uuid import uuid4

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import (
    FlirtistAnalysisCard,
    FlirtistCoachChatRequest,
    FlirtistCoachChatResponse,
    FlirtistCoachMessage,
    FlirtistInterestBreakdown,
    FlirtistMessageCount,
    FlirtistPreviewMessage,
    FlirtistProductSessionRequest,
    FlirtistProductSessionResponse,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.services.flirtist_product_ai import FlirtistProductAI
from app.services.flirtist_product_coach import coach_answer, coach_suggestions, repair_coach_response
from app.services.flirtist_product_coach_memory import coach_memory_summary
from app.services.flirtist_product_image_storage import FlirtistProductImageStorage, FlirtistStoredImage
from app.services.flirtist_product_reply_quality import repair_reply_coaching
from app.services.flirtist_product_repository import FlirtistProductRepository
from app.services.flirtist_product_reply_fallback import ensure_reply_packs, reply_coaching
from app.services.flirtist_product_transcript import clean_preview_messages, preview_messages


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
        stored_image = self._image_storage.store_session_image(
            request,
            user_id=user_id,
            client_install_id=client_install_id,
        )
        fallback = _fallback_session(request, stored_image)
        response = self._ai.complete_session(
            request=request,
            fallback=fallback,
            image_url=stored_image.url if stored_image else None,
        )
        if response.replyCoaching:
            language = _language(response.language, response.locale)
            chat_preview = _authoritative_chat_preview(language, request) or clean_preview_messages(
                language,
                response.chatPreview,
            )
            coaching = ensure_reply_packs(response.replyCoaching, language, chat_preview)
            response = response.model_copy(
                update={
                    "chatPreview": chat_preview,
                    "replyCoaching": repair_reply_coaching(coaching, language, chat_preview),
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
            replyCoaching=reply_coaching(language, request.style, messages, focus=request.focus),
        )
        response = self._ai.complete_style(request=request, fallback=fallback)
        coaching = ensure_reply_packs(response.replyCoaching, language, messages)
        return response.model_copy(update={"replyCoaching": repair_reply_coaching(coaching, language, messages)})

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
            return FlirtistProductSessionResponse(**base, analysisCard=_analysis_card(language, chat_preview))
        case unreachable:
            assert_never(unreachable)


def _authoritative_chat_preview(
    language: FlirtistLanguage,
    request: FlirtistProductSessionRequest,
) -> list[FlirtistPreviewMessage] | None:
    if request.source != "manual" or not request.text:
        return None
    return preview_messages(language, request.text)


def _language(language: FlirtistLanguage | None, locale: str) -> FlirtistLanguage:
    if language in {"en", "ko"}:
        return language
    return "ko" if locale.lower().startswith("ko") else "en"


def _locale(language: FlirtistLanguage, locale: str) -> str:
    return "ko-KR" if language == "ko" else (locale if locale.startswith("en") else "en-US")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:18]}"


def _title(language: FlirtistLanguage, request: FlirtistProductSessionRequest) -> str:
    if request.mode == "score_analysis":
        return "Chat Wrapped" if language == "en" else "채팅 점수화"
    if request.source == "screenshot":
        return "Screenshot reply coach" if language == "en" else "스크린샷 답장 코칭"
    return "Manual text reply coach" if language == "en" else "텍스트 답장 코칭"


def _analysis_card(language: FlirtistLanguage, messages: list[FlirtistPreviewMessage]) -> FlirtistAnalysisCard:
    my_count = sum(1 for message in messages if message.role == "me")
    them_count = sum(1 for message in messages if message.role == "them")
    if language == "ko":
        return FlirtistAnalysisCard(
            title="Chat Wrapped",
            messageCount=FlirtistMessageCount(you=max(my_count, 1), them=max(them_count, 1)),
            interestLevel=FlirtistInterestBreakdown(you=68, them=56),
            meaningfulWordsYou=["커피", "퇴근", "같이"],
            meaningfulWordsThem=["회사", "정신", "고생"],
            redFlags=["상대 답장 텀이 느림"],
            greenFlags=["상대가 하루 맥락을 공유함", "가벼운 제안 여지 있음"],
            attachmentYou="안정형",
            attachmentThem="신중형",
            compatibilityScore=72,
        )
    return FlirtistAnalysisCard(
        title="Chat Wrapped",
        messageCount=FlirtistMessageCount(you=max(my_count, 1), them=max(them_count, 1)),
        interestLevel=FlirtistInterestBreakdown(you=68, them=56),
        meaningfulWordsYou=["coffee", "after work", "together"],
        meaningfulWordsThem=["work", "chaotic", "tired"],
        redFlags=["Their response pace looks slow"],
        greenFlags=["They shared personal context", "There is room for a light invite"],
        attachmentYou="Secure",
        attachmentThem="Cautious",
        compatibilityScore=72,
    )
