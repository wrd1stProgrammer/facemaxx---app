from __future__ import annotations

from typing import assert_never
from uuid import uuid4

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import (
    FlirtistPreviewMessage,
    FlirtistReplyCoaching,
    FlirtistReplyOption,
    FlirtistReplyPack,
)
from app.services.flirtist_product_reply_context import ReplyContext
from app.services.flirtist_product_reply_context_builder import reply_context_from_messages
from app.services.flirtist_product_reply_texts_en import en_reply_texts
from app.services.flirtist_product_reply_texts_ko import ko_reply_texts
from app.services.flirtist_language_profile import reply_headline, reply_pack_specs as localized_reply_pack_specs


def reply_coaching(
    language: FlirtistLanguage,
    style: str,
    messages: list[FlirtistPreviewMessage] | None = None,
    focus: str | None = None,
) -> FlirtistReplyCoaching:
    context = _reply_context(language, messages or [])
    packs = reply_packs(language, context, focus=focus)
    selected = next((pack for pack in packs if pack.style == style.lower()), packs[0])
    return FlirtistReplyCoaching(
        headline=reply_headline(language),
        summary=_summary(language, context),
        nextMove=_next_move(language, context),
        replies=selected.replies,
        replyPacks=packs,
    )


def ensure_reply_packs(
    coaching: FlirtistReplyCoaching,
    language: FlirtistLanguage,
    messages: list[FlirtistPreviewMessage] | None = None,
    excluded_texts: list[str] | None = None,
    fill_missing: bool = True,
) -> FlirtistReplyCoaching:
    context = _reply_context(language, messages or [])
    fallback_packs = reply_packs(language, context)
    packs = _complete_reply_packs(coaching.replyPacks, fallback_packs, excluded_texts, fill_missing)
    if coaching.replies:
        primary_style = coaching.replies[0].style or fallback_packs[0].style
        packs = _packs_with_primary_replies(packs, primary_style, coaching.replies, excluded_texts, fill_missing)
    return coaching.model_copy(update={"replyPacks": packs})


def _complete_reply_packs(
    provider_packs: list[FlirtistReplyPack],
    fallback_packs: list[FlirtistReplyPack],
    excluded_texts: list[str] | None,
    fill_missing: bool,
) -> list[FlirtistReplyPack]:
    if not provider_packs:
        return fallback_packs
    fallback_by_style = {pack.style: pack for pack in fallback_packs}
    provider_by_style: dict[str, FlirtistReplyPack] = {}
    for pack in provider_packs:
        style = pack.style.strip().lower()
        fallback = fallback_by_style.get(style)
        if fallback is None or style in provider_by_style:
            continue
        provider_by_style[style] = pack.model_copy(
            update={
                "style": fallback.style,
                "label": fallback.label,
                "buttonTitle": fallback.buttonTitle,
                "iconName": fallback.iconName,
                "replies": _reply_options(pack.replies, fallback.replies, excluded_texts, fill_missing),
            }
        )
    return [provider_by_style.get(pack.style, pack) for pack in fallback_packs]


def _packs_with_primary_replies(
    packs: list[FlirtistReplyPack],
    primary_style: str,
    replies: list[FlirtistReplyOption],
    excluded_texts: list[str] | None,
    fill_missing: bool,
) -> list[FlirtistReplyPack]:
    primary = primary_style.lower()
    target_index = next((index for index, pack in enumerate(packs) if pack.style == primary), 0)
    updated_packs: list[FlirtistReplyPack] = []
    for index, pack in enumerate(packs):
        if index != target_index:
            updated_packs.append(pack)
            continue
        next_replies = _reply_options(replies, pack.replies, excluded_texts, fill_missing)
        if len(next_replies) >= len(pack.replies) or (not fill_missing and next_replies):
            updated_packs.append(pack.model_copy(update={"replies": next_replies}))
        else:
            updated_packs.append(pack)
    return updated_packs


