from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import TypeAlias, TypeVar, assert_never

from pydantic import Field, ValidationError

from app.core.config import get_settings
from app.schemas.common import FacemaxxBaseModel
from app.schemas.flirtist_product import (
    FlirtistAnalysisCard,
    FlirtistCoachChatRequest,
    FlirtistCoachChatResponse,
    FlirtistProductSessionRequest,
    FlirtistProductSessionResponse,
    FlirtistPreviewMessage,
    FlirtistReplyCoaching,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.services.flirtist_config import FlirtistAIConfig, load_flirtist_ai_config
from app.services.flirtist_product_image_input import provider_image_url
from app.services.flirtist_provider import (
    FlirtistProviderError,
    FlirtistProviderTransport,
    LiveFlirtistProviderTransport,
)
from app.services.flirtist_product_ai_prompts import _coach_prompt, _session_prompt, _style_prompt

ProductModel = TypeVar("ProductModel", bound=FacemaxxBaseModel)
JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
LOGGER = logging.getLogger(__name__)


class FlirtistAIReplyOption(FacemaxxBaseModel):
    text: str = Field(min_length=1, max_length=1200)
    whyItWorks: str = Field(min_length=1, max_length=240)


class FlirtistAIReplyPack(FacemaxxBaseModel):
    style: str = Field(min_length=2, max_length=40)
    replies: list[FlirtistAIReplyOption] = Field(min_length=4, max_length=4)


class FlirtistAIReplyCoaching(FacemaxxBaseModel):
    headline: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=240)
    nextMove: str = Field(min_length=1, max_length=240)
    replyPacks: list[FlirtistAIReplyPack] = Field(min_length=5, max_length=5)


class FlirtistProductSessionAIOutput(FacemaxxBaseModel):
    contentKind: str | None = None
    chatPreview: list[FlirtistPreviewMessage] | None = None
    replyCoaching: FlirtistAIReplyCoaching | None = None
    analysisCard: FlirtistAnalysisCard | None = None


class FlirtistOpenAIWallTimeout(Exception):
    pass


@dataclass(frozen=True, slots=True)
class FlirtistProductAIError(Exception):
    reason: str

    def __str__(self) -> str:
        return self.reason


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
        effective_image_url = provider_image_url(request, image_url, self._config.effective_provider)
        text = self._complete_json_text(
            prompt=_session_prompt(request, fallback),
            image_url=effective_image_url,
            response_model=FlirtistProductSessionAIOutput,
            max_output_tokens=_session_max_output_tokens(request),
            timeout_seconds=_session_timeout_seconds(request, effective_image_url),
        )
        if text is None:
            if _should_fail_without_provider_result(request, self._config.effective_provider):
                raise FlirtistProductAIError(reason=_analysis_failure_message(request.locale))
            return fallback
        response = _merge_response_or_none(text, fallback, FlirtistProductSessionResponse)
        if response is None:
            if _should_fail_without_provider_result(request, self._config.effective_provider):
                raise FlirtistProductAIError(reason=_analysis_failure_message(request.locale))
            return fallback
        return response

    def can_use_inline_session_image(self, request: FlirtistProductSessionRequest) -> bool:
        return (
            self._config.effective_provider == "openai"
            and request.source == "screenshot"
            and bool(request.imageBase64)
        )

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
            timeout_seconds=24.0,
        )
        if text is None:
            if self._config.effective_provider != "mock":
                raise FlirtistProductAIError(reason=_generation_failure_message(request.locale))
            return fallback
        response = _merge_response_or_none(text, fallback, FlirtistReplyStyleResponse)
        if response is None:
            if self._config.effective_provider != "mock":
                raise FlirtistProductAIError(reason=_generation_failure_message(request.locale))
            return fallback
        return response

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
            timeout_seconds=12.0,
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
        timeout_seconds: float = 30.0,
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
                    timeout_seconds=timeout_seconds,
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
        timeout_seconds: float,
    ) -> str | None:
        try:
            from openai import APIConnectionError, APITimeoutError, OpenAI, OpenAIError
        except ImportError:
            LOGGER.warning("Flirtist product OpenAI package is not installed; using fallback")
            return None

        try:
            api_key = _openai_key()
            if api_key is None:
                LOGGER.warning("Flirtist product OpenAI key is not configured; using fallback")
                return None
            content = [{"type": "input_text", "text": prompt}]
            if image_url:
                content.append(
                    {
                        "type": "input_image",
                        "image_url": image_url,
                    }
                )
            attempt_timeouts = _openai_attempt_timeouts(timeout_seconds, image_url)
            for attempt, attempt_timeout in enumerate(attempt_timeouts):
                client = OpenAI(api_key=api_key, timeout=attempt_timeout, max_retries=0)
                try:
                    response = _create_openai_response(
                        client,
                        timeout_seconds=attempt_timeout,
                        request_kwargs={
                            "model": self._config.openai_model,
                            "input": [{"role": "user", "content": content}],
                            "max_output_tokens": max_output_tokens,
                            "text": _response_text_format(response_model),
                            **_openai_latency_options(self._config.openai_model),
                        },
                    )
                    return response.output_text or None
                except (APITimeoutError, APIConnectionError, FlirtistOpenAIWallTimeout) as exc:
                    if attempt + 1 < len(attempt_timeouts):
                        LOGGER.warning(
                            "Flirtist product OpenAI attempt failed; retrying within request budget: %s",
                            exc,
                        )
                        continue
                    raise
            return None
        except (OpenAIError, FlirtistOpenAIWallTimeout, AttributeError) as exc:
            LOGGER.warning("Flirtist product OpenAI completion failed: %s", exc)
            return None


