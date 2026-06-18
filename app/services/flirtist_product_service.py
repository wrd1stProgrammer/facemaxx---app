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
    FlirtistReplyPack,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.services.flirtist_product_ai import FlirtistProductAI
from app.services.flirtist_product_coach import coach_answer, coach_suggestions
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
        if response.replyCoaching:
            response = response.model_copy(
                update={"replyCoaching": _ensure_reply_packs(response.replyCoaching, _language(response.language, response.locale))}
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
        fallback = FlirtistReplyStyleResponse(
            sessionId=request.sessionId or _new_id("flt"),
            replyCoaching=_reply_coaching(language, request.style, focus=request.focus),
        )
        response = self._ai.complete_style(request=request, fallback=fallback)
        return response.model_copy(update={"replyCoaching": _ensure_reply_packs(response.replyCoaching, language)})

    def coach_chat(self, request: FlirtistCoachChatRequest) -> FlirtistCoachChatResponse:
        language = _language(request.language, request.locale)
        fallback = FlirtistCoachChatResponse(
            sessionId=request.sessionId or _new_id("coach"),
            message=FlirtistCoachMessage(role="assistant", text=coach_answer(language, request)),
            suggestions=coach_suggestions(language, request),
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


def _ensure_reply_packs(coaching: FlirtistReplyCoaching, language: FlirtistLanguage) -> FlirtistReplyCoaching:
    if coaching.replyPacks:
        return coaching
    packs = _reply_packs(language)
    return coaching.model_copy(update={"replyPacks": packs})


def _reply_coaching(language: FlirtistLanguage, style: str, focus: str | None = None) -> FlirtistReplyCoaching:
    packs = _reply_packs(language, focus=focus)
    selected = next((pack for pack in packs if pack.style == style.lower()), packs[0])
    if language == "ko":
        return FlirtistReplyCoaching(
            headline="AI 추천 답장",
            summary="상대가 피곤함을 공유했으니 공감 한 줄 뒤에 가벼운 제안을 붙이는 흐름이 좋아요.",
            nextMove="부담 없이 답하기 쉬운 한 문장으로 보내세요.",
            replies=selected.replies,
            replyPacks=packs,
        )
    return FlirtistReplyCoaching(
        headline="AI generated rizz",
        summary="They shared context, so acknowledge it and offer one easy next step.",
        nextMove="Send a warm reply that is specific but low-pressure.",
        replies=selected.replies,
        replyPacks=packs,
    )


def _reply_packs(language: FlirtistLanguage, focus: str | None = None) -> list[FlirtistReplyPack]:
    specs = _reply_pack_specs(language)
    return [
        FlirtistReplyPack(
            style=style,
            label=label,
            buttonTitle=button_title,
            iconName=icon,
            replies=[
                _reply_option(language, style, text, _why_for_style(language, style))
                for text in _reply_texts(language, style, focus)
            ],
        )
        for style, label, button_title, icon in specs
    ]


def _reply_pack_specs(language: FlirtistLanguage) -> list[tuple[str, str, str, str]]:
    if language == "ko":
        return [
            ("genuine", "Genuine", "진짜같은 답장 받기", "bolt.fill"),
            ("nsfw", "NSFW", "Get NSFW Reply", "flame.fill"),
            ("flirty", "Flirty", "Get Flirty Reply", "heart.fill"),
            ("witty", "Witty", "Get Witty Reply", "sparkles"),
            ("romantic", "Romantic", "Get Romantic Reply", "rose.fill"),
        ]
    return [
        ("genuine", "Genuine", "Get Genuine Reply", "bolt.fill"),
        ("nsfw", "NSFW", "Get NSFW Reply", "flame.fill"),
        ("flirty", "Flirty", "Get Flirty Reply", "heart.fill"),
        ("witty", "Witty", "Get Witty Reply", "sparkles"),
        ("romantic", "Romantic", "Get Romantic Reply", "rose.fill"),
    ]


def _reply_texts(language: FlirtistLanguage, style: str, focus: str | None) -> list[str]:
    focus_hint = _focus_hint(language, focus)
    if language == "ko":
        match style:
            case "nsfw":
                return [
                    f"{focus_hint}이런 말 조심해야 하는데, 네 얘기 들으니까 더 보고 싶어졌어.",
                    f"{focus_hint}오늘 힘 빠졌겠다. 내가 옆에 있었으면 좀 덜 얌전하게 웃겨줬을 텐데.",
                    f"{focus_hint}지금은 쉬는 게 먼저인데, 나중에 보면 꽤 위험하게 재밌을 것 같아.",
                    f"{focus_hint}너랑 있으면 괜히 장난이 더 세질 것 같은데, 그거 괜찮아?",
                    f"{focus_hint}오늘은 푹 쉬고, 컨디션 돌아오면 나랑 조금 더 가까이 얘기하자.",
                ]
            case "flirty":
                return [
                    f"{focus_hint}그 정도면 오늘은 쉬어야겠다. 괜찮아지면 내가 기분 전환 시켜줄게.",
                    f"{focus_hint}오늘 정신없었으면, 이번 주엔 내가 좀 편한 시간 만들어줘도 돼?",
                    f"{focus_hint}듣기만 해도 빡세다. 나중에 잠깐 만나서 머리 식히자.",
                    f"{focus_hint}오늘 하루는 회사가 가져갔으니까, 남은 시간은 네가 좀 편했으면 좋겠다.",
                    f"{focus_hint}고생했네. 컨디션 괜찮을 때 나랑 맛있는 거 먹으면서 풀자.",
                ]
            case "witty":
                return [
                    f"{focus_hint}오늘 난이도 너무 높았네. 일단 생존 축하부터 해야겠다.",
                    f"{focus_hint}그 정도면 퇴근이 아니라 탈출인데? 무사 귀환 축하해.",
                    f"{focus_hint}오늘 회사가 보스전이었으면, 보상 장면은 내가 챙겨도 돼?",
                    f"{focus_hint}지금은 대단한 말보다 누워 있기 버튼이 필요해 보인다.",
                    f"{focus_hint}오늘은 아무것도 안 해도 무죄야. 대신 나중에 썰은 들어야겠어.",
                ]
            case "romantic":
                return [
                    f"{focus_hint}그런 날엔 긴 말보다 편하게 쉬는 게 먼저지. 나중에 천천히 얘기 들어줄게.",
                    f"{focus_hint}오늘 하루가 좀 버거웠겠다. 무리하지 말고, 괜찮아지면 내가 같이 있어줄게.",
                    f"{focus_hint}힘든 얘기인데도 말해줘서 좋아. 지금은 네가 좀 편했으면 좋겠다.",
                    f"{focus_hint}오늘은 그냥 쉬어. 나중에 컨디션 돌아오면 얼굴 보고 얘기하자.",
                    f"{focus_hint}그 얘기 들으니까 괜히 마음 쓰이네. 오늘은 너부터 챙겨.",
                ]
            case _:
                return [
                    f"{focus_hint}오늘 진짜 정신없었겠다. 일단 푹 쉬고, 괜찮아지면 얘기 더 들려줘.",
                    f"{focus_hint}듣기만 해도 피곤하다. 지금은 쉬고, 나중에 편할 때 이어서 얘기하자.",
                    f"{focus_hint}그 정도면 오늘은 아무것도 안 해도 인정이야. 무리하지 마.",
                    f"{focus_hint}고생 많았네. 컨디션 괜찮아지면 잠깐 기분 전환하러 나가자.",
                    f"{focus_hint}말해줘서 고마워. 오늘은 일단 쉬고, 나중에 편하게 얘기하자.",
                ]
    match style:
        case "nsfw":
            return [
                f"{focus_hint}Careful, if we get coffee after work I might forget to play it cool around you.",
                f"{focus_hint}You sound like trouble in the best way, and I am slightly too curious now.",
                f"{focus_hint}If this is me behaving, imagine what happens when we actually meet.",
                f"{focus_hint}I was going to keep this innocent, but you make that harder than expected.",
                f"{focus_hint}Coffee is the excuse. Seeing whether the tension is real is the plan.",
            ]
        case "flirty":
            return [
                f"{focus_hint}Sounds like you earned a reset. Want to grab coffee after work sometime this week?",
                f"{focus_hint}That day sounds chaotic. I can offer coffee and a much better distraction.",
                f"{focus_hint}You survived the day, so I think a small reward is fair. Coffee with me?",
                f"{focus_hint}I would say rest up, but I also want to steal an hour of your week.",
                f"{focus_hint}If your week needs a better plot twist, I can volunteer as coffee company.",
            ]
        case "witty":
            return [
                f"{focus_hint}You survived work chaos, so coffee feels legally required. Want to go this week?",
                f"{focus_hint}Your day sounds like it needs a soft reboot and caffeine. I can help with one of those.",
                f"{focus_hint}That sounds like a day with boss-level difficulty. Coffee side quest?",
                f"{focus_hint}I respect the survival arc. Now we just need the reward scene.",
                f"{focus_hint}If chaos was the main event, I can be the calmer afterparty.",
            ]
        case "romantic":
            return [
                f"{focus_hint}That sounds heavy. Let me make one part of your week feel easier over coffee.",
                f"{focus_hint}I like hearing about your day, but I would rather hear it while sitting across from you.",
                f"{focus_hint}Long day. Small coffee. Good company. I can handle the last two.",
                f"{focus_hint}If you need a softer ending to that day, I would love to be part of it.",
                f"{focus_hint}You deserve a calmer hour. I would be happy to borrow one with you.",
            ]
        case _:
            return [
                f"{focus_hint}That sounds like a lot. Want to decompress over coffee this week?",
                f"{focus_hint}Sounds like you had a real day. If you want a low-pressure reset, I am free for coffee.",
                f"{focus_hint}I am glad you made it through. Want to trade chaos stories over coffee?",
                f"{focus_hint}No pressure, but I would like to hear the full story sometime this week.",
                f"{focus_hint}That day deserves a better ending. Coffee sometime?",
            ]


def _reply_option(language: FlirtistLanguage, style: str, text: str, why: str) -> FlirtistReplyOption:
    return FlirtistReplyOption(
        id=_new_id("reply"),
        style=style,
        text=text,
        whyItWorks=why,
        aiObviousness=12,
        pressure=18,
        replyLikelihood=84,
    )


def _why_for_style(language: FlirtistLanguage, style: str) -> str:
    if language == "ko":
        match style:
            case "nsfw":
                return "강한 텐션은 주되 노골적 압박 없이 선택권을 남깁니다."
            case "witty":
                return "가벼운 농담으로 피곤한 흐름을 낮은 압도로 바꿉니다."
            case "romantic":
                return "상대의 하루를 챙기는 느낌이라 진심이 살아납니다."
            case "flirty":
                return "공감과 제안을 함께 넣어 답장하기 쉽습니다."
            case _:
                return "자연스럽고 부담 없는 초대라 실제 대화처럼 느껴집니다."
    match style:
        case "nsfw":
            return "It raises tension without getting explicit or pressuring them."
        case "witty":
            return "The joke lightens the mood while keeping the invite clear."
        case "romantic":
            return "It feels attentive and specific without overdoing it."
        case "flirty":
            return "It validates their day and opens a simple next step."
        case _:
            return "It is warm, low-pressure, and easy to answer."


def _focus_hint(language: FlirtistLanguage, focus: str | None) -> str:
    if not focus:
        return ""
    clipped = focus.strip().replace("\n", " ")[:28]
    if not clipped:
        return ""
    return "" if language == "ko" else f"With {clipped} in mind, "


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