def _reply_options(
    provider_replies: list[FlirtistReplyOption],
    fallback_replies: list[FlirtistReplyOption],
    excluded_texts: list[str] | None,
    fill_missing: bool,
) -> list[FlirtistReplyOption]:
    blocked = {_normalized_reply_text(text) for text in excluded_texts or []}
    seen: set[str] = set()
    replies: list[FlirtistReplyOption] = []
    for reply in provider_replies:
        normalized = _normalized_reply_text(reply.text)
        if not normalized or normalized in blocked or normalized in seen:
            continue
        replies.append(reply)
        seen.add(normalized)
        if len(replies) >= 4:
            return replies
    if not fill_missing:
        return replies
    for fallback in fallback_replies:
        normalized = _normalized_reply_text(fallback.text)
        if not normalized or normalized in blocked or normalized in seen:
            continue
        replies.append(fallback)
        seen.add(normalized)
        if len(replies) >= 4:
            break
    return replies


def reply_packs(
    language: FlirtistLanguage,
    context: ReplyContext,
    focus: str | None = None,
) -> list[FlirtistReplyPack]:
    return [
        FlirtistReplyPack(
            style=style,
            label=label,
            buttonTitle=button_title,
            iconName=icon,
            replies=[
                _reply_option(language, style, text, _why_for_style(language, style, index), index)
                for index, text in enumerate(_reply_texts(language, style, context, focus)[:4])
            ],
        )
        for style, label, button_title, icon in _reply_pack_specs(language)
    ]


def _reply_context(language: FlirtistLanguage, messages: list[FlirtistPreviewMessage]) -> ReplyContext:
    return reply_context_from_messages(language, messages)


def _reply_pack_specs(language: FlirtistLanguage) -> list[tuple[str, str, str, str]]:
    return localized_reply_pack_specs(language)


def _reply_texts(
    language: FlirtistLanguage,
    style: str,
    context: ReplyContext,
    focus: str | None,
) -> list[str]:
    if language == "ko":
        return ko_reply_texts(style, context, focus)[:4]
    return en_reply_texts(style, context, focus)[:4]


def _summary(language: FlirtistLanguage, context: ReplyContext) -> str:
    if language == "ko":
        match context.scenario:
            case "celebration":
                return "상대가 좋은 소식을 공유했으니 먼저 진심으로 축하하고, 자연스럽게 더 이어가세요."
            case "fatigue":
                return "상대가 피곤함을 공유했으니 공감 한 줄 뒤에 부담 낮은 다음 흐름을 붙이세요."
            case "affection":
                return "상대가 호감 섞인 말을 꺼냈으니 그 뉘앙스를 받아주고, 왜 생각났는지 가볍게 물어보세요."
            case "plans":
                return "상대가 만남이나 연락 제안을 받아줬으니 약속이 살아나게 구체적으로 이어가세요."
            case "availability":
                return "상대가 지금 별일 없다고 답했으니 부담 낮은 제안이나 장난으로 바로 이어가세요."
            case "reaction" | "generic":
                return "상대가 꺼낸 말을 되짚고, 가볍게 더 말하기 쉬운 답장을 보내세요."
            case unreachable:
                assert_never(unreachable)
    match context.scenario:
        case "celebration":
            return "They shared a win, so lead with a real congratulations and an easy next step."
        case "fatigue":
            return "They shared a rough day, so validate it before adding a low-pressure next step."
        case "affection":
            return "They gave a small signal of affection, so receive it warmly and ask what sparked it."
        case "plans":
            return "They accepted a meetup or contact plan, so make that plan feel concrete and easy to continue."
        case "availability":
            return "They are free or doing nothing, so turn that opening into a light, easy next move."
        case "reaction" | "generic":
            return "Mirror their actual topic and make the next reply easy to answer."
        case unreachable:
            assert_never(unreachable)


