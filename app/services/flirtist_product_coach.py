from __future__ import annotations

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import FlirtistCoachChatRequest


def coach_answer(language: FlirtistLanguage, request: FlirtistCoachChatRequest) -> str:
    message = _normalized(request.message)
    context_hint = _context_hint(language, request.context)
    if language == "ko":
        if _mentions(message, ("커피", "카페", "coffee", "말 걸", "approach")):
            return (
                f"{context_hint}커피숍에서는 멀리서 크게 치고 들어가기보다, 상황을 한 번 공유하는 낮은 압도의 한마디가 좋아요. "
                "예를 들면 '혹시 여기 자주 오세요? 메뉴 고르는데 실패 중이라 추천받고 싶어서요'처럼 선택권을 주세요."
            )
        if _mentions(message, ("느려", "답장", "읽씹", "reply", "slow")):
            return (
                f"{context_hint}답장이 느릴 때는 확인받으려는 메시지를 추가하지 않는 게 좋아요. "
                "마지막 말에 가볍게 공감하고, 상대가 부담 없이 다시 들어올 수 있는 질문 하나만 남겨두세요."
            )
        if _mentions(message, ("첫 데이트", "데이트 후", "after date", "first date")):
            return (
                f"{context_hint}첫 데이트 후에는 평가보다 구체적인 순간 하나를 짚는 게 자연스러워요. "
                "'오늘 그 얘기 계속 생각나더라. 조심히 들어갔어?'처럼 여운과 배려를 같이 보내세요."
            )
        return (
            f"{context_hint}지금은 정답 문장보다 상대가 답하기 쉬운 구조가 중요해요. "
            "상대 말 한 부분을 짧게 받아주고, 질문은 하나만, 다음 행동은 선택권 있게 열어두세요."
        )
    if _mentions(message, ("coffee", "cafe", "approach", "line")):
        return (
            f"{context_hint}In a coffee shop, start with the shared situation instead of a cold compliment. "
            "Try one low-pressure opener like, 'I am losing the menu battle. Is there anything here you would actually recommend?'"
        )
    if _mentions(message, ("slow", "reply", "text back", "ghost")):
        return (
            f"{context_hint}With slow replies, do not chase the response window. "
            "Acknowledge the last thing they gave you, ask one easy question, then let the message breathe."
        )
    if _mentions(message, ("first date", "after date", "date went")):
        return (
            f"{context_hint}After a first date, reference one specific moment instead of giving a big review. "
            "Something like, 'That story about your friend still has me laughing. Did you get home okay?' feels warm and easy."
        )
    return (
        f"{context_hint}Good moment to slow the play down. Reflect one specific detail, keep the ask to one question, "
        "and make the next step feel optional rather than like a pitch."
    )


def coach_suggestions(language: FlirtistLanguage, request: FlirtistCoachChatRequest) -> list[str]:
    message = _normalized(request.message)
    if language == "ko":
        if _mentions(message, ("커피", "카페", "말 걸")):
            return ["정확히 보낼 첫마디 만들어줘", "상대가 웃으면 다음엔?", "부담 없는 버전으로 바꿔줘"]
        if _mentions(message, ("첫 데이트", "데이트 후")):
            return ["짧은 후속 문자 써줘", "더 플러팅하게", "너무 들이대지 않게"]
        return ["이 상황에서 보낼 문장 만들어줘", "상대 반응별로 연습", "더 자연스럽게 바꿔줘"]
    if _mentions(message, ("coffee", "cafe", "approach")):
        return ["Write the exact opener", "Practice if she smiles", "Make it more casual"]
    if _mentions(message, ("first date", "after date")):
        return ["Write the follow-up text", "Make it flirtier", "Make it lower pressure"]
    return ["Write the exact message", "Practice possible replies", "Make it more natural"]


def _context_hint(language: FlirtistLanguage, context: str | None) -> str:
    if not context:
        return ""
    return "저장한 내 콘텍스트를 반영하면, " if language == "ko" else "Using your saved context, "


def _mentions(message: str, needles: tuple[str, ...]) -> bool:
    return any(needle in message for needle in needles)


def _normalized(value: str) -> str:
    return value.strip().lower()
