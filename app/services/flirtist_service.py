from __future__ import annotations

from typing import Protocol

from app.schemas.flirtist import (
    FlirtistChatRequest,
    FlirtistDraftRequest,
    FlirtistGenerateRequest,
    FlirtistGoalRequest,
    FlirtistOCRRequest,
    FlirtistPickupLinesRequest,
    FlirtistPickupLinesResponse,
    FlirtistProfileRequest,
    FlirtistResponse,
)
from app.services.flirtist_config import FlirtistAIConfig, load_flirtist_ai_config
from app.services.flirtist_provider import FlirtistAIProviderGateway, FlirtistProviderTransport


class LocaleRequest(Protocol):
    language: str | None
    locale: str


class FlirtistService:
    def __init__(
        self,
        config: FlirtistAIConfig | None = None,
        provider_gateway: FlirtistAIProviderGateway | None = None,
        provider_transport: FlirtistProviderTransport | None = None,
    ):
        self.config = config or load_flirtist_ai_config()
        self.provider_gateway = provider_gateway or FlirtistAIProviderGateway(
            self.config,
            transport=provider_transport,
        )

    def analyze_chat(self, request: FlirtistChatRequest) -> FlirtistResponse:
        language = _language(request)
        text = _combined_messages(request.messages)
        unsafe = _risk_flags(text)
        fallback = _response(
            language=language,
            locale=_locale(language, request.locale),
            summary=_copy(language, "They are keeping the thread warm with enough detail to continue.", "상대가 대화 소재를 이어주고 있어 호감 신호가 있습니다."),
            interest=74 if not unsafe else 35,
            vibe=_copy(language, "Warm, curious, lightly flirty", "편안하고 살짝 호감"),
            risks=unsafe,
        )
        return self.provider_gateway.complete(action="analyze_chat", request=request, fallback=fallback)

    def generate_replies(self, request: FlirtistGenerateRequest) -> FlirtistResponse:
        language = _language(request)
        response = _response(
            language=language,
            locale=_locale(language, request.locale),
            summary=_copy(language, "They are keeping the thread warm with enough detail to continue.", "상대가 대화 소재를 이어주고 있어 호감 신호가 있습니다."),
            interest=74,
            vibe=_copy(language, "Warm, curious, lightly flirty", "편안하고 살짝 호감"),
        )
        response.replies = _replies(language)
        response.whyItWorks = _why(language)
        response.recommendedAction = _copy(language, "Send the playful specific reply.", "구체적인 가벼운 답장을 보내세요.")
        return self.provider_gateway.complete(action="generate_replies", request=request, fallback=response)

    def generate_pickup_lines(self, request: FlirtistPickupLinesRequest) -> FlirtistPickupLinesResponse:
        language = _language(request)
        fallback = FlirtistPickupLinesResponse(
            situation=request.situation,
            lines=_pickup_lines(language, request.situation),
            language=language,
            locale=_locale(language, request.locale),
        )
        return self.provider_gateway.complete_pickup_lines(request=request, fallback=fallback)

    def check_draft(self, request: FlirtistDraftRequest) -> FlirtistResponse:
        language = _language(request)
        risks = _risk_flags(request.draft)
        blocked = bool(risks)
        fallback = _response(
            language=language,
            locale=_locale(language, request.locale),
            summary=_copy(language, "Draft checked for tone, pressure, and safety.", "문장의 톤과 부담감을 점검했습니다."),
            interest=50,
            vibe=_copy(language, "Needs a safer rewrite" if blocked else "Clear and low-pressure", "안전한 수정 필요" if blocked else "담백하고 자연스러움"),
            risks=risks,
            improved="" if blocked else _copy(language, "That sounds fun. Are you free one evening this week?", "좋아요. 이번 주 중 편한 날에 가볍게 볼까요?"),
            action=_copy(language, "I can't help write sexual, minor-involved, coercive, or harassing messages." if blocked else "Send the lighter version.", "미성년자, 성적 압박, 조작적 메시지는 도와드릴 수 없습니다." if blocked else "부담을 낮춘 문장으로 보내세요."),
        )
        return self.provider_gateway.complete(action="check_draft", request=request, fallback=fallback)

    def profile_coach(self, request: FlirtistProfileRequest) -> FlirtistResponse:
        language = _language(request)
        fallback = _response(
            language=language,
            locale=_locale(language, request.locale),
            summary=_copy(language, "Profile has usable hooks; sharpen the first line and make photos activity-led.", "프로필에 대화 시작점이 있습니다. 첫 문장과 사진 맥락을 더 선명하게 다듬으세요."),
            interest=68,
            vibe=_copy(language, "Approachable", "다가가기 쉬움"),
            profile=_profile(language),
        )
        return self.provider_gateway.complete(action="profile_coach", request=request, fallback=fallback)

    def goal_coach(self, request: FlirtistGoalRequest) -> FlirtistResponse:
        language = _language(request)
        fallback = _response(
            language=language,
            locale=_locale(language, request.locale),
            summary=_copy(language, "Move forward with a concrete, low-pressure option.", "구체적이지만 부담 낮은 선택지로 다음 행동을 제안하세요."),
            interest=70,
            vibe=_copy(language, "Promising but pace-sensitive", "가능성은 있지만 속도 조절 필요"),
            action=_copy(language, "Offer two simple times and leave room for no.", "두 가지 가벼운 시간을 제안하고 거절 여지를 남기세요."),
        )
        return self.provider_gateway.complete(action="goal_coach", request=request, fallback=fallback)

    def ocr_chat(self, request: FlirtistOCRRequest) -> FlirtistResponse:
        language = _language(request)
        source = request.text or _copy(language, "Screenshot text mock extracted.", "스크린샷 텍스트를 모의 추출했습니다.")
        fallback = _response(
            language=language,
            locale=_locale(language, request.locale),
            summary=_copy(language, f"Structured chat text: {source[:120]}", f"구조화된 대화 텍스트: {source[:80]}"),
            interest=62,
            vibe=_copy(language, "Ready for analysis", "분석 준비 완료"),
        )
        return self.provider_gateway.complete(action="ocr_chat", request=request, fallback=fallback)


