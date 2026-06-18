from __future__ import annotations

import json
from typing import TypeAlias

from app.schemas.common import FacemaxxBaseModel
from app.schemas.flirtist_product import (
    FlirtistCoachChatRequest,
    FlirtistCoachChatResponse,
    FlirtistProductSessionRequest,
    FlirtistProductSessionResponse,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.services.flirtist_product_transcript import sanitized_transcript_text

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def _session_prompt(request: FlirtistProductSessionRequest, fallback: FlirtistProductSessionResponse) -> str:
    prompt_request = request.model_copy(update={"text": sanitized_transcript_text(request.text)})
    return "\n".join(
        [
            "You are Flirtist, a bilingual dating situation coach. Return one JSON object only.",
            "If a Cloudinary screenshot URL is attached, read the visible chat/profile content from the image.",
            "If transcript text is provided, treat it as authoritative OCR. Infer the latest actionable exchange from the whole transcript, not only the final short reaction.",
            "Ignore app chrome, input placeholders, timestamps, icon labels, and OCR UI noise such as Message..., Type a message, Send, AI 추천 답장, Get NSFW Reply, FLIRTIST, or 집중할 키워드.",
            "Never include raw base64 or private identifiers in the JSON.",
            "For reply_coach, produce chatPreview and replyCoaching. For score_analysis, produce analysisCard.",
            "For reply_coach, return 1-3 strong replies in replyCoaching.replies only; do not generate replyPacks.",
            "Every reply must be copy-ready text the user can send. Never start with speaker labels, OCR fragments, Message..., Them:, Me:, or explanations.",
            "Ground every reply in the last meaningful chat message. If there is enough context, avoid generic prompts like 'tell me more' unless phrased around a specific detail.",
            "When the latest message is a short yes/좋아/조아네/heart after the user suggested meeting, food, a city, or contacting later, answer the accepted plan directly.",
            "Do not copy fallback wording. The contract JSON is only a shape guide; write fresh replies from the chat.",
            "Quality bar for every reply: 1) references the exact situation without quoting the whole message, 2) sounds like a real text, 3) gives the other person an easy next response, 4) does not suddenly escalate intimacy, 5) is specific enough that it would be wrong for a different chat.",
            "The server will expand style packs after your response, so keep the JSON compact and focused on the visible situation.",
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
    return "\n".join(
        [
            "Rewrite the dating reply in the requested style. Return one JSON object only.",
            "Keep it natural, low-pressure, and safe. Do not mention that AI wrote it.",
            "Ignore OCR placeholders and UI chrome such as Message..., Type a message, Send, AI 추천 답장, Get NSFW Reply, FLIRTIST, or 집중할 키워드.",
            "Never include those UI words, speaker labels, or coaching explanations in a reply option.",
            "Do not copy fallback wording. The contract JSON is only a shape guide; write fresh alternatives from the chat.",
            "Reject low-value rewrites that merely say 'tell me more', quote the full incoming message, or could fit any random chat.",
            "If the context includes an accepted plan, city, food, or meetup, every alternative must mention that concrete plan instead of generic emotional support.",
            "For Korean, make every alternative sound like a native Korean text message. Avoid 당신, direct English translation rhythm, and repeated coffee/default invite wording.",
            "Keep the existing closeness level from the base reply and context; do not suddenly become too intimate.",
            "Return replyCoaching with 5 alternatives in replyCoaching.replies and a matching single replyPacks entry.",
            "If focus is provided, weave that word or phrase into the alternatives naturally.",
            "If style is nsfw, make it bold and tense but non-explicit, consenting-adult, and never sexually pressuring.",
            f"Request JSON: {prompt_request.model_dump_json()}",
            f"Response contract JSON: {_contract_json(fallback)}",
        ]
    )


def _coach_prompt(request: FlirtistCoachChatRequest, fallback: FlirtistCoachChatResponse) -> str:
    return "\n".join(
        [
            "You are a private 1:1 dating practice coach inside Flirtist.",
            "Answer like a sharp human DM coach: concise, specific, warm, and immediately usable.",
            "Do not quote, title-case, or restate the user's question. Never start with '<user message> situation...' or a translated restatement.",
            "If the latest user message is a follow-up like 'so what should I send?' or '그니까 뭐라보낼까', use the previous meaningful user message in history as the real situation.",
            "When the user asks what to send or say, put one copy-ready line or spoken opener in the answer, then give one short reason and one next-step guardrail.",
            "Avoid templated coaching filler such as 'one small next action', 'ask one question', 'make the next step optional', or 'send no additional confirmation messages' unless tied to a concrete sentence.",
            "Focus on the latest user message, using history only to recover the current situation. If the history has prior assistant answers, do not repeat them.",
            "Use context as durable private user profile information, but never quote it back verbatim.",
            "For Korean, write like a native KakaoTalk coach: casual, concrete, not textbook-like, and no 당신.",
            "Keep the assistant message under 110 words and make it visibly different for different user messages.",
            "Return one JSON object only. Include an assistant message and 2-5 suggested next user prompts.",
            "Refuse manipulation, stalking, coercion, minors, or explicit sexual pressure.",
            f"Request JSON: {request.model_dump_json()}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def _contract_json(fallback: FacemaxxBaseModel) -> str:
    payload = fallback.model_dump(mode="json")
    if isinstance(fallback, FlirtistProductSessionResponse):
        payload["chatPreview"] = [
            {"role": "them", "text": "<visible chat message>"},
            {"role": "me", "text": "<visible chat message>"},
        ]
        if payload.get("replyCoaching") is not None:
            payload["replyCoaching"] = _reply_coaching_contract()
        if payload.get("analysisCard") is not None:
            payload["analysisCard"] = "<analysisCard object matching schema>"
    elif isinstance(fallback, FlirtistReplyStyleResponse):
        payload["replyCoaching"] = _reply_coaching_contract(include_pack=True)
    elif isinstance(fallback, FlirtistCoachChatResponse):
        payload["message"] = {"role": "assistant", "text": "<short coach answer>"}
        payload["suggestions"] = ["<next user prompt>"]
    return json.dumps(payload, ensure_ascii=False)


def _reply_coaching_contract(*, include_pack: bool = False) -> dict[str, JsonValue]:
    option = {
        "id": "reply_ai_1",
        "style": "genuine",
        "text": "<copy-ready reply text>",
        "whyItWorks": "<one reason>",
        "aiObviousness": 10,
        "pressure": 20,
        "replyLikelihood": 80,
    }
    pack = {
        "style": "genuine",
        "label": "Genuine",
        "buttonTitle": "Get Genuine Reply",
        "iconName": "bolt.fill",
        "replies": [option],
    }
    return {
        "headline": "<short title>",
        "summary": "<short situation read>",
        "nextMove": "<one next step>",
        "replies": [option],
        "replyPacks": [pack] if include_pack else [],
    }
