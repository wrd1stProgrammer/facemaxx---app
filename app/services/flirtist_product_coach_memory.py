from __future__ import annotations

from typing import Final

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import FlirtistCoachChatRequest
from app.services.flirtist_product_coach_ko import ko_intent

MAX_MEMORY_CHARS: Final = 900
MAX_MEMORY_BULLETS: Final = 6
MEMORY_MARKER: Final = "Coach memory:"


def coach_memory_summary(language: FlirtistLanguage, request: FlirtistCoachChatRequest) -> str | None:
    bullets = _memory_bullets_from_context(request.context)
    for message in request.history:
        if message.role != "user":
            continue
        _append_unique(bullets, _bullet_for_message(language, message.text))
    _append_unique(bullets, _bullet_for_message(language, request.message))
    if not bullets:
        return None
    return "\n".join(bullets[-MAX_MEMORY_BULLETS:])[:MAX_MEMORY_CHARS].strip()


def coach_memory_source_text(context: str | None) -> str:
    return " ".join(line.lstrip("- ").strip() for line in _memory_bullets_from_context(context))


def _memory_bullets_from_context(context: str | None) -> list[str]:
    if not context:
        return []
    lines = context.splitlines()
    marker_index = next((index for index, line in enumerate(lines) if line.strip() == MEMORY_MARKER), None)
    if marker_index is None:
        return []
    bullets: list[str] = []
    for line in lines[marker_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("-"):
            break
        _append_unique(bullets, stripped)
    return bullets


def _bullet_for_message(language: FlirtistLanguage, text: str) -> str | None:
    message = _normalized(text)
    if not message or _is_generic_followup(message):
        return None
    if language == "ko":
        return _ko_bullet(message)
    return _en_bullet(message)


def _ko_bullet(message: str) -> str | None:
    match ko_intent(message):
        case "old_crush_drinks":
            return "- 2년 전 썸/오랜만인 상대에게 술 한잔 제안하려 함."
        case "bar_approach":
            return "- 헌팅포차나 술집에서 낯선 상대에게 자연스럽게 첫마디를 걸고 싶어 함."
        case "coffee_approach":
            return "- 카페나 커피숍에서 부담 없이 말을 거는 상황을 연습 중."
        case "slow_reply":
            return "- 상대 답장이 느린 상황에서 압박 없이 이어가는 법을 고민 중."
        case "first_contact":
            return "- 먼저 연락할 명분과 부담 낮은 선톡 문장을 찾는 중."
        case "blind_date":
            return "- 소개팅 전 약속 확인과 가벼운 설렘을 주는 문장을 고민 중."
        case "after_date":
            return "- 첫 데이트 후 여운을 살린 후속 문자를 고민 중."
        case "profile_compliment":
            return "- 프로필/사진을 외모 평가처럼 보이지 않게 칭찬하고 싶어 함."
        case "texting_pace":
            return "- 연락 빈도와 카톡 텀을 부담 없이 조율하고 싶어 함."
        case "confession_timing":
            return "- 고백 타이밍과 관계 확정 전 신호를 확인하고 싶어 함."
        case "low_pressure_flirt":
            return "- 선 넘지 않는 가벼운 플러팅 문장을 연습 중."
        case "meetup":
            return "- 만남이나 약속 제안을 답하기 쉽게 만들고 싶어 함."
        case "generic":
            return f"- 최근 고민: {message[:64]}"
        case unreachable:
            assert_never(unreachable)


def _en_bullet(message: str) -> str | None:
    if _contains_any(message, ("coffee", "cafe", "approach")):
        return "- Practicing a low-pressure opener in a coffee shop or cafe."
    if _contains_any(message, ("slow", "reply", "text back", "ghost")):
        return "- Wants to handle slow replies without sounding needy."
    if _contains_any(message, ("first date", "after date")):
        return "- Wants a warm follow-up after a first date."
    if _contains_any(message, ("ask her out", "ask him out", "date", "drinks", "meet")):
        return "- Wants to ask someone out while keeping the pressure low."
    return f"- Current coaching topic: {message[:72]}"


def _append_unique(bullets: list[str], bullet: str | None) -> None:
    if bullet is None:
        return
    normalized = _compact(bullet)
    if any(_compact(existing) == normalized for existing in bullets):
        return
    bullets.append(bullet)


def _is_generic_followup(message: str) -> bool:
    return _compact(message) in {
        "그니까뭐라보낼까",
        "그래서뭐라보내",
        "그래서뭐라고해",
        "뭐라보내",
        "뭐라고보내",
        "문장써줘",
        "그냥써줘",
        "whatdoisay",
        "writethetext",
        "exactmessage",
    }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _normalized(value: str) -> str:
    return value.strip().lower()


def _compact(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())
