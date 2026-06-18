from __future__ import annotations

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import FlirtistPreviewMessage
from app.services.flirtist_product_reply_context import ReplyContext, ReplyScenario


def reply_context_from_messages(
    language: FlirtistLanguage,
    messages: list[FlirtistPreviewMessage],
) -> ReplyContext:
    last_them_index = _last_role_index(messages, "them")
    last_them = messages[last_them_index].text if last_them_index is not None else _last_non_system_text(messages)
    anchor = _anchor_text(language, messages, last_them_index, last_them)
    return ReplyContext(
        scenario=_scenario(language, anchor),
        topic=_topic(language, anchor),
        last_them=last_them,
    )


def _anchor_text(
    language: FlirtistLanguage,
    messages: list[FlirtistPreviewMessage],
    last_them_index: int | None,
    last_them: str,
) -> str:
    if last_them_index is None:
        return last_them
    if not _is_short_positive_reply(language, last_them):
        return last_them
    for message in reversed(messages[:last_them_index]):
        if message.role == "me" and _looks_like_plan(language, message.text):
            return f"{message.text} {last_them}"
    return last_them


def _last_role_index(messages: list[FlirtistPreviewMessage], role: str) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == role:
            return index
    return None


def _last_non_system_text(messages: list[FlirtistPreviewMessage]) -> str:
    return next((message.text for message in reversed(messages) if message.role != "system"), "")


def _is_short_positive_reply(language: FlirtistLanguage, text: str) -> bool:
    lowered = text.lower().strip()
    if len(lowered) > 28:
        return False
    if language == "ko":
        return _contains_any(lowered, ("응", "웅", "좋", "조아", "조아네", "그래", "오키", "ㅇㅋ"))
    return _contains_any(lowered, ("yes", "yeah", "yep", "sure", "sounds good", "ok", "okay", "love that"))


def _looks_like_plan(language: FlirtistLanguage, text: str) -> bool:
    lowered = text.lower()
    if language == "ko":
        return _contains_any(lowered, ("만나", "보자", "밥", "커피", "맛난", "맛있는", "사줄", "연락", "광주", "서울", "부산", "데이트"))
    return _contains_any(lowered, ("meet", "see you", "coffee", "dinner", "food", "text me", "message me", "come to", "date"))


def _scenario(language: FlirtistLanguage, text: str) -> ReplyScenario:
    lowered = text.lower()
    if language == "ko":
        if _contains_any(lowered, ("붙", "합격", "성공", "해냈", "드디어", "끝났다", "축하")):
            return "celebration"
        if _contains_any(lowered, ("회사", "퇴근", "피곤", "힘들", "정신", "야근", "빡세", "지쳤")):
            return "fatigue"
        if _contains_any(lowered, ("커피", "밥", "만나", "보자", "데이트", "술", "맛난", "맛있는", "사줄", "연락", "광주")):
            return "plans"
        if _contains_any(lowered, ("보고 싶", "보고싶", "좋아", "설레", "귀엽", "생각났", "생각났어")):
            return "affection"
        if _contains_any(lowered, ("영화", "드라마", "노래", "봤", "재밌", "맛있", "좋았", "별로")):
            return "reaction"
        return "generic"
    if _contains_any(lowered, ("passed", "accepted", "finally", "done", "won", "celebrate", "congrats")):
        return "celebration"
    if _contains_any(lowered, ("work", "tired", "chaotic", "exhausted", "rough", "busy", "drained")):
        return "fatigue"
    if _contains_any(lowered, ("coffee", "dinner", "date", "meet", "movie", "drinks", "text me", "come to")):
        return "plans"
    if _contains_any(lowered, ("miss", "like you", "cute", "thinking of you", "thought of you", "on my mind", "crossed my mind")):
        return "affection"
    if _contains_any(lowered, ("movie", "watched", "saw", "show", "song", "fun", "interesting", "liked", "loved")):
        return "reaction"
    return "generic"


def _topic(language: FlirtistLanguage, text: str) -> str:
    lowered = text.lower()
    if language == "ko":
        if "광주" in lowered:
            return "광주에서 만나는 약속"
        if "회계" in lowered and "시험" in lowered:
            return "회계 시험"
        if "시험" in lowered:
            return "시험"
        if "영화" in lowered:
            return "그 영화"
        if "드라마" in lowered:
            return "그 드라마"
        if "노래" in lowered:
            return "그 노래"
        if "생각" in lowered:
            return "생각난 순간"
        if "회사" in lowered or "퇴근" in lowered:
            return "오늘 하루"
    else:
        if "accounting exam" in lowered:
            return "your accounting exam"
        if "exam" in lowered:
            return "your exam"
        if "movie" in lowered or "watched" in lowered or "saw" in lowered:
            return "the movie"
        if "show" in lowered:
            return "the show"
        if "song" in lowered:
            return "the song"
        if "thought of you" in lowered or "on my mind" in lowered or "crossed my mind" in lowered:
            return "that moment"
        if "work" in lowered:
            return "your day"
    clipped = " ".join(text.split())[:36]
    return clipped or "그 얘기"


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
