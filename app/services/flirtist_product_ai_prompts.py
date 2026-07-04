from __future__ import annotations

import json
from typing import Final, TypeAlias

from app.schemas.common import FacemaxxBaseModel
from app.schemas.flirtist_product import (
    FlirtistCoachChatRequest,
    FlirtistCoachChatResponse,
    FlirtistProductSessionRequest,
    FlirtistProductSessionResponse,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.schemas.flirtist import normalize_flirtist_language
from app.services.flirtist_language_profile import analysis_title, culture_guidance, language_name
from app.services.flirtist_product_transcript import sanitized_transcript_text

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]

STYLE_PURPOSE_CONTRACT: Final[tuple[str, ...]] = (
    "Style purpose contract:",
    "genuine: keep the conversation easy to continue without pressure",
    "witty: create light banter from one real chat detail",
    "flirty: show interest clearly but do not overplay it",
    "romantic: give emotional steadiness or empathy without premature commitment",
    "nsfw: raise tension safely without explicit sexual content, coercion, or creepy pressure",
)
CHAT_ONLY_OCR_CONTRACT: Final[tuple[str, ...]] = (
    "Only use text that belongs to visible chat bubbles as evidence for chat analysis and reply writing.",
    "Do not use status bars, navigation bars, dates, timestamps, notification badges, input fields, buttons, icons, usernames outside bubbles, or app scanner/paywall copy as evidence.",
)


