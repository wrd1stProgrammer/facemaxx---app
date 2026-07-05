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
from app.services.flirtist_product_reply_fallback import FlirtistContentKind
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
    excluded_texts: list[str] | None = None,
    fill_missing: bool = True,
    content_kind: FlirtistContentKind = "chat",
) -> FlirtistReplyCoaching:
    fallback = reply_coaching(language, _primary_style(coaching), messages, content_kind=content_kind)
    replies = _repair_options(coaching.replies, fallback.replies, messages, excluded_texts, fill_missing)
    packs = _repair_packs(coaching.replyPacks, fallback.replyPacks, messages, excluded_texts, fill_missing)
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
    excluded_texts: list[str] | None,
    fill_missing: bool,
) -> list[FlirtistReplyPack]:
    fallback_by_style = {pack.style: pack for pack in fallback_packs}
    repaired: list[FlirtistReplyPack] = []
    for pack in packs:
        fallback = fallback_by_style.get(pack.style)
        if fallback is None:
            repaired.append(pack)
            continue
        repaired.append(
            pack.model_copy(
                update={
                    "replies": _repair_options(
                        pack.replies,
                        fallback.replies,
                        messages,
                        excluded_texts,
                        fill_missing,
                    )
                }
            )
        )
    return repaired or fallback_packs


def _repair_options(
    options: list[FlirtistReplyOption],
    fallback_options: list[FlirtistReplyOption],
    messages: list[FlirtistPreviewMessage],
    excluded_texts: list[str] | None,
    fill_missing: bool,
) -> list[FlirtistReplyOption]:
    target_count = len(fallback_options)
    fallback_iter = iter(fallback_options)
    repaired: list[FlirtistReplyOption] = []
    seen_texts: set[str] = set()
    blocked_texts = {_normalized_reply_text(text) for text in excluded_texts or []}
    why_counts = _why_counts(options)
    metric_counts = _metric_counts(options)
    for option in options:
        if len(repaired) >= target_count:
            break
        normalized = _normalized_reply_text(option.text)
        if normalized in blocked_texts:
            continue
        if _bad_reply_text(option.text, messages):
            if not fill_missing:
                continue
            option = next(fallback_iter, fallback_options[0])
            normalized = _normalized_reply_text(option.text)
        if normalized in seen_texts or normalized in blocked_texts:
            continue
        option = _repair_repeated_details(option, fallback_options, len(repaired), why_counts, metric_counts)
        repaired.append(option)
        seen_texts.add(normalized)
    if not fill_missing:
        return repaired
    for fallback_option in fallback_options:
        if len(repaired) >= target_count:
            break
        normalized = _normalized_reply_text(fallback_option.text)
        if normalized in seen_texts or normalized in blocked_texts:
            continue
        repaired.append(fallback_option)
        seen_texts.add(normalized)
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
    if _wrong_plan_perspective(text, messages):
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
        "편하게 해주는 게 좋더라",
        "무슨 상황",
        "앞뒤가 제일 궁금",
        "네 속도에 맞춰서",
        "나는 잘 듣고 싶어",
        "비밀 장소",
        "밤에 더 신나",
        "심장이 막 뛰",
        "특별한 코스",
        "후회는 안 할 텐데",
        "tell me more when",
        "i want to hear more about",
        "more about that when",
        "i like when you tell me things like that",
        "i like hearing your thoughts at your pace",
        "that felt honest",
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


def _wrong_plan_perspective(text: str, messages: list[FlirtistPreviewMessage]) -> bool:
    if not _latest_them_accepts_prior_me_plan(messages):
        return False
    lowered = text.lower()
    return any(fragment in lowered for fragment in ("사줘", "사주라", "광주 갈게", "내가 갈게"))


def _latest_them_accepts_prior_me_plan(messages: list[FlirtistPreviewMessage]) -> bool:
    latest_them_index = next((index for index in range(len(messages) - 1, -1, -1) if messages[index].role == "them"), None)
    if latest_them_index is None:
        return False
    latest_them = messages[latest_them_index].text.lower().strip()
    if len(latest_them) > 28 or not any(fragment in latest_them for fragment in ("응", "웅", "좋", "조아", "그래", "오키", "ㅇㅋ", "yes", "yeah", "ok")):
        return False
    return any(
        message.role == "me" and _looks_like_user_plan_offer(message.text)
        for message in messages[:latest_them_index]
    )


def _looks_like_user_plan_offer(text: str) -> bool:
    lowered = text.lower()
    return any(fragment in lowered for fragment in ("사줄", "맛난", "맛있는", "연락", "광주", "밥", "커피", "meet", "food", "dinner"))


def _repair_repeated_details(
    option: FlirtistReplyOption,
    fallback_options: list[FlirtistReplyOption],
    index: int,
    why_counts: dict[str, int],
    metric_counts: dict[tuple[int, int, int], int],
) -> FlirtistReplyOption:
    if not fallback_options:
        return option
    fallback = fallback_options[min(index, len(fallback_options) - 1)]
    updates: dict[str, str | int] = {}
    if why_counts.get(option.whyItWorks, 0) > 1:
        updates["whyItWorks"] = fallback.whyItWorks
    metrics = (option.aiObviousness, option.pressure, option.replyLikelihood)
    if metric_counts.get(metrics, 0) > 1:
        updates["aiObviousness"] = fallback.aiObviousness
        updates["pressure"] = fallback.pressure
        updates["replyLikelihood"] = fallback.replyLikelihood
    if not updates:
        return option
    return option.model_copy(update=updates)


def _why_counts(options: list[FlirtistReplyOption]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for option in options:
        counts[option.whyItWorks] = counts.get(option.whyItWorks, 0) + 1
    return counts


def _metric_counts(options: list[FlirtistReplyOption]) -> dict[tuple[int, int, int], int]:
    counts: dict[tuple[int, int, int], int] = {}
    for option in options:
        metrics = (option.aiObviousness, option.pressure, option.replyLikelihood)
        counts[metrics] = counts.get(metrics, 0) + 1
    return counts


def _normalized_reply_text(text: str) -> str:
    return " ".join(text.casefold().split())
