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
        headline="AI 추천 답장" if language == "ko" else "AI generated rizz",
        summary=_summary(language, context),
        nextMove=_next_move(language, context),
        replies=selected.replies,
        replyPacks=packs,
    )


def ensure_reply_packs(
    coaching: FlirtistReplyCoaching,
    language: FlirtistLanguage,
    messages: list[FlirtistPreviewMessage] | None = None,
) -> FlirtistReplyCoaching:
    if coaching.replyPacks:
        return coaching
    context = _reply_context(language, messages or [])
    return coaching.model_copy(update={"replyPacks": reply_packs(language, context)})


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
                _reply_option(language, style, text, _why_for_style(language, style))
                for text in _reply_texts(language, style, context, focus)
            ],
        )
        for style, label, button_title, icon in _reply_pack_specs(language)
    ]


def _reply_context(language: FlirtistLanguage, messages: list[FlirtistPreviewMessage]) -> ReplyContext:
    return reply_context_from_messages(language, messages)


def _reply_pack_specs(language: FlirtistLanguage) -> list[tuple[str, str, str, str]]:
    if language == "ko":
        return [
            ("genuine", "Genuine", "진짜같은 답장 받기", "bolt.fill"),
            ("nsfw", "NSFW", "Get NSFW Reply", "flame.fill"),
            ("flirty", "Flirty", "Get Flirty Reply", "heart.fill"),
            ("witty", "Witty", "Get Witty Reply", "sparkles"),
            ("romantic", "Romantic", "Get Romantic Reply", "heart.circle.fill"),
        ]
    return [
        ("genuine", "Genuine", "Get Genuine Reply", "bolt.fill"),
        ("nsfw", "NSFW", "Get NSFW Reply", "flame.fill"),
        ("flirty", "Flirty", "Get Flirty Reply", "heart.fill"),
        ("witty", "Witty", "Get Witty Reply", "sparkles"),
        ("romantic", "Romantic", "Get Romantic Reply", "heart.circle.fill"),
    ]


def _reply_texts(
    language: FlirtistLanguage,
    style: str,
    context: ReplyContext,
    focus: str | None,
) -> list[str]:
    if language == "ko":
        return ko_reply_texts(style, context, focus)
    return en_reply_texts(style, context, focus)


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
        case "reaction" | "generic":
            return "Use their actual topic and ask for one small continuation."
        case unreachable:
            assert_never(unreachable)


def _reply_option(language: FlirtistLanguage, style: str, text: str, why: str) -> FlirtistReplyOption:
    return FlirtistReplyOption(
        id=f"reply_{uuid4().hex[:18]}",
        style=style,
        text=text,
        whyItWorks=why,
        aiObviousness=12,
        pressure=18,
        replyLikelihood=84,
    )


def _why_for_style(language: FlirtistLanguage, style: str) -> str:
    if language == "ko":
        match style:
            case "nsfw":
                return "강한 텐션은 주되 노골적 압박 없이 선택권을 남깁니다."
            case "witty":
                return "가벼운 농담으로 대화를 부담 없이 이어갑니다."
            case "romantic":
                return "상대가 꺼낸 맥락을 챙겨 진심이 살아납니다."
            case "flirty":
                return "상대의 말을 받아주면서 자연스럽게 관심을 드러냅니다."
            case _:
                return "상대가 실제로 말한 내용을 되짚어 답장하기 쉽습니다."
    match style:
        case "nsfw":
            return "It raises tension without getting explicit or pressuring them."
        case "witty":
            return "The joke keeps the conversation light and specific."
        case "romantic":
            return "It feels attentive without overdoing it."
        case "flirty":
            return "It mirrors their topic while showing interest."
        case _:
            return "It is warm, specific, and easy to answer."
