from __future__ import annotations

from typing import Final

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import FlirtistCoachChatRequest
from app.schemas.flirtist_product import FlirtistCoachChatResponse
from app.schemas.flirtist_product import FlirtistCoachMessage
from app.services.flirtist_product_coach_memory import coach_memory_source_text
from app.services.flirtist_product_coach_ko import ko_answer, ko_intent, ko_suggestions

LOW_VALUE_COACH_PHRASES: Final = (
    "한 번에 관계를 밀어붙이기보다",
    "상대가 편하게 선택할 수 있는 작은 다음 행동",
    "작은 다음 행동이 좋아요",
    "마지막에는 질문 하나만 남기고",
    "추가 확인 메시지는 보내지 마세요",
    "good moment to slow the play down",
    "reflect one specific detail",
    "make the next step feel optional",
)


def coach_answer(language: FlirtistLanguage, request: FlirtistCoachChatRequest) -> str:
    message = _effective_message(request)
    context_hint = _context_hint(language, request.context)
    if language == "ko":
        return ko_answer(context_hint, ko_intent(message), message)
    return _en_answer(context_hint, message)


def coach_suggestions(language: FlirtistLanguage, request: FlirtistCoachChatRequest) -> list[str]:
    message = _effective_message(request)
    if language == "ko":
        return ko_suggestions(ko_intent(message))
    return _en_suggestions(message)


def repair_coach_response(
    language: FlirtistLanguage,
    request: FlirtistCoachChatRequest,
    response: FlirtistCoachChatResponse,
) -> FlirtistCoachChatResponse:
    if not _is_low_value_coach_text(request, response.message.text):
        return response
    return response.model_copy(
        update={
            "message": FlirtistCoachMessage(role="assistant", text=coach_answer(language, request)),
            "suggestions": coach_suggestions(language, request),
        }
    )


def _effective_message(request: FlirtistCoachChatRequest) -> str:
    message = _normalized(request.message)
    if not _is_generic_followup(message):
        return message
    for item in reversed(request.history):
        if item.role != "user":
            continue
        candidate = _normalized(item.text)
        if candidate and not _is_generic_followup(candidate):
            return candidate
    memory = _normalized(coach_memory_source_text(request.context))
    if memory:
        return memory
    return message


def _context_hint(language: FlirtistLanguage, context: str | None) -> str:
    if not context:
        return ""
    return "네 상황까지 감안하면, " if language == "ko" else "Using your saved context, "


def _mentions(message: str, needles: tuple[str, ...]) -> bool:
    return any(needle in message for needle in needles)


def _normalized(value: str) -> str:
    return value.strip().lower()


def _is_generic_followup(message: str) -> bool:
    compact = _compact(message)
    return compact in {
        "그니까뭐라보낼까",
        "그래서뭐라보내",
        "그래서뭐라고해",
        "뭐라보내",
        "뭐라고보내",
        "문장써줘",
        "그냥써줘",
        "exactmessage",
        "whatdoisay",
        "writethetext",
    }


def _en_answer(context_hint: str, message: str) -> str:
    if _mentions(message, ("coffee", "cafe", "approach", "line")):
        return (
            f"{context_hint}In a coffee shop, use the room instead of a cold compliment. "
            "Try: \"I'm losing the menu battle. Is there anything here you'd actually recommend?\" "
            "If they keep it short, thank them and leave it there; if they smile, continue with names."
        )
    if _mentions(message, ("slow", "reply", "text back", "ghost")):
        return (
            f"{context_hint}Do not chase the slow reply. Send one relaxed bridge like, "
            "\"No rush, your work story sounded intense. Tell me the good part when you get a minute.\""
        )
    if _mentions(message, ("first date", "after date", "date went")):
        return (
            f"{context_hint}After a first date, mention one real moment instead of reviewing the whole night. "
            "Try: \"That story about your friend still has me laughing. Did you get home okay?\""
        )
    return (
        f"{context_hint}Give them one easy hook, not a whole speech. Try: "
        "\"That made me curious. Tell me the short version when you get a second.\""
    )


def _en_suggestions(message: str) -> list[str]:
    if _mentions(message, ("coffee", "cafe", "approach")):
        return ["Write the exact opener", "Practice if she smiles", "Make it more casual"]
    if _mentions(message, ("first date", "after date")):
        return ["Write the follow-up text", "Make it flirtier", "Make it lower pressure"]
    return ["Write the exact message", "Practice possible replies", "Make it more natural"]


def _is_low_value_coach_text(request: FlirtistCoachChatRequest, text: str) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in LOW_VALUE_COACH_PHRASES):
        return True
    user_messages = [request.message, _effective_message(request)]
    user_messages.extend(item.text for item in request.history if item.role == "user")
    compact_text = _compact(lowered)
    return any(len(_compact(message)) >= 8 and _compact(message) in compact_text for message in user_messages)


def _compact(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())
