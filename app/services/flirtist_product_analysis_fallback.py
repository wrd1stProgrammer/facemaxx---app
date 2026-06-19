from __future__ import annotations

import re
from collections import Counter
from typing import Final

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import (
    FlirtistAnalysisCard,
    FlirtistInterestBreakdown,
    FlirtistMessageCount,
    FlirtistPreviewMessage,
)
from app.services.flirtist_product_transcript import is_ui_noise_text

_WORD_RE: Final[re.Pattern[str]] = re.compile(r"[가-힣A-Za-z0-9]+")
_KO_STOPWORDS: Final[set[str]] = {
    "그냥",
    "오늘",
    "내일",
    "어제",
    "진짜",
    "완전",
    "약간",
    "조금",
    "나",
    "너",
    "나는",
    "너는",
    "내가",
    "네가",
    "상대",
    "뭐해",
    "머해",
    "오옹",
    "웅",
    "응",
    "그래",
    "ㅋㅋ",
    "ㅎㅎ",
    "ㅠㅠ",
    "메시지",
    "채팅",
}
_EN_STOPWORDS: Final[set[str]] = {
    "the",
    "and",
    "you",
    "your",
    "me",
    "mine",
    "them",
    "that",
    "this",
    "with",
    "just",
    "really",
    "today",
    "tonight",
    "message",
}


def analysis_card(language: FlirtistLanguage, messages: list[FlirtistPreviewMessage]) -> FlirtistAnalysisCard:
    meaningful_messages = [message for message in messages if message.role in {"me", "them"} and not is_ui_noise_text(message.text)]
    my_messages = [message.text for message in meaningful_messages if message.role == "me"]
    them_messages = [message.text for message in meaningful_messages if message.role == "them"]
    counts = FlirtistMessageCount(you=max(len(my_messages), 1), them=max(len(them_messages), 1))
    you_interest, them_interest = _interest_scores(language, my_messages, them_messages)
    return FlirtistAnalysisCard(
        title="대화 분석" if language == "ko" else "Chat Wrapped",
        messageCount=counts,
        interestLevel=FlirtistInterestBreakdown(you=you_interest, them=them_interest),
        meaningfulWordsYou=_keywords(language, my_messages),
        meaningfulWordsThem=_keywords(language, them_messages),
        redFlags=_red_flags(language, my_messages, them_messages),
        greenFlags=_green_flags(language, my_messages, them_messages),
        attachmentYou=_attachment(language, "me", my_messages),
        attachmentThem=_attachment(language, "them", them_messages),
        compatibilityScore=_compatibility_score(you_interest, them_interest, counts),
    )


def _interest_scores(
    language: FlirtistLanguage,
    my_messages: list[str],
    them_messages: list[str],
) -> tuple[int, int]:
    you = 48 + min(len(my_messages) * 4, 24)
    them = 48 + min(len(them_messages) * 4, 24)
    you += _signal_score(language, " ".join(my_messages))
    them += _signal_score(language, " ".join(them_messages))
    return min(92, max(35, you)), min(92, max(35, them))


def _signal_score(language: FlirtistLanguage, text: str) -> int:
    lowered = text.lower()
    if language == "ko":
        signals = ("좋", "조아", "보고", "만나", "맛", "사줄", "연락", "기다", "응원", "ㅋㅋ", "ㅎㅎ", "하트")
    else:
        signals = ("yes", "yeah", "meet", "coffee", "dinner", "miss", "like", "wait", "fun", "haha", "heart")
    return min(sum(6 for signal in signals if signal in lowered), 24)


def _keywords(language: FlirtistLanguage, texts: list[str]) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        for word in _WORD_RE.findall(text):
            normalized = _normalize_word(language, word)
            if normalized:
                counter[normalized] += 1
    ranked = [word for word, _ in counter.most_common(6)]
    return ranked or (["맥락 부족"] if language == "ko" else ["not enough context"])


def _normalize_word(language: FlirtistLanguage, raw_word: str) -> str | None:
    word = raw_word.strip().lower()
    if language == "ko":
        word = word.strip("은는이가을를도만에에서으로로랑과와야아")
        if len(word) < 2 or word in _KO_STOPWORDS:
            return None
        return word
    if len(word) < 3 or word in _EN_STOPWORDS:
        return None
    return word


def _red_flags(
    language: FlirtistLanguage,
    my_messages: list[str],
    them_messages: list[str],
) -> list[str]:
    joined = " ".join(my_messages + them_messages).lower()
    flags: list[str] = []
    if language == "ko":
        if len(them_messages) <= 1:
            flags.append("상대 메시지가 적어 확신은 낮음")
        if any(token in joined for token in ("?", "뭐라", "왜", "갑자기")):
            flags.append("질문 의도가 약간 열려 있음")
        return flags[:3] or ["큰 위험 신호는 적음"]
    if len(them_messages) <= 1:
        flags.append("Limited replies from them")
    if any(token in joined for token in ("why", "what happened", "?")):
        flags.append("Intent still needs a little context")
    return flags[:3] or ["No major red flags"]


def _green_flags(
    language: FlirtistLanguage,
    my_messages: list[str],
    them_messages: list[str],
) -> list[str]:
    joined_them = " ".join(them_messages).lower()
    joined_all = " ".join(my_messages + them_messages).lower()
    flags: list[str] = []
    if language == "ko":
        if any(token in joined_them for token in ("웅", "응", "좋", "조아", "ㅋㅋ", "ㅎㅎ")):
            flags.append("상대가 긍정적으로 받아줌")
        if any(token in joined_all for token in ("만나", "밥", "맛", "연락", "기다", "광주", "카페", "술")):
            flags.append("약속이나 장소 맥락이 살아 있음")
        if len(them_messages) >= 2:
            flags.append("상대가 대화를 이어줌")
        return flags[:3] or ["대화를 이어갈 여지는 있음"]
    if any(token in joined_them for token in ("yes", "yeah", "sure", "haha", "love")):
        flags.append("They respond positively")
    if any(token in joined_all for token in ("meet", "coffee", "dinner", "drinks", "text")):
        flags.append("There is a concrete next-step hook")
    if len(them_messages) >= 2:
        flags.append("They keep the thread alive")
    return flags[:3] or ["There is room to continue"]


def _attachment(language: FlirtistLanguage, role: str, texts: list[str]) -> str:
    joined = " ".join(texts).lower()
    if language == "ko":
        if role == "me":
            if any(token in joined for token in ("만나", "사줄", "연락", "갈게")):
                return "가볍게 리드하는 편"
            return "편하게 반응하는 편"
        if any(token in joined for token in ("웅", "응", "조아", "좋")):
            return "수용적으로 받아주는 편"
        return "신중하게 이어가는 편"
    if role == "me":
        if any(token in joined for token in ("meet", "buy", "text", "come")):
            return "Lightly leading"
        return "Easygoing"
    if any(token in joined for token in ("yes", "yeah", "sure", "good")):
        return "Receptive"
    return "Cautious"


def _compatibility_score(
    you_interest: int,
    them_interest: int,
    counts: FlirtistMessageCount,
) -> int:
    balance_gap = abs(counts.you - counts.them)
    balance_bonus = max(0, 12 - balance_gap * 3)
    return min(94, max(42, int((you_interest + them_interest) / 2) + balance_bonus))
