from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, TypeAlias, assert_never

from app.schemas.flirtist import (
    FlirtistChatRequest,
    FlirtistDraftRequest,
    FlirtistGenerateRequest,
    FlirtistGoalRequest,
    FlirtistOCRRequest,
    FlirtistPickupLinesRequest,
    FlirtistPickupLinesResponse,
    FlirtistProfileRequest,
    FlirtistResponse,
)
from app.services.flirtist_config import FlirtistProvider


@dataclass(frozen=True, slots=True)
class AnthropicContentShapeError(Exception):
    reason: str


@dataclass(frozen=True, slots=True)
class FlirtistProviderError(Exception):
    provider: FlirtistProvider
    reason: str

    def __str__(self) -> str:
        return f"{self.provider}: {self.reason}"


FlirtistAIAction: TypeAlias = Literal[
    "analyze_chat",
    "generate_replies",
    "check_draft",
    "profile_coach",
    "goal_coach",
    "ocr_chat",
    "pickup_lines",
]
FlirtistAIRequest: TypeAlias = (
    FlirtistChatRequest
    | FlirtistGenerateRequest
    | FlirtistDraftRequest
    | FlirtistProfileRequest
    | FlirtistGoalRequest
    | FlirtistOCRRequest
    | FlirtistPickupLinesRequest
)
JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


def prompt(*, action: FlirtistAIAction, request: FlirtistAIRequest, fallback: FlirtistResponse) -> str:
    return "\n".join(
        [
            "You are Flirtist, a bilingual dating situation coach for Korean and English dating contexts.",
            "Return one JSON object only. No markdown. Match this response contract exactly.",
            "Refuse or de-escalate sexual, minor-involved, coercive, stalking, or harassment requests.",
            "Do not include provider names. Do not store or ask for raw screenshots.",
            "For Korean output, write like a native Korean KakaoTalk or Instagram DM: short, idiomatic, context-first, and copy-ready.",
            "For Korean output, avoid 당신, literal English translations, fortune-cookie compliments, and default coffee invites unless the context actually points there.",
            "For English output, avoid canned pickup-line clichés and make each reply sound like a real person texting in this specific situation.",
            "For reply suggestions, return messages the user can send directly, not coaching explanations.",
            f"Action: {action}",
            f"Request JSON: {request_json_for_prompt(request)}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def request_json_for_prompt(request: FlirtistAIRequest) -> str:
    payload = request.model_dump(exclude_none=True, mode="json")
    match request:
        case FlirtistOCRRequest():
            if "imageBase64" in payload:
                payload["imageBase64"] = "[omitted raw screenshot image]"
        case (
            FlirtistChatRequest()
            | FlirtistGenerateRequest()
            | FlirtistDraftRequest()
            | FlirtistProfileRequest()
            | FlirtistGoalRequest()
            | FlirtistPickupLinesRequest()
        ):
            pass
        case unreachable:
            assert_never(unreachable)
    return json.dumps(payload, ensure_ascii=False)


def response_from_text(
    text: str,
    *,
    fallback: FlirtistResponse,
    provider: FlirtistProvider,
) -> FlirtistResponse:
    if not text.strip():
        raise FlirtistProviderError(provider=provider, reason="empty provider response")
    data = json_object_from_text(text)
    base = fallback.model_dump(mode="json")
    base.update(data)
    return FlirtistResponse.model_validate(base)


def pickup_lines_from_text(
    text: str,
    *,
    fallback: FlirtistPickupLinesResponse,
    provider: FlirtistProvider,
) -> FlirtistPickupLinesResponse:
    if not text.strip():
        raise FlirtistProviderError(provider=provider, reason="empty provider response")
    data = json_object_from_text(text)
    base = fallback.model_dump(mode="json")
    base.update(data)
    return FlirtistPickupLinesResponse.model_validate(base)


def json_object_from_text(text: str) -> JSONObject:
    try:
        value: JSONValue = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise json.JSONDecodeError("provider response is not a JSON object", text, 0)
    return value


def anthropic_content_text(payload: JSONObject) -> str:
    content = payload["content"]
    if not isinstance(content, list):
        raise AnthropicContentShapeError(reason="content_not_list")
    texts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            texts.append(item["text"])
    if not texts:
        raise AnthropicContentShapeError(reason="missing_text_content")
    return "\n".join(texts)
