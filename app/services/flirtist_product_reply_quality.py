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
    replies = _repair_options(coaching.replies, fallback.replies)
    packs = _repair_packs(coaching.replyPacks, fallback.replyPacks)
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
) -> list[FlirtistReplyPack]:
    fallback_by_style = {pack.style: pack for pack in fallback_packs}
    repaired: list[FlirtistReplyPack] = []
    for pack in packs:
        fallback = fallback_by_style.get(pack.style)
        if fallback is None:
            repaired.append(pack)
            continue
        repaired.append(pack.model_copy(update={"replies": _repair_options(pack.replies, fallback.replies)}))
    return repaired or fallback_packs


def _repair_options(
    options: list[FlirtistReplyOption],
    fallback_options: list[FlirtistReplyOption],
) -> list[FlirtistReplyOption]:
    fallback_iter = iter(fallback_options)
    repaired: list[FlirtistReplyOption] = []
    for option in options:
        if _bad_text(option.text):
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