def _transport_prompt(prompt: str, *, image_url: str | None) -> str:
    if image_url is None:
        return prompt
    return "\n".join(
        [
            prompt,
            "",
            f"Cloudinary screenshot image URL: {image_url}",
            "Use the screenshot image as the primary visual source for chat order, left/right speaker roles, and message text. If your provider cannot inspect the image URL, fail instead of inventing chat content.",
        ]
    )


def _session_max_output_tokens(request: FlirtistProductSessionRequest) -> int:
    match request.mode:
        case "reply_coach":
            return 2400
        case "score_analysis":
            return 1400
        case unreachable:
            assert_never(unreachable)


def _session_timeout_seconds(request: FlirtistProductSessionRequest, image_url: str | None = None) -> float:
    is_inline_image = bool(image_url and image_url.startswith("data:image/"))
    match request.mode:
        case "reply_coach":
            return 55.0 if is_inline_image else 55.0 if image_url else 18.0
        case "score_analysis":
            return 35.0 if is_inline_image else 45.0 if image_url else 18.0
        case unreachable:
            assert_never(unreachable)


def _should_fail_without_provider_result(request: FlirtistProductSessionRequest, provider: str) -> bool:
    if provider == "mock":
        return False
    match request.mode:
        case "score_analysis":
            return True
        case "reply_coach":
            return request.source == "screenshot"
        case unreachable:
            assert_never(unreachable)


def _analysis_failure_message(locale: str) -> str:
    if locale.lower().startswith("ko"):
        return "분석에 실패했습니다. 잠시 후 다시 시도해 주세요."
    return "Analysis failed. Please try again in a moment."


def _generation_failure_message(locale: str) -> str:
    if locale.lower().startswith("ko"):
        return "생성에 실패했습니다. 다시 시도해 주세요."
    return "Generation failed. Please try again."


def _merge_response(text: str, fallback: ProductModel, model: type[ProductModel]) -> ProductModel:
    response = _merge_response_or_none(text, fallback, model)
    if response is None:
        return fallback
    return response