def _language(request: LocaleRequest) -> str:
    if request.language in {"en", "ko"}:
        return request.language
    return "ko" if request.locale.lower().startswith("ko") else "en"


def _locale(language: str, locale: str) -> str:
    return "ko-KR" if language == "ko" else (locale if locale.startswith("en") else "en-US")


def _combined_messages(messages) -> str:
    return " ".join(message.text for message in messages)


def _risk_flags(text: str) -> list[str]:
    lowered = text.lower()
    flags: list[str] = []
    if "15" in lowered or "minor" in lowered or "underage" in lowered:
        flags.append("minor")
    if "sexual" in lowered or "nude" in lowered:
        flags.append("sexual_explicit")
    if "pressure" in lowered or "make her" in lowered or "make him" in lowered:
        flags.append("coercion")
    if "stalk" in lowered or "track" in lowered:
        flags.append("stalking")
    return flags


def _copy(language: str, en: str, ko: str) -> str:
    return ko if language == "ko" else en


def _replies(language: str) -> list[str]:
    if language == "ko":
        return ["링크 고마워요. 제 취향일 것 같아서 기대돼요.", "좋아요. 보고 나서 근처에서 가볍게 커피 한잔할까요?"]
    return ["Send it over. If it looks as good as you made it sound, we should check it out.", "I’m in. You clearly have better exhibition taste than my algorithm."]


def _why(language: str) -> list[str]:
    if language == "ko":
        return ["상대의 공유를 인정하고 과하지 않게 관심을 표현합니다.", "구체적인 다음 행동이 있어 답장하기 쉽습니다."]
    return ["It validates their suggestion without sounding over-eager.", "It creates a specific, low-pressure next step."]


