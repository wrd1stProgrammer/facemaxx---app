from __future__ import annotations

from itertools import chain

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import (
    FlirtistPreviewMessage,
    FlirtistReplyCoaching,
    FlirtistReplyOption,
    FlirtistReplyPack,
)
from app.services.flirtist_product_reply_fallback import reply_coaching
from app.services.flirtist_product_transcript import is_ui_noise_text

_BAD_REPLY_FRAGMENTS = (
    "message...",
    "message…",
    "type a message",
    "send a message",
    "메시지...",
    "메세지...",
    "ai 추천 답장",
    "get nsfw reply",
    "flirtist",
    "집중할 키워드",
)


def repair_reply_coaching(
    coaching: FlirtistReplyCoaching,
    language: FlirtistLanguage,
    messages: list[FlirtistPreviewMessage],
) -> FlirtistReplyCoaching:
    fallback = reply_coaching(language, _primary_style(coaching), messages)
    replies = _repair_options(coaching.replies, fallback.replies, messages)
    packs = _repair_packs(coaching.replyPacks, fallback.replyPacks, messages)
    return coaching.model_copy(
        update={
            "summary": fallback.summary if _bad_text(coaching.summary) else coaching.summary,
            "nextMove": fallback.nextMove if _bad_text(coaching.nextMove) else coaching.nextMove,
            "replies": replies,
            "replyPacks": packs,
        }
    )


def _repair_packs(
    packs: list[FlirtistReplyPack],
    fallback_packs: list[FlirtistReplyPack],
    messages: list[FlirtistPreviewMessage],
) -> list[FlirtistReplyPack]:
    fallback_by_style = {pack.style: pack for pack in fallback_packs}
    repaired: list[FlirtistReplyPack] = []
    for pack in packs:
        fallback = fallback_by_style.get(pack.style)
        if fallback is None:
            repaired.append(pack)
            continue
        repaired.append(pack.model_copy(update={"replies": _repair_options(pack.replies, fallback.replies, messages)}))
    return repaired or fallback_packs


def _repair_options(
    options: list[FlirtistReplyOption],
    fallback_options: list[FlirtistReplyOption],
    messages: list[FlirtistPreviewMessage],
) -> list[FlirtistReplyOption]:
    fallback_iter = iter(fallback_options)
    repaired: list[FlirtistReplyOption] = []
    for option in options:
        if _bad_reply_text(option.text, messages):
            repaired.append(next(fallback_iter, fallback_options[0]))
        else:
            repaired.append(option)
    return repaired or fallback_options


def _primary_style(coaching: FlirtistReplyCoaching) -> str:
    styles = chain(
        (reply.style for reply in coaching.replies),
        (pack.style for pack in coaching.replyPacks),
    )
    return next((style for style in styles if style), "genuine")


def _bad_text(text: str) -> bool:
    lowered = text.lower()
    return is_ui_noise_text(text) or any(fragment in lowered for fragment in _BAD_REPLY_FRAGMENTS)


def _bad_reply_text(text: str, messages: list[FlirtistPreviewMessage]) -> bool:
    if _bad_text(text):
        return True
    lowered = " ".join(text.lower().split())
    if _has_low_value_phrase(lowered):
        return True
    return _echoes_long_source(lowered, messages) and _has_generic_continuation(lowered)


def _has_low_value_phrase(lowered: str) -> bool:
    weak_phrases = (
        "얘기 조금 더 듣고 싶어",
        "쪽으로 더 얘기",
        "편할 때 이어서",
        "tell me more when",
        "i want to hear more about",
        "more about that when",
    )
    return any(phrase in lowered for phrase in weak_phrases)


def _has_generic_continuation(lowered: str) -> bool:
    generic_phrases = (
        "조금 더",
        "더 얘기",
        "궁금",
        "tell me more",
        "hear more",
        "curious",
    )
    return any(phrase in lowered for phrase in generic_phrases)


def _echoes_long_source(lowered: str, messages: list[FlirtistPreviewMessage]) -> bool:
    for message in messages:
        source = " ".join(message.text.lower().split())
        if len(source) >= 14 and source in lowered:
            return True
    return False
