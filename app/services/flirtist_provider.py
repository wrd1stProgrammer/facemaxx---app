from __future__ import annotations

import json
import os
from typing import Protocol, assert_never

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
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
from app.services.flirtist_pickup_lines import pickup_lines_prompt
from app.services.flirtist_provider_payloads import (
    FlirtistAIAction,
    FlirtistAIRequest,
    FlirtistProviderError,
    anthropic_content_text,
    pickup_lines_from_text,
    prompt,
    response_from_text,
)


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
                prompt=prompt(action=action, request=request, fallback=fallback),
                config=self._config,
            )
            return response_from_text(text, fallback=fallback, provider=provider)
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
                prompt=pickup_lines_prompt(request=request, fallback=fallback),
                config=self._config,
            )
            return pickup_lines_from_text(text, fallback=fallback, provider=provider)
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
                return anthropic_content_text(response.json())
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise FlirtistProviderError(provider="anthropic", reason=str(exc)) from exc

    def _gemini_text(self, *, prompt: str, config: FlirtistAIConfig) -> str:
        key = _provider_key("FLIRTIST_GEMINI_API_KEY", "GEMINI_API_KEY", "gemini")
        previous_google_api_key = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            from google import genai
            from google.genai import errors, types
        except ImportError as exc:
            raise FlirtistProviderError(provider="gemini", reason=str(exc)) from exc

        try:
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
        except (errors.APIError, AttributeError, RuntimeError, ValueError) as exc:
            raise FlirtistProviderError(provider="gemini", reason=str(exc)) from exc
        finally:
            if previous_google_api_key is not None:
                os.environ["GOOGLE_API_KEY"] = previous_google_api_key


def _provider_key(primary: str, fallback: str, provider: FlirtistProvider) -> str:
    value = os.environ.get(primary) or os.environ.get(fallback)
    if value:
        return value
    settings = get_settings()
    match provider:
        case "openai":
            if settings.openai_api_key:
                return settings.openai_api_key
        case "gemini":
            if settings.gemini_api_key:
                return settings.gemini_api_key
        case "anthropic" | "mock":
            pass
        case unreachable:
            assert_never(unreachable)
    raise FlirtistProviderError(provider=provider, reason=f"{primary} is not configured")
