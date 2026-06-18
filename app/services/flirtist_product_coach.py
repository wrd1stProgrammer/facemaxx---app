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
        if _mentions(message, ("선톡", "먼저 연락", "먼저 톡")):
            return (
                f"{context_hint}선톡이 없다는 사실만으로 관심 없다고 단정하기보다, 상대가 쉽게 답할 수 있는 연결고리 하나가 좋아요. "
                "'문득 그 얘기 생각났어. 오늘은 좀 나아졌어?'처럼 부담 낮은 확인을 한 번만 보내고 기다려보세요."
            )
        if _mentions(message, ("소개팅", "만나기 전", "첫 만남")):
            return (
                f"{context_hint}소개팅 전 메시지는 재미를 증명하기보다 약속을 편하게 만드는 역할이면 충분해요. "
                "'내일 7시 맞지? 가는 길 조심히 와. 메뉴는 같이 골라보자'처럼 확인, 배려, 작은 여지를 담아주세요."
            )
        if _mentions(message, ("첫 데이트", "데이트 후", "after date", "first date")):
            return (
                f"{context_hint}첫 데이트 후에는 평가보다 구체적인 순간 하나를 짚는 게 자연스러워요. "
                "'오늘 그 얘기 계속 생각나더라. 조심히 들어갔어?'처럼 여운과 배려를 같이 보내세요."
            )
        return _ko_contextual_fallback_answer(context_hint, message)
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
        if _mentions(message, ("선톡", "먼저 연락", "먼저 톡")):
            return ["선톡 보낼 문장 만들어줘", "안 부담스럽게 바꿔줘", "보낸 뒤 대처 연습"]
        if _mentions(message, ("소개팅", "만나기 전", "첫 만남")):
            return ["소개팅 전 문자 써줘", "더 설레게 바꿔줘", "약속 확인용으로 짧게"]
        if _mentions(message, ("첫 데이트", "데이트 후")):
            return ["짧은 후속 문자 써줘", "더 플러팅하게", "너무 들이대지 않게"]
        return _ko_contextual_fallback_suggestions(message)
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


def _ko_contextual_fallback_answer(context_hint: str, message: str) -> str:
    topic = _ko_topic(message)
    guidance = _ko_fallback_guidance(message)
    return (
        f"{context_hint}{topic} 상황에서는 한 번에 관계를 밀어붙이기보다, 상대가 편하게 선택할 수 있는 작은 다음 행동이 좋아요. "
        f"{guidance} 마지막에는 질문 하나만 남기고, 답이 늦어도 추가 확인 메시지는 보내지 마세요."
    )


def _ko_contextual_fallback_suggestions(message: str) -> list[str]:
    topic = _ko_topic(message)
    return [
        f"{topic} 문장 3개 만들어줘",
        f"{topic} 상대 반응별로 연습",
        f"{topic} 더 담백하게 바꿔줘",
    ]


def _ko_topic(message: str) -> str:
    if _mentions(message, ("프로필", "사진", "셀카", "칭찬")):
        return "프로필/사진 칭찬"
    if _mentions(message, ("연락", "빈도", "카톡", "톡 텀", "텀")):
        return "연락 빈도 조율"
    if _mentions(message, ("고백", "타이밍", "사귀", "관계 확정")):
        return "고백 타이밍"
    if _mentions(message, ("플러팅", "부담", "연습", "장난")):
        return "부담 낮은 플러팅"
    if _mentions(message, ("약속", "만남", "일정", "시간")):
        return "만남 제안"

    clipped = message.strip(" ?!.。！？")
    if not clipped:
        return "이 상황"
    return f"'{clipped[:18]}'"


def _ko_fallback_guidance(message: str) -> str:
    if _mentions(message, ("프로필", "사진", "셀카", "칭찬")):
        return "외모 평가처럼 들리지 않게 사진 속 선택, 분위기, 취향을 짚고 짧게 물어보세요."
    if _mentions(message, ("연락", "빈도", "카톡", "톡 텀", "텀")):
        return "내 기준을 설명하기보다 서로 편한 속도를 확인하는 문장으로 시작하세요."
    if _mentions(message, ("고백", "타이밍", "사귀", "관계 확정")):
        return "고백 문장부터 준비하기 전에 최근 만남의 온도와 다음 약속 의지를 먼저 확인하세요."
    if _mentions(message, ("플러팅", "부담", "연습", "장난")):
        return "칭찬 하나에 가벼운 질문 하나만 붙여서 장난스럽지만 빠져나갈 여지를 주세요."
    if _mentions(message, ("약속", "만남", "일정", "시간")):
        return "시간을 강하게 고정하기보다 두 가지 선택지를 주면 상대가 답하기 쉽습니다."
    return "상대가 이미 준 단서 하나를 다시 받아주고, 다음 행동은 작고 구체적으로 열어두세요."