def _next_move(language: FlirtistLanguage, context: ReplyContext) -> str:
    if language == "ko":
        match context.scenario:
            case "celebration":
                return "축하를 먼저 보내고, 상대가 더 말하고 싶게 한 문장만 붙이세요."
            case "fatigue":
                return "부담 없이 답하기 쉬운 한 문장으로 보내세요."
            case "affection":
                return "좋다는 반응을 짧게 보여주고, 생각난 순간을 물어보세요."
            case "plans":
                return "장소나 약속을 한 번 더 살려서 답하기 쉬운 한 문장으로 보내세요."
            case "availability":
                return "심심하지 않게 해줄 수 있다는 식으로 짧고 가볍게 보내세요."
            case "reaction" | "generic":
                return "상대가 방금 말한 단어를 그대로 살려서 짧게 보내세요."
            case unreachable:
                assert_never(unreachable)
    match context.scenario:
        case "celebration":
            return "Congratulate them first, then leave one warm opening."
        case "fatigue":
            return "Keep it warm, specific, and low-pressure."
        case "affection":
            return "Receive the signal, then ask what made them think of you."
        case "plans":
            return "Keep the plan concrete and give them one easy next step."
        case "availability":
            return "Make the empty time feel easy to continue without pushing."
        case "reaction" | "generic":
            return "Use their actual topic and ask for one small continuation."
        case unreachable:
            assert_never(unreachable)


def _reply_option(language: FlirtistLanguage, style: str, text: str, why: str, index: int) -> FlirtistReplyOption:
    ai_obviousness, pressure, reply_likelihood = _metrics_for_style(style, index)
    return FlirtistReplyOption(
        id=f"reply_{uuid4().hex[:18]}",
        style=style,
        text=text,
        whyItWorks=why,
        aiObviousness=ai_obviousness,
        pressure=pressure,
        replyLikelihood=reply_likelihood,
    )


def _why_for_style(language: FlirtistLanguage, style: str, index: int) -> str:
    tactic_index = index % 4
    if language == "ko":
        tactic = (
            "다음 행동을 쉽게 정해 답장이 편합니다.",
            "빠진 디테일만 물어 부담이 낮습니다.",
            "감정 반응이 짧아 자연스럽게 이어집니다.",
            "실제 대화 포인트를 살려 티가 덜 납니다.",
        )[tactic_index]
        match style:
            case "nsfw":
                return f"텐션은 올리되 선을 지킵니다. {tactic}"
            case "witty":
                return f"가벼운 티키타카를 만듭니다. {tactic}"
            case "romantic":
                return f"안정감 있게 받아줍니다. {tactic}"
            case "flirty":
                return f"호감은 보이되 과하지 않습니다. {tactic}"
            case _:
                return f"부담 없이 이어갈 명분이 있습니다. {tactic}"
    tactic_en = (
        "It gives them one easy next step.",
        "It asks only for the missing detail.",
        "It adds a light emotional reaction.",
        "It uses a real chat detail.",
    )[tactic_index]
    match style:
        case "nsfw":
            return f"It raises tension safely. {tactic_en}"
        case "witty":
            return f"It turns context into banter. {tactic_en}"
        case "romantic":
            return f"It feels steady, not rushed. {tactic_en}"
        case "flirty":
            return f"It shows interest lightly. {tactic_en}"
        case _:
            return f"It keeps the thread easy. {tactic_en}"


def _metrics_for_style(style: str, index: int) -> tuple[int, int, int]:
    values_by_style = {
        "genuine": ((8, 16, 88), (10, 14, 84), (12, 18, 86), (9, 15, 85)),
        "witty": ((14, 20, 84), (16, 18, 82), (12, 22, 85), (15, 19, 83)),
        "flirty": ((18, 24, 86), (16, 22, 84), (20, 26, 88), (17, 23, 85)),
        "romantic": ((10, 18, 82), (12, 16, 84), (11, 20, 83), (13, 17, 81)),
        "nsfw": ((22, 32, 80), (24, 30, 78), (20, 34, 82), (23, 31, 79)),
    }
    values = values_by_style.get(style, values_by_style["genuine"])
    return values[index % len(values)]


def _normalized_reply_text(text: str) -> str:
    return " ".join(text.casefold().split())
