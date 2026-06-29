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
from app.services.flirtist_provider import (
    FlirtistProviderError,
    FlirtistProviderTransport,
    LiveFlirtistProviderTransport,
)
from app.services.flirtist_product_ai_prompts import _coach_prompt, _session_prompt, _style_prompt

ProductModel = TypeVar("ProductModel", bound=FacemaxxBaseModel)
JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
LOGGER = logging.getLogger(__name__)


class FlirtistProductAI:
    def __init__(
        self,
        config: FlirtistAIConfig | None = None,
        provider_transport: FlirtistProviderTransport | None = None,
    ) -> None:
        self._config = config or load_flirtist_ai_config()
        self._provider_transport = provider_transport or LiveFlirtistProviderTransport()

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
            max_output_tokens=3600,
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
            max_output_tokens=2400,
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
        provider = self._config.effective_provider
        match provider:
            case "mock":
                LOGGER.warning(
                    "Flirtist product AI using fallback because provider is mock "
                    "(requested=%s, effective=%s)",
                    self._config.requested_provider,
                    self._config.effective_provider,
                )
                return None
            case "openai":
                return self._complete_openai_json_text(
                    prompt=prompt,
                    image_url=image_url,
                    response_model=response_model,
                    max_output_tokens=max_output_tokens,
                )
            case "anthropic" | "gemini":
                try:
                    return self._provider_transport.complete_text(
                        provider=provider,
                        prompt=_transport_prompt(prompt, image_url=image_url),
                        config=self._config,
                    )
                except FlirtistProviderError as exc:
                    LOGGER.warning("Flirtist product provider completion failed: %s", exc)
                    return None

    def _complete_openai_json_text(
        self,
        *,
        prompt: str,
        image_url: str | None,
        response_model: type[ProductModel],
        max_output_tokens: int,
    ) -> str | None:
        try:
            from openai import OpenAI, OpenAIError
        except ImportError:
            LOGGER.warning("Flirtist product OpenAI package is not installed; using fallback")
            return None

        try:
            api_key = _openai_key()
            if api_key is None:
                LOGGER.warning("Flirtist product OpenAI key is not configured; using fallback")
                return None
            client = OpenAI(api_key=api_key, timeout=30.0)
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
                **_openai_latency_options(self._config.openai_model),
            )
            return response.output_text or None
        except (OpenAIError, AttributeError) as exc:
            LOGGER.warning("Flirtist product OpenAI completion failed: %s", exc)
            return None


def _transport_prompt(prompt: str, *, image_url: str | None) -> str:
    if image_url is None:
        return prompt
    return "\n".join(
        [
            prompt,
            "",
            "Stored screenshot image URL is available for product display only. Use the Request JSON text field as the chat transcript.",
        ]
    )


def _merge_response(text: str, fallback: ProductModel, model: type[ProductModel]) -> ProductModel:
    try:
        payload = _json_object_from_text(text)
    except json.JSONDecodeError as exc:
        payload = _partial_payload_from_text(text)
        if payload is None:
            LOGGER.warning("Flirtist product provider response could not be merged: %s", exc)
            return fallback

    try:
        base = fallback.model_dump(mode="json")
        _drop_provider_session_metadata(payload, fallback)
        _deep_update(base, payload)
        return model.model_validate(base)
    except (ValidationError, AttributeError) as exc:
        LOGGER.warning("Flirtist product provider response could not be merged: %s", exc)
        return fallback


def _drop_provider_session_metadata(payload: dict[str, JsonValue], fallback: ProductModel) -> None:
    if not isinstance(fallback, FlirtistProductSessionResponse):
        return
    for key in (
        "sessionId",
        "mode",
        "source",
        "locale",
        "language",
        "createdAt",
        "saved",
        "serverPersisted",
        "imageUrl",
        "imageStoragePath",
    ):
        payload.pop(key, None)


def _response_text_format(model: type[ProductModel]) -> dict[str, JsonValue]:
    return {
        "format": {
            "type": "json_schema",
            "name": model.__name__,
            "schema": model.model_json_schema(),
            "strict": False,
        }
    }


def _openai_latency_options(model: str) -> dict[str, JsonValue]:
    normalized = model.lower()
    if normalized.startswith("gpt-5") or normalized.startswith(("o3", "o4")):
        return {"reasoning": {"effort": "minimal"}}
    return {}


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


def _partial_payload_from_text(text: str) -> dict[str, JsonValue] | None:
    payload: dict[str, JsonValue] = {}
    for key in (
        "sessionId",
        "mode",
        "source",
        "title",
        "locale",
        "language",
        "createdAt",
        "saved",
        "serverPersisted",
        "imageUrl",
        "imageStoragePath",
        "chatPreview",
        "analysisCard",
    ):
        value = _json_value_after_key(text, key)
        if value is not None:
            payload[key] = value

    reply_coaching = _json_value_after_key(text, "replyCoaching")
    if isinstance(reply_coaching, dict):
        payload["replyCoaching"] = reply_coaching
    else:
        partial_reply_coaching = _partial_reply_coaching_from_text(text)
        if partial_reply_coaching:
            payload["replyCoaching"] = partial_reply_coaching

    return payload or None


def _partial_reply_coaching_from_text(text: str) -> dict[str, JsonValue]:
    start = _value_start_after_key(text, "replyCoaching")
    search_text = text[start:] if start is not None else text
    coaching: dict[str, JsonValue] = {}
    for key in ("headline", "summary", "nextMove", "replyPacks"):
        value = _json_value_after_key(search_text, key)
        if value is not None:
            coaching[key] = value
    replies = _json_value_after_key(search_text, "replies")
    if isinstance(replies, list):
        coaching["replies"] = replies
    else:
        recovered_replies = _json_array_items_after_key(search_text, "replies")
        if recovered_replies:
            coaching["replies"] = recovered_replies
    return coaching


def _deep_update(base: dict[str, JsonValue], payload: dict[str, JsonValue]) -> None:
    for key, value in payload.items():
        existing = base.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            _deep_update(existing, value)
        else:
            base[key] = value


def _json_value_after_key(text: str, key: str) -> JsonValue | None:
    start = _value_start_after_key(text, key)
    if start is None:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:].lstrip())
    except json.JSONDecodeError:
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list | dict):
        return value
    return None


def _json_array_items_after_key(text: str, key: str) -> list[JsonValue]:
    start = _value_start_after_key(text, key)
    if start is None:
        return []
    cursor = _skip_json_space(text, start)
    if cursor >= len(text) or text[cursor] != "[":
        return []
    cursor += 1
    decoder = json.JSONDecoder()
    items: list[JsonValue] = []
    while cursor < len(text):
        cursor = _skip_json_space(text, cursor)
        if cursor >= len(text) or text[cursor] == "]":
            break
        if text[cursor] == ",":
            cursor += 1
            continue
        try:
            value, end = decoder.raw_decode(text[cursor:])
        except json.JSONDecodeError:
            break
        if isinstance(value, (str, int, float, bool)) or value is None:
            items.append(value)
        elif isinstance(value, list | dict):
            items.append(value)
        cursor += end
    return items


def _skip_json_space(text: str, cursor: int) -> int:
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def _value_start_after_key(text: str, key: str) -> int | None:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*', text)
    return match.end() if match else None


def _openai_key() -> str | None:
    settings = get_settings()
    return os.environ.get("FLIRTIST_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
