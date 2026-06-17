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
    FlirtistReplyCoaching,
    FlirtistReplyOption,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.services.flirtist_product_ai import FlirtistProductAI
from app.services.flirtist_product_image_storage import FlirtistProductImageStorage, FlirtistStoredImage
from app.services.flirtist_product_repository import FlirtistProductRepository


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
        fallback = FlirtistReplyStyleResponse(
            sessionId=request.sessionId or _new_id("flt"),
            replyCoaching=_reply_coaching(_language(request.language, request.locale), request.style),
        )
        return self._ai.complete_style(request=request, fallback=fallback)

    def coach_chat(self, request: FlirtistCoachChatRequest) -> FlirtistCoachChatResponse:
        language = _language(request.language, request.locale)
        fallback = FlirtistCoachChatResponse(
            sessionId=request.sessionId or _new_id("coach"),
            message=FlirtistCoachMessage(role="assistant", text=_coach_answer(language)),
            suggestions=_coach_suggestions(language),
        )
        return self._ai.complete_coach_chat(request=request, fallback=fallback)


def _fallback_session(
    request: FlirtistProductSessionRequest,
    stored_image: FlirtistStoredImage | None,
) -> FlirtistProductSessionResponse:
    language = _language(request.language, request.locale)
    chat_preview = _preview_messages(language, request.text)
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
            return FlirtistProductSessionResponse(**base, replyCoaching=_reply_coaching(language, "genuine"))
        case "score_analysis":
            return FlirtistProductSessionResponse(**base, analysisCard=_analysis_card(language, chat_preview))
        case unreachable:
            assert_never(unreachable)


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


def _preview_messages(language: FlirtistLanguage, text: str | None) -> list[FlirtistPreviewMessage]:
    if not text:
        return [
            FlirtistPreviewMessage(role="system", text="Screenshot uploaded" if language == "en" else "스크린샷 업로드됨")
        ]
    messages: list[FlirtistPreviewMessage] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith(("me:", "나:", "저:")):
            messages.append(FlirtistPreviewMessage(role="me", text=line.split(":", 1)[1].strip()))
        elif lowered.startswith(("them:", "상대:", "그쪽:")):
            messages.append(FlirtistPreviewMessage(role="them", text=line.split(":", 1)[1].strip()))
        else:
            messages.append(FlirtistPreviewMessage(role="them", text=line))
    return messages or [FlirtistPreviewMessage(role="system", text=text[:500])]


def _reply_coaching(language: FlirtistLanguage, style: str) -> FlirtistReplyCoaching:
    if language == "ko":
        reply = _styled_reply_ko(style)
        return FlirtistReplyCoaching(
            headline="AI 추천 답장",
            summary="상대가 피곤함을 공유했으니 공감 한 줄 뒤에 가벼운 제안을 붙이는 흐름이 좋아요.",
            nextMove="부담 없이 답하기 쉬운 한 문장으로 보내세요.",
            replies=[reply],
        )
    reply = _styled_reply_en(style)
    return FlirtistReplyCoaching(
        headline="AI generated rizz",
        summary="They shared context, so acknowledge it and offer one easy next step.",
        nextMove="Send a warm reply that is specific but low-pressure.",
        replies=[reply],
    )


def _styled_reply_ko(style: str) -> FlirtistReplyOption:
    text = "그럼 오늘은 고생한 기념으로, 퇴근 후에 우리 같이 커피 한잔할래?"
    if style.lower() in {"funny", "witty"}:
        text = "오늘 살아남은 기념으로 커피 훈장 하나 받으러 갈래?"
    if style.lower() in {"short", "calm"}:
        text = "오늘 고생했어. 퇴근 후에 가볍게 커피 한잔할래?"
    return FlirtistReplyOption(
        id=_new_id("reply"),
        style=style,
        text=text,
        whyItWorks="공감과 제안이 함께 있어 자연스럽고 답하기 쉽습니다.",
        aiObviousness=12,
        pressure=18,
        replyLikelihood=84,
    )


def _styled_reply_en(style: str) -> FlirtistReplyOption:
    text = "Sounds like you earned a reset. Want to grab coffee after work sometime this week?"
    if style.lower() in {"funny", "witty"}:
        text = "You survived work chaos, so coffee feels legally required. Want to go this week?"
    if style.lower() in {"short", "calm"}:
        text = "That sounds like a lot. Want to decompress over coffee this week?"
    return FlirtistReplyOption(
        id=_new_id("reply"),
        style=style,
        text=text,
        whyItWorks="It validates their day and gives them an easy yes/no next step.",
        aiObviousness=12,
        pressure=18,
        replyLikelihood=84,
    )


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


def _coach_answer(language: FlirtistLanguage) -> str:
    if language == "ko":
        return "좋아요. 지금은 밀어붙이기보다 상대가 답하기 쉬운 낮은 압도의 제안이 좋아요. 마지막 메시지를 한 번 공감하고, 날짜는 하나만 가볍게 열어두세요."
    return "Good read. After a slow chat, keep the move low-pressure: acknowledge her week, make one simple invite, and leave an easy out so it feels relaxed."


def _coach_suggestions(language: FlirtistLanguage) -> list[str]:
    if language == "ko":
        return ["이 상황에서 보낼 문장 만들어줘", "상대가 늦게 답할 때 대처법", "부담스럽지 않은 데이트 제안"]
    return ["Write the exact message", "Practice if she says maybe", "Make it more playful"]
