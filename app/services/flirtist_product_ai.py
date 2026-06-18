from __future__ import annotations

import json
import logging
import os
import re
from typing import TypeAlias, TypeVar

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
from app.services.flirtist_product_ai_prompts import _coach_prompt, _session_prompt, _style_prompt

ProductModel = TypeVar("ProductModel", bound=FacemaxxBaseModel)
JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
LOGGER = logging.getLogger(__name__)


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
        text = self._complete_json_text(
            prompt=_session_prompt(request, fallback),
            image_url=image_url,
            response_model=FlirtistProductSessionResponse,
            max_output_tokens=1800,
        )
        if text is None:
            return fallback
        return _merge_response(text, fallback, FlirtistProductSessionResponse)

    def complete_style(
        self,
        *,
        request: FlirtistReplyStyleRequest,
        fallback: FlirtistReplyStyleResponse,
    ) -> FlirtistReplyStyleResponse:
        text = self._complete_json_text(
            prompt=_style_prompt(request, fallback),
            image_url=None,
            response_model=FlirtistReplyStyleResponse,
            max_output_tokens=1800,
        )
        if text is None:
            return fallback
        return _merge_response(text, fallback, FlirtistReplyStyleResponse)

    def complete_coach_chat(
        self,
        *,
        request: FlirtistCoachChatRequest,
        fallback: FlirtistCoachChatResponse,
    ) -> FlirtistCoachChatResponse:
        text = self._complete_json_text(
            prompt=_coach_prompt(request, fallback),
            image_url=None,
            response_model=FlirtistCoachChatResponse,
            max_output_tokens=450,
        )
        if text is None:
            return fallback
        return _merge_response(text, fallback, FlirtistCoachChatResponse)

    def _complete_json_text(
        self,
        *,
        prompt: str,
        image_url: str | None,
        response_model: type[ProductModel],
        max_output_tokens: int = 1400,
    ) -> str | None:
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
            client = OpenAI(api_key=api_key, timeout=45.0)
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
                max_output_tokens=max_output_tokens,
                text=_response_text_format(response_model),
            )
            return response.output_text or None
        except (OpenAIError, AttributeError) as exc:
            LOGGER.warning("Flirtist product OpenAI completion failed: %s", exc)
            return None


def _merge_response(text: str, fallback: ProductModel, model: type[ProductModel]) -> ProductModel:
    try:
        payload = _json_object_from_text(text)
        base = fallback.model_dump(mode="json")
        base.update(payload)
        return model.model_validate(base)
    except (ValidationError, json.JSONDecodeError, AttributeError) as exc:
        LOGGER.warning("Flirtist product provider response could not be merged: %s", exc)
        return fallback


def _response_text_format(model: type[ProductModel]) -> dict[str, JsonValue]:
    return {
        "format": {
            "type": "json_schema",
            "name": model.__name__,
            "schema": model.model_json_schema(),
            "strict": False,
        }
    }


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
