from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Literal, assert_never

from app.core.config import Settings, get_settings


FlirtistProvider = Literal["mock", "openai", "anthropic", "gemini"]


@dataclass(frozen=True, slots=True)
class FlirtistAIConfig:
    requested_provider: FlirtistProvider
    effective_provider: FlirtistProvider
    openai_model: str
    anthropic_model: str
    gemini_model: str


def load_flirtist_ai_config() -> FlirtistAIConfig:
    settings = get_settings()
    requested = _provider(os.environ.get("FLIRTIST_AI_PROVIDER"), settings)
    effective = requested if _has_key(requested, settings) else "mock"
    return FlirtistAIConfig(
        requested_provider=requested,
        effective_provider=effective,
        openai_model=os.environ.get("FLIRTIST_OPENAI_MODEL", settings.openai_model).strip() or settings.openai_model,
        anthropic_model=os.environ.get("FLIRTIST_ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()
        or "claude-sonnet-4-5",
        gemini_model=os.environ.get("FLIRTIST_GEMINI_MODEL", "gemini-3-flash-preview").strip()
        or "gemini-3-flash-preview",
    )


def _provider(raw: str | None, settings: Settings) -> FlirtistProvider:
    default_provider = "openai" if os.environ.get("FLIRTIST_OPENAI_API_KEY") or settings.openai_api_key else "mock"
    normalized = (raw or default_provider).strip().lower()
    aliases: dict[str, FlirtistProvider] = {
        "openai": "openai",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "gemini": "gemini",
        "google": "gemini",
        "mock": "mock",
        "dummy": "mock",
        "fallback": "mock",
        "": "mock",
    }
    return aliases.get(normalized, "mock")


def _has_key(provider: FlirtistProvider, settings: Settings) -> bool:
    match provider:
        case "mock":
            return True
        case "openai":
            return bool(
                os.environ.get("FLIRTIST_OPENAI_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or settings.openai_api_key
            )
        case "anthropic":
            return bool(os.environ.get("FLIRTIST_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
        case "gemini":
            return bool(os.environ.get("FLIRTIST_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY"))
        case unreachable:
            assert_never(unreachable)