def _session_prompt(request: FlirtistProductSessionRequest, fallback: FlirtistProductSessionResponse) -> str:
    prompt_request = request.model_copy(update={"text": sanitized_transcript_text(request.text)})
    target_language = normalize_flirtist_language(request.language, request.locale)
    latest_them_message = _latest_them_message(prompt_request.text)
    return "\n".join(
        [
            "You are Flirtist, a multilingual dating situation coach. Return one JSON object only.",
            f"Target language: {language_name(target_language)}. Locale: {request.locale}.",
            f"Cultural tone guide: {culture_guidance(target_language)}",
            "All user-facing text in the JSON must be written in the target language, including analysis titles, labels, reply text, whyItWorks, summaries, nextMove, redFlags, greenFlags, and attachment phrases.",
            "If a Cloudinary screenshot URL is attached and no transcript text is provided, read the visible chat/profile content from the image.",
            "If transcript text is provided, treat it as authoritative OCR. Infer the latest actionable exchange from the whole transcript, not only the final short reaction.",
            "Role contract for screenshots and transcripts: Them = left-side incoming bubbles from the other person; Me = right-side outgoing bubbles from the app user.",
            "For reply_coach, always write what Me should send next to Them. Never write the message Them should send to Me, and never answer as if Them is comforting, teasing, or replying to Me.",
            f"For reply_coach, answer the latest meaningful Them message: {latest_them_message or '<infer latest Them message from transcript>'}. If the final line is Me, suggest a low-pressure follow-up from Me instead of inventing Them's reply.",
            "Perspective fail examples: if Me offered food/help/a meetup and Them accepted, do not write a reply where Them accepts the offer. Write Me confirming or moving the plan forward.",
            "For Korean accepted-plan chats, phrases like '갈게', '사줘', or '해줘' are usually Them's perspective when Me was the one offering. Avoid them unless Me is clearly the visitor/requester in the transcript.",
            "Ignore app chrome, input placeholders, timestamps, icon labels, and OCR UI noise such as Message..., Type a message, Send, AI 추천 답장, Get NSFW Reply, FLIRTIST, or 집중할 키워드.",
            *CHAT_ONLY_OCR_CONTRACT,
            "chatPreview must contain only Me/Them chat messages from visible bubbles; exclude every non-chat OCR fragment even if it appears in Request JSON.",
            "Never include raw base64 or private identifiers in the JSON.",
            "For reply_coach, produce chatPreview and replyCoaching. For score_analysis, produce analysisCard.",
            f"For score_analysis, localize the analysisCard title as: {analysis_title(target_language)}.",
            "For score_analysis, meaningfulWordsYou and meaningfulWordsThem must be concise words or short phrases copied from the real chat topic, not UI words, timestamps, placeholders, or generic labels.",
            "For score_analysis, keep redFlags, greenFlags, and attachment style phrases short enough for a mobile card while still specific to the chat.",
            "For reply_coach, return replyCoaching.replies as the same four genuine replies used in the genuine style pack, and return replyCoaching.replyPacks with exactly these five style packs in this order: genuine, witty, flirty, romantic, nsfw.",
            *STYLE_PURPOSE_CONTRACT,
            "Each style pack must be grounded in the same latest actionable chat context and include exactly four copy-ready replies that would be wrong for a different chat.",
            "Within each style pack, the four replies must use four different tactics: 1) move the accepted plan forward, 2) ask one concrete missing detail, 3) add a light emotional reaction, 4) make a playful callback to a real chat detail.",
            "Do not anchor all replies on the same visible noun or phrase. Use the underlying situation, and reuse a chat keyword only when it naturally advances the next message.",
            "Keep the initial reply_coach JSON compact: four short alternatives per style, no extra variants beyond those four.",
            "Keep every reply short enough for a phone card: Korean usually 12-34 characters, English usually under 90 characters. Keep whyItWorks under 14 words.",
            "The selected style must change the purpose, not just the adjectives. Do not make five style packs that are the same reply with different warmth levels.",
            "whyItWorks must explain why that purpose fits this chat, not just restate that the reply is good.",
            "Every reply must be copy-ready text the user can send. Never start with speaker labels, OCR fragments, Message..., Them:, Me:, or explanations.",
            "Ground every reply in the last meaningful chat message. If there is enough context, avoid generic prompts like 'tell me more' unless phrased around a specific detail.",
            "Do not quote a full incoming message inside the reply. A short callback is fine; parroting the screenshot text is a failure.",
            "When the latest message is a short yes/좋아/조아네/heart after the user suggested meeting, food, a city, or contacting later, answer the accepted plan directly.",
            "For accepted-plan chats, every reply in every style pack must keep at least one concrete plan detail from the chat, such as the city/place, food/meal, timing, contact, or meetup action.",
            "Do not invent missing plan details. If the chat does not mention a neighborhood, restaurant, exact day, time, or activity, do not create one; ask a light follow-up around the concrete details that are present.",
            "Do not copy fallback wording. The contract JSON is only a shape guide; write fresh replies from the chat.",
            "Quality bar for every reply: 1) references the exact situation without quoting the whole message, 2) sounds like a real text, 3) gives the other person an easy next response, 4) does not suddenly escalate intimacy, 5) is specific enough that it would be wrong for a different chat.",
            "For Korean reply_coach, write replies like a native Korean KakaoTalk/Instagram DM. Avoid 당신, stiff translations, generic coffee templates, and phrases like 고생한 기념 unless the chat naturally supports them.",
            "For Korean reply_coach, preserve the relationship tone from the screenshot: 존댓말 vs 반말, warmth, humor level, and how close they seem. Prefer short, alive Korean that reacts to the specific trigger instead of quoting the whole incoming message.",
            "For English reply_coach, avoid canned pickup-line clichés. Use the actual visible context and produce copy-ready text, not coaching advice.",
            "Refuse unsafe dating manipulation, stalking, coercion, minors, or explicit sexual pressure.",
            f"Request JSON without image: {prompt_request.model_dump_json(exclude={'imageBase64'})}",
            f"Cloudinary image URL: {fallback.imageUrl or 'none'}",
            f"Response contract JSON: {_contract_json(fallback)}",
        ]
    )


