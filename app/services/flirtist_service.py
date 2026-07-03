from __future__ import annotations

from typing import Protocol

from app.schemas.flirtist import (
    FlirtistChatRequest,
    FlirtistDraftRequest,
    FlirtistGenerateRequest,
    FlirtistGoalRequest,
    FlirtistLanguage,
    FlirtistOCRRequest,
    FlirtistPickupLinesRequest,
    FlirtistPickupLinesResponse,
    FlirtistProfileRequest,
    FlirtistResponse,
    default_locale_for_language,
    normalize_flirtist_language,
)
from app.services.flirtist_config import FlirtistAIConfig, load_flirtist_ai_config
from app.services.flirtist_pickup_lines import curate_pickup_lines, pickup_lines
from app.services.flirtist_provider import FlirtistAIProviderGateway, FlirtistProviderTransport


class LocaleRequest(Protocol):
    language: FlirtistLanguage | None
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
            lines=pickup_lines(language, request.situation),
            language=language,
            locale=_locale(language, request.locale),
        )
        response = self.provider_gateway.complete_pickup_lines(request=request, fallback=fallback)
        return response.model_copy(
            update={
                "language": language,
                "locale": _locale(language, request.locale),
                "lines": curate_pickup_lines(response.lines, language, request.situation),
            }
        )

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


def _language(request: LocaleRequest) -> FlirtistLanguage:
    return normalize_flirtist_language(request.language, request.locale)


def _locale(language: FlirtistLanguage, locale: str) -> str:
    return default_locale_for_language(language, locale)


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