def _merge_response_or_none(text: str, fallback: ProductModel, model: type[ProductModel]) -> ProductModel | None:
    try:
        payload = _json_object_from_text(text)
    except json.JSONDecodeError as exc:
        payload = _partial_payload_from_text(text)
        if payload is None:
            LOGGER.warning("Flirtist product provider response could not be merged: %s", exc)
            return None

    try:
        base = fallback.model_dump(mode="json")
        _drop_provider_session_metadata(payload, fallback)
        _normalize_provider_reply_packs(payload, fallback)
        _deep_update(base, payload)
        return model.model_validate(base)
    except (ValidationError, AttributeError) as exc:
        LOGGER.warning("Flirtist product provider response could not be merged: %s", exc)
        return None


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
    if fallback.mode == "score_analysis":
        payload.pop("replyCoaching", None)
    else:
        payload.pop("analysisCard", None)


def _normalize_provider_reply_packs(payload: dict[str, JsonValue], fallback: ProductModel) -> None:
    reply_coaching = payload.get("replyCoaching")
    if not isinstance(reply_coaching, dict):
        return
    reply_packs = reply_coaching.get("replyPacks")
    if reply_packs is None:
        if "replies" in reply_coaching:
            reply_coaching["replyPacks"] = []
        return
    if not isinstance(reply_packs, list):
        reply_coaching["replyPacks"] = []
        return
    fallback_coaching = getattr(fallback, "replyCoaching", None)
    fallback_packs = {
        pack.style.casefold(): pack
        for pack in fallback_coaching.replyPacks
    } if fallback_coaching is not None else {}
    complete_packs: list[JsonValue] = []
    for pack in reply_packs:
        if not isinstance(pack, dict):
            continue
        replies = pack.get("replies")
        if not isinstance(replies, list) or not replies:
            continue
        style = str(pack.get("style") or "").casefold()
        fallback_pack = fallback_packs.get(style)
        enriched_pack = fallback_pack.model_dump(mode="json") if fallback_pack is not None else dict(pack)
        enriched_pack.update({key: value for key, value in pack.items() if key != "replies"})
        enriched_replies: list[JsonValue] = []
        for index, reply in enumerate(replies):
            if not isinstance(reply, dict):
                continue
            fallback_reply = (
                fallback_pack.replies[index]
                if fallback_pack is not None and index < len(fallback_pack.replies)
                else None
            )
            enriched_reply = fallback_reply.model_dump(mode="json") if fallback_reply is not None else {}
            enriched_reply.update(reply)
            enriched_reply["id"] = f"reply_ai_{style}_{index + 1}"
            enriched_reply["style"] = style
            enriched_replies.append(enriched_reply)
        enriched_pack["replies"] = enriched_replies
        complete_packs.append(enriched_pack)
    reply_coaching["replyPacks"] = complete_packs
    genuine_pack = next(
        (pack for pack in complete_packs if isinstance(pack, dict) and pack.get("style") == "genuine"),
        None,
    )
    if isinstance(genuine_pack, dict) and "replies" not in reply_coaching:
        reply_coaching["replies"] = genuine_pack.get("replies", [])


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


def _openai_attempt_timeouts(timeout_seconds: float, image_url: str | None) -> tuple[float, ...]:
    if not image_url or not image_url.startswith("data:image/"):
        return (timeout_seconds,)
    if timeout_seconds >= 55:
        return (40.0, timeout_seconds - 40.0)
    if timeout_seconds >= 35:
        return (25.0, timeout_seconds - 25.0)
    return (timeout_seconds,)


def _create_openai_response(client, *, timeout_seconds: float, request_kwargs: dict[str, object]):
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="flirtist-openai")
    future = executor.submit(client.responses.create, **request_kwargs)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        close = getattr(client, "close", None)
        if callable(close):
            close()
        raise FlirtistOpenAIWallTimeout(f"OpenAI exceeded {timeout_seconds:.0f}s wall-clock budget") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


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
        "contentKind",
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