def _style_prompt(request: FlirtistReplyStyleRequest, fallback: FlirtistReplyStyleResponse) -> str:
    prompt_request = request.model_copy(update={"context": sanitized_transcript_text(request.context) or request.context})
    target_language = normalize_flirtist_language(request.language, request.locale)
    return "\n".join(
        [
            "Rewrite the dating reply in the requested style. Return one JSON object only.",
            f"Target language: {language_name(target_language)}. Locale: {request.locale}.",
            f"Cultural tone guide: {culture_guidance(target_language)}",
            "All returned reply text, labels, summary, nextMove, and whyItWorks must be in the target language.",
            "Rewrite as Me talking to Them. In screenshots, Them means left-side incoming and Me means right-side outgoing.",
            "Never produce a reply that Them would send to Me.",
            "If Me offered food/help/a meetup and Them accepted, do not write a reply where Them accepts the offer. Write Me confirming or moving the plan forward.",
            "For Korean accepted-plan chats, phrases like '갈게', '사줘', or '해줘' are usually Them's perspective when Me was the one offering. Avoid them unless Me is clearly the visitor/requester in the context.",
            "Keep it natural, low-pressure, and safe. Do not mention that AI wrote it.",
            *STYLE_PURPOSE_CONTRACT,
            "The selected style must change the purpose, not just the adjectives. Do not return four paraphrases of the same move.",
            "whyItWorks must explain why that purpose fits this chat, not just restate that the reply is good.",
            "Ignore OCR placeholders and UI chrome such as Message..., Type a message, Send, AI 추천 답장, Get NSFW Reply, FLIRTIST, or 집중할 키워드.",
            *CHAT_ONLY_OCR_CONTRACT,
            "Never include those UI words, speaker labels, or coaching explanations in a reply option.",
            "Do not copy fallback wording. The contract JSON is only a shape guide; write fresh alternatives from the chat.",
            "Reject low-value rewrites that merely say 'tell me more', quote the full incoming message, or could fit any random chat.",
            "The four alternatives must be meaningfully different, not the same idea with swapped adjectives. Vary the move: plan-forward, concrete missing detail, light emotional reaction, playful callback.",
            "Keep each alternative short enough for a phone card: Korean usually 12-34 characters, English usually under 90 characters.",
            "Do not anchor every alternative on the same keyword from the screenshot. Use the situation behind the keyword and keep the language sendable.",
            "If the context includes an accepted plan, city, food, or meetup, every alternative must mention that concrete plan instead of generic emotional support.",
            "For accepted-plan chats, keep at least one concrete plan detail in each alternative, such as the city/place, food/meal, timing, contact, or meetup action.",
            "Do not invent missing plan details such as exact dates, neighborhoods, restaurants, or activities. Ask naturally for the missing detail instead.",
            "For Korean, make every alternative sound like a native Korean text message. Avoid 당신, direct English translation rhythm, and repeated coffee/default invite wording.",
            "Keep the existing closeness level from the base reply and context; do not suddenly become too intimate.",
            "Return exactly 4 alternatives in replyCoaching.replies and a matching single replyPacks entry with those same 4 alternatives.",
            "Treat existingReplies as blocked outputs. Do not repeat or lightly paraphrase any existingReplies item; the four alternatives must be new.",
            "If focus is provided, weave that word or phrase into the alternatives naturally.",
            "If style is nsfw, make it bold and tense but non-explicit, consenting-adult, and never sexually pressuring.",
            "For nsfw, avoid secret-place, night-time, heart-racing, and 'you will not regret it' clichés unless the chat clearly contains that detail.",
            f"Request JSON: {prompt_request.model_dump_json()}",
            f"Response contract JSON: {_contract_json(fallback)}",
        ]
    )