def _pickup_lines(language: str, situation: str) -> list[str]:
    situation_hint = situation.rstrip(".!?")[:72]
    if language == "ko":
        return [
            f"{situation_hint} 상황이면, 당신 취향부터 물어보는 게 제일 자연스러울 것 같아요.",
            "혹시 이 근처에서 제일 괜찮은 커피를 아는 사람처럼 보이는데, 맞나요?",
            "말 걸 타이밍을 재고 있었는데, 지금이 제일 자연스러운 것 같아서요.",
            "오늘 제 목표는 좋은 대화 하나 만드는 건데, 당신이 도와줄래요?",
            "이 책보다 당신 취향이 더 궁금해졌어요.",
            "잠깐만요, 웃는 분위기가 좋아서 인사 안 하면 후회할 것 같았어요.",
            "여기 처음 왔는데, 당신이 고른 메뉴가 정답 같아 보여요.",
            "혹시 짧은 대화 하나 나눠도 괜찮을까요? 부담은 두고 왔어요.",
            "당신 분위기가 좋아서, 이름 정도는 알고 가고 싶었어요.",
            "지금 대화 시작하면 어색할까요, 아니면 꽤 괜찮은 우연일까요?",
            "내가 좋은 질문을 하나 찾고 있었는데, 당신 취향부터 물어봐도 될까요?",
            "오늘 제일 괜찮은 선택이 이쪽으로 인사하는 거였으면 좋겠네요.",
            "혹시 이 순간을 자연스럽게 만드는 능력도 있으세요?",
            "당신에게 어울리는 첫마디를 고르다가 그냥 솔직하게 왔어요.",
            "여기서 제일 흥미로운 건 메뉴가 아니라 당신인 것 같아요.",
            "짧게만 말할게요. 당신이 눈에 띄어서 인사하고 싶었어요.",
            "내가 방금 좋은 핑계를 잃어버렸는데, 그냥 인사해도 될까요?",
            "혹시 좋은 대화 좋아하세요? 제가 지금 하나 시작해보려는데요.",
            "처음 보는 사람한테 말 걸기 어렵지만, 당신은 예외로 하고 싶었어요.",
            "오늘 우연을 하나 만들고 싶은데, 같이 해볼래요?",
        ]
    return [
        f"Since this is about {situation_hint}, I have to ask what caught your eye first.",
        "I was looking for a smooth opener, but honestly, hi felt better.",
        "This place is nice, but your taste might be the part I actually want a recommendation on.",
        "Quick question: are you always this easy to notice, or did I pick a lucky day?",
        "I was going to pretend I needed directions, but I mostly just wanted to say hi.",
        "You seem like someone who could make a short conversation worth remembering.",
        "I need an unbiased opinion: is starting a conversation right now charming or mildly brave?",
        "I was trying to think of the perfect line, then decided a real hello was better.",
        "If your vibe had a review, I would at least give it five stars for making me curious.",
        "I am not usually this direct, but you made not saying hello feel like the weirder choice.",
        "You look like you have a good answer to a simple question: coffee or dessert first?",
        "I had a whole line ready, but your smile made it retire early.",
        "Would it be too forward to ask what made you choose this spot?",
        "I am collecting good moments today. This felt like one worth starting.",
        "You seem interesting enough that I am willing to risk a slightly awkward hello.",
        "If I only get one line, I will spend it on this: I wanted to meet you.",
        "You caught my attention in a way that made my phone less interesting.",
        "I am trying to be less mysterious and more honest, so hi, I think you are cute.",
        "This could be nothing, or it could be a good story. Want to find out?",
        "I promise this is my least rehearsed line: I just wanted to talk to you.",
    ]


def _profile(language: str) -> list[str]:
    if language == "ko":
        return ["첫 문장에 취향을 하나 더 구체적으로 넣기", "사진 설명은 활동과 분위기 중심으로 정리", "첫 DM으로 이어질 질문 포인트 남기기"]
    return ["Make the first line more specific", "Use activity-led photo captions", "Leave one easy first-message hook"]


def _response(
    *,
    language: str,
    locale: str,
    summary: str,
    interest: int,
    vibe: str,
    risks: list[str] | None = None,
    improved: str | None = None,
    action: str | None = None,
    profile: list[str] | None = None,
) -> FlirtistResponse:
    return FlirtistResponse(
        summary=summary,
        interestScore=interest,
        vibe=vibe,
        riskFlags=risks or [],
        nextMove=_copy(language, "Reply with a specific callback and one easy next step.", "구체적인 콜백과 가벼운 다음 행동을 함께 보내세요."),
        recommendedAction=action or _copy(language, "Send a warm, low-pressure reply.", "부담 낮은 따뜻한 답장을 보내세요."),
        replies=_replies(language),
        whyItWorks=_why(language),
        improvedDraft=improved
        if improved is not None
        else _copy(language, "That sounds fun. Are you free one evening this week?", "좋아요. 이번 주 중 편한 날에 가볍게 볼까요?"),
        profileSuggestions=profile or _profile(language),
        confidenceScore=0.82,
        language=language,
        locale=locale,
        aiObviousness=14,
        pressure=18 if not risks else 72,
        replyLikelihood=84 if not risks else 20,
    )
