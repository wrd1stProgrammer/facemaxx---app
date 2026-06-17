from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias, assert_never

import httpx
from pydantic import ValidationError

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
from app.services.flirtist_config import FlirtistAIConfig, FlirtistProvider


@dataclass(frozen=True, slots=True)
class AnthropicContentShapeError(Exception):
    reason: str


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


@dataclass(frozen=True, slots=True)
class FlirtistProviderError(Exception):
    provider: FlirtistProvider
    reason: str

    def __str__(self) -> str:
        return f"{self.provider}: {self.reason}"


class FlirtistProviderTransport(Protocol):
    def complete_text(self, *, provider: FlirtistProvider, prompt: str, config: FlirtistAIConfig) -> str: ...


class FlirtistAIProviderGateway:
    def __init__(
        self,
        config: FlirtistAIConfig,
        transport: FlirtistProviderTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or LiveFlirtistProviderTransport()

    def complete(
        self,
        *,
        action: FlirtistAIAction,
        request: FlirtistAIRequest,
        fallback: FlirtistResponse,
    ) -> FlirtistResponse:
        provider = self._config.effective_provider
        match provider:
            case "mock":
                return fallback
            case "openai" | "anthropic" | "gemini":
                pass
            case unreachable:
                assert_never(unreachable)
        try:
            text = self._transport.complete_text(
                provider=provider,
                prompt=_prompt(action=action, request=request, fallback=fallback),
                config=self._config,
            )
            return _response_from_text(text, fallback=fallback, provider=provider)
        except (FlirtistProviderError, ValidationError, json.JSONDecodeError):
            return fallback

    def complete_pickup_lines(
        self,
        *,
        request: FlirtistPickupLinesRequest,
        fallback: FlirtistPickupLinesResponse,
    ) -> FlirtistPickupLinesResponse:
        provider = self._config.effective_provider
        match provider:
            case "mock":
                return fallback
            case "openai" | "anthropic" | "gemini":
                pass
            case unreachable:
                assert_never(unreachable)
        try:
            text = self._transport.complete_text(
                provider=provider,
                prompt=_pickup_lines_prompt(request=request, fallback=fallback),
                config=self._config,
            )
            return _pickup_lines_from_text(text, fallback=fallback, provider=provider)
        except (FlirtistProviderError, ValidationError, json.JSONDecodeError):
            return fallback


class LiveFlirtistProviderTransport:
    def complete_text(self, *, provider: FlirtistProvider, prompt: str, config: FlirtistAIConfig) -> str:
        match provider:
            case "mock":
                raise FlirtistProviderError(provider=provider, reason="mock transport is not callable")
            case "openai":
                return self._openai_text(prompt=prompt, config=config)
            case "anthropic":
                return self._anthropic_text(prompt=prompt, config=config)
            case "gemini":
                return self._gemini_text(prompt=prompt, config=config)
            case unreachable:
                assert_never(unreachable)

    def _openai_text(self, *, prompt: str, config: FlirtistAIConfig) -> str:
        key = _provider_key("FLIRTIST_OPENAI_API_KEY", "OPENAI_API_KEY", "openai")
        try:
            from openai import OpenAI, OpenAIError
        except ImportError as exc:
            raise FlirtistProviderError(provider="openai", reason=str(exc)) from exc

        try:
            client = OpenAI(api_key=key)
            response = client.responses.create(model=config.openai_model, input=prompt)
            return response.output_text or ""
        except (OpenAIError, AttributeError) as exc:
            raise FlirtistProviderError(provider="openai", reason=str(exc)) from exc

    def _anthropic_text(self, *, prompt: str, config: FlirtistAIConfig) -> str:
        key = _provider_key("FLIRTIST_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "anthropic")
        try:
            payload = {
                "model": config.anthropic_model,
                "max_tokens": 1200,
                "temperature": 0.35,
                "messages": [{"role": "user", "content": prompt}],
            }
            headers = {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            with httpx.Client(timeout=30) as client:
                response = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                response.raise_for_status()
                return _anthropic_content_text(response.json())
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise FlirtistProviderError(provider="anthropic", reason=str(exc)) from exc

    def _gemini_text(self, *, prompt: str, config: FlirtistAIConfig) -> str:
        key = _provider_key("FLIRTIST_GEMINI_API_KEY", "GEMINI_API_KEY", "gemini")
        previous_google_api_key = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=key)
            generation_config = types.GenerateContentConfig(
                temperature=0.35,
                response_mime_type="application/json",
            )
            response = client.models.generate_content(
                model=config.gemini_model,
                contents=[prompt],
                config=generation_config,
            )
            return response.text or ""
        except (ImportError, AttributeError, RuntimeError, ValueError) as exc:
            raise FlirtistProviderError(provider="gemini", reason=str(exc)) from exc
        finally:
            if previous_google_api_key is not None:
                os.environ["GOOGLE_API_KEY"] = previous_google_api_key


def _provider_key(primary: str, fallback: str, provider: FlirtistProvider) -> str:
    value = os.environ.get(primary) or os.environ.get(fallback)
    if value:
        return value
    raise FlirtistProviderError(provider=provider, reason=f"{primary} is not configured")


def _prompt(*, action: FlirtistAIAction, request: FlirtistAIRequest, fallback: FlirtistResponse) -> str:
    return "\n".join(
        [
            "You are Flirtist, a bilingual dating situation coach for Korean and English dating contexts.",
            "Return one JSON object only. No markdown. Match this response contract exactly.",
            "Refuse or de-escalate sexual, minor-involved, coercive, stalking, or harassment requests.",
            "Do not include provider names. Do not store or ask for raw screenshots.",
            f"Action: {action}",
            f"Request JSON: {_request_json_for_prompt(request)}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def _request_json_for_prompt(request: FlirtistAIRequest) -> str:
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


def _pickup_lines_prompt(*, request: FlirtistPickupLinesRequest, fallback: FlirtistPickupLinesResponse) -> str:
    return "\n".join(
        [
            "You are Flirtist, a dating-app pickup line writer for consenting adult dating contexts.",
            "Return one JSON object only. No markdown. The JSON must include a lines array with exactly 20 strings.",
            "Make every line specific to the user's situation. Keep it playful, natural, and non-explicit.",
            "Avoid coercion, harassment, minors, stalking, or sexually explicit pressure.",
            f"Request JSON: {_request_json_for_prompt(request)}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def _response_from_text(
    text: str,
    *,
    fallback: FlirtistResponse,
    provider: FlirtistProvider,
) -> FlirtistResponse:
    if not text.strip():
        raise FlirtistProviderError(provider=provider, reason="empty provider response")
    data = _json_object_from_text(text)
    base = fallback.model_dump(mode="json")
    base.update(data)
    return FlirtistResponse.model_validate(base)


def _pickup_lines_from_text(
    text: str,
    *,
    fallback: FlirtistPickupLinesResponse,
    provider: FlirtistProvider,
) -> FlirtistPickupLinesResponse:
    if not text.strip():
        raise FlirtistProviderError(provider=provider, reason="empty provider response")
    data = _json_object_from_text(text)
    base = fallback.model_dump(mode="json")
    base.update(data)
    return FlirtistPickupLinesResponse.model_validate(base)


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


def _anthropic_content_text(payload) -> str:
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