def _coach_prompt(request: FlirtistCoachChatRequest, fallback: FlirtistCoachChatResponse) -> str:
    target_language = normalize_flirtist_language(request.language, request.locale)
    return "\n".join(
        [
            "You are a private 1:1 dating practice coach inside Flirtist.",
            f"Target language: {language_name(target_language)}. Locale: {request.locale}.",
            f"Cultural tone guide: {culture_guidance(target_language)}",
            "Answer, suggestions, and memorySummary must be in the target language unless the user explicitly asks otherwise.",
            "Answer like a sharp human DM coach: concise, specific, warm, and immediately usable.",
            "Do not quote, title-case, or restate the user's question. Never start with '<user message> situation...' or a translated restatement.",
            "If the latest user message is a follow-up like 'so what should I send?' or '그니까 뭐라보낼까', use the previous meaningful user message in history as the real situation.",
            "The context field may include a 'Coach memory:' block. Treat it as compact rolling memory from earlier turns and use it to resolve follow-ups when recent history is too short.",
            "When the user asks what to send or say, put one copy-ready line or spoken opener in the answer, then give one short reason and one next-step guardrail.",
            "Avoid templated coaching filler such as 'one small next action', 'ask one question', 'make the next step optional', or 'send no additional confirmation messages' unless tied to a concrete sentence.",
            "Focus on the latest user message, using history only to recover the current situation. If the history has prior assistant answers, do not repeat them.",
            "Use context as durable private user profile information, but never quote it back verbatim.",
            "For Korean, write like a native KakaoTalk coach: casual, concrete, not textbook-like, and no 당신.",
            "Keep the assistant message under 110 words and make it visibly different for different user messages.",
            "Return one JSON object only. Include an assistant message, 2-5 suggested next user prompts, and memorySummary when useful.",
            "memorySummary should be a compact rolling memory of durable user coaching context, not a transcript. Keep it under 900 characters.",
            "Refuse manipulation, stalking, coercion, minors, or explicit sexual pressure.",
            f"Request JSON: {request.model_dump_json()}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def _contract_json(fallback: FacemaxxBaseModel) -> str:
    if isinstance(fallback, FlirtistProductSessionResponse):
        payload: dict[str, JsonValue] = {}
        payload["chatPreview"] = [
            {"role": "them", "text": "<visible chat message>"},
            {"role": "me", "text": "<visible chat message>"},
        ]
        if fallback.replyCoaching is not None:
            payload["replyCoaching"] = _reply_coaching_contract(include_all_packs=True)
        if fallback.analysisCard is not None:
            payload["analysisCard"] = _analysis_card_contract()
    elif isinstance(fallback, FlirtistReplyStyleResponse):
        payload = {}
        payload["replyCoaching"] = _reply_coaching_contract(include_pack=True)
    elif isinstance(fallback, FlirtistCoachChatResponse):
        payload = {}
        payload["message"] = {"role": "assistant", "text": "<short coach answer>"}
        payload["suggestions"] = ["<next user prompt>"]
    else:
        payload = fallback.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False)


def _reply_coaching_contract(
    *,
    include_pack: bool = False,
    include_all_packs: bool = False,
    replies_per_pack: int = 4,
) -> dict[str, JsonValue]:
    reply_count = min(max(replies_per_pack, 1), 4)
    option = {
        "id": "reply_ai_1",
        "style": "genuine",
        "text": "<copy-ready reply text>",
        "whyItWorks": "<one reason>",
        "aiObviousness": 10,
        "pressure": 20,
        "replyLikelihood": 80,
    }
    options = [
        option | {"id": f"reply_ai_{index}", "text": f"<copy-ready reply text {index}>"}
        for index in range(1, reply_count + 1)
    ]
    pack_specs = [
        ("genuine", "Natural", "Natural replies", "bolt.fill"),
        ("witty", "Witty", "Witty replies", "sparkles"),
        ("flirty", "Flirty", "Flirty replies", "heart.fill"),
        ("romantic", "Warm", "Warm replies", "heart.circle.fill"),
        ("nsfw", "Bold", "Bolder replies", "flame.fill"),
    ]
    packs = [
        {
            "style": style,
            "label": label,
            "buttonTitle": button_title,
            "iconName": icon_name,
            "replies": [
                reply | {"style": style, "text": f"<copy-ready {style} reply text {index}>"}
                for index, reply in enumerate(options, start=1)
            ],
        }
        for style, label, button_title, icon_name in pack_specs
    ]
    if include_pack:
        packs = packs[:1]
    elif not include_all_packs:
        packs = []
    return {
        "headline": "<short title>",
        "summary": "<short situation read>",
        "nextMove": "<one next step>",
        "replies": options,
        "replyPacks": packs,
    }


def _latest_them_message(text: str | None) -> str | None:
    if not text:
        return None
    for line in reversed(text.splitlines()):
        lowered = line.lower().strip()
        for prefix in ("them:", "상대:", "그쪽:"):
            if lowered.startswith(prefix):
                value = line.split(":", 1)[1].strip()
                return value[:160] if value else None
    return None


def _analysis_card_contract() -> dict[str, JsonValue]:
    return {
        "title": "대화 분석 or Chat Wrapped",
        "messageCount": {"you": 3, "them": 4},
        "interestLevel": {"you": 64, "them": 72},
        "meaningfulWordsYou": ["<actual user topic>", "<actual user place>"],
        "meaningfulWordsThem": ["<actual them topic>", "<actual them signal>"],
        "redFlags": ["<specific caution from visible chat>"],
        "greenFlags": ["<specific positive signal from visible chat>"],
        "attachmentYou": "<short style phrase>",
        "attachmentThem": "<short style phrase>",
        "compatibilityScore": 72,
    }
