from __future__ import annotations

import json
import os
import re
from typing import TypeVar

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.common import FacemaxxBaseModel
from app.schemas.flirtist_product import (
    FlirtistCoachChatRequest,
    FlirtistCoachChatResponse,
    FlirtistProductSessionRequest,
    FlirtistProductSessionResponse,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.services.flirtist_config import FlirtistAIConfig, load_flirtist_ai_config

ProductModel = TypeVar("ProductModel", bound=FacemaxxBaseModel)


class FlirtistProductAI:
    def __init__(self, config: FlirtistAIConfig | None = None) -> None:
        self._config = config or load_flirtist_ai_config()

    def complete_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        fallback: FlirtistProductSessionResponse,
        image_url: str | None,
    ) -> FlirtistProductSessionResponse:
        text = self._complete_json_text(prompt=_session_prompt(request, fallback), image_url=image_url)
        if text is None:
            return fallback
        return _merge_response(text, fallback, FlirtistProductSessionResponse)

    def complete_style(
        self,
        *,
        request: FlirtistReplyStyleRequest,
        fallback: FlirtistReplyStyleResponse,
    ) -> FlirtistReplyStyleResponse:
        text = self._complete_json_text(prompt=_style_prompt(request, fallback), image_url=None)
        if text is None:
            return fallback
        return _merge_response(text, fallback, FlirtistReplyStyleResponse)

    def complete_coach_chat(
        self,
        *,
        request: FlirtistCoachChatRequest,
        fallback: FlirtistCoachChatResponse,
    ) -> FlirtistCoachChatResponse:
        text = self._complete_json_text(prompt=_coach_prompt(request, fallback), image_url=None)
        if text is None:
            return fallback
        return _merge_response(text, fallback, FlirtistCoachChatResponse)

    def _complete_json_text(self, *, prompt: str, image_url: str | None) -> str | None:
        if self._config.effective_provider != "openai":
            return None
        try:
            from openai import OpenAI, OpenAIError
        except ImportError:
            return None

        try:
            api_key = _openai_key()
            if api_key is None:
                return None
            client = OpenAI(api_key=api_key)
            content = [{"type": "input_text", "text": prompt}]
            if image_url:
                content.append(
                    {
                        "type": "input_image",
                        "image_url": image_url,
                    }
                )
            response = client.responses.create(
                model=self._config.openai_model,
                input=[{"role": "user", "content": content}],
            )
            return response.output_text or None
        except (OpenAIError, AttributeError):
            return None


def _session_prompt(request: FlirtistProductSessionRequest, fallback: FlirtistProductSessionResponse) -> str:
    return "\n".join(
        [
            "You are Flirtist, a bilingual dating situation coach. Return one JSON object only.",
            "If a Cloudinary screenshot URL is attached, read the visible chat/profile content from the image.",
            "Never include raw base64 or private identifiers in the JSON.",
            "For reply_coach, produce chatPreview and replyCoaching. For score_analysis, produce analysisCard.",
            "Refuse unsafe dating manipulation, stalking, coercion, minors, or explicit sexual pressure.",
            f"Request JSON without image: {request.model_dump_json(exclude={'imageBase64'})}",
            f"Cloudinary image URL: {fallback.imageUrl or 'none'}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def _style_prompt(request: FlirtistReplyStyleRequest, fallback: FlirtistReplyStyleResponse) -> str:
    return "\n".join(
        [
            "Rewrite the dating reply in the requested style. Return one JSON object only.",
            "Keep it natural, low-pressure, and safe. Do not mention that AI wrote it.",
            f"Request JSON: {request.model_dump_json()}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def _coach_prompt(request: FlirtistCoachChatRequest, fallback: FlirtistCoachChatResponse) -> str:
    return "\n".join(
        [
            "You are a private 1:1 dating practice coach inside Flirtist.",
            "Answer like an Instagram DM coach: concise, specific, warm, and actionable.",
            "Return one JSON object only. Include an assistant message and 2-5 suggested next user prompts.",
            "Refuse manipulation, stalking, coercion, minors, or explicit sexual pressure.",
            f"Request JSON: {request.model_dump_json()}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def _merge_response(text: str, fallback: ProductModel, model: type[ProductModel]) -> ProductModel:
    try:
        payload = _json_object_from_text(text)
        base = fallback.model_dump(mode="json")
        base.update(payload)
        return model.model_validate(base)
    except (ValidationError, json.JSONDecodeError, AttributeError):
        return fallback


def _json_object_from_text(text: str):
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise json.JSONDecodeError("provider response is not a JSON object", text, 0)
    return value


def _openai_key() -> str | None:
    settings = get_settings()
    return os.environ.get("FLIRTIST_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
