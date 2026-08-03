from __future__ import annotations

from dataclasses import dataclass
import math
import os
from typing import Literal, assert_never

from app.core.config import Settings, get_settings


FlirtistProvider = Literal["mock", "openai", "anthropic", "gemini", "codex_cli"]
DEFAULT_FLIRTIST_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_FLIRTIST_CODEX_MODEL = "gpt-5.6-luna"
DEFAULT_FLIRTIST_CODEX_REASONING_EFFORT = "low"


@dataclass(frozen=True, slots=True)
class FlirtistAIConfig:
    requested_provider: FlirtistProvider
    effective_provider: FlirtistProvider
    openai_model: str
    anthropic_model: str
    gemini_model: str
    fallback_provider: FlirtistProvider = "openai"
    codex_model: str = DEFAULT_FLIRTIST_CODEX_MODEL
    codex_reasoning_effort: str = DEFAULT_FLIRTIST_CODEX_REASONING_EFFORT
    codex_binary: str = "codex"
    codex_timeout_seconds: float = 45.0
    codex_max_concurrency: int = 2
    codex_home: str = "~/.codex"


def load_flirtist_ai_config() -> FlirtistAIConfig:
    settings = get_settings()
    requested = _provider(os.environ.get("FLIRTIST_AI_PROVIDER"), settings)
    effective = requested if _has_key(requested, settings) else "mock"
    return FlirtistAIConfig(
        requested_provider=requested,
        effective_provider=effective,
        openai_model=os.environ.get("FLIRTIST_OPENAI_MODEL", DEFAULT_FLIRTIST_OPENAI_MODEL).strip()
        or DEFAULT_FLIRTIST_OPENAI_MODEL,
        anthropic_model=os.environ.get("FLIRTIST_ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()
        or "claude-sonnet-4-5",
        gemini_model=os.environ.get("FLIRTIST_GEMINI_MODEL", settings.gemini_model).strip()
        or settings.gemini_model,
        fallback_provider=_fallback_provider(os.environ.get("FLIRTIST_AI_FALLBACK_PROVIDER")),
        codex_model=os.environ.get("FLIRTIST_CODEX_MODEL", DEFAULT_FLIRTIST_CODEX_MODEL).strip()
        or DEFAULT_FLIRTIST_CODEX_MODEL,
        codex_reasoning_effort=_codex_reasoning_effort(
            os.environ.get("FLIRTIST_CODEX_REASONING_EFFORT")
        ),
        codex_binary=os.environ.get("FLIRTIST_CODEX_BIN", "codex").strip() or "codex",
        codex_timeout_seconds=_bounded_float(
            os.environ.get("FLIRTIST_CODEX_TIMEOUT_SECONDS"),
            default=45.0,
            minimum=5.0,
            maximum=120.0,
        ),
        codex_max_concurrency=_bounded_int(
            os.environ.get("FLIRTIST_CODEX_MAX_CONCURRENCY"),
            default=2,
            minimum=1,
            maximum=8,
        ),
        codex_home=os.path.expanduser(os.environ.get("CODEX_HOME", "~/.codex").strip() or "~/.codex"),
    )


def _provider(raw: str | None, settings: Settings) -> FlirtistProvider:
    default_provider = _default_provider(settings)
    normalized = (raw or default_provider).strip().lower()
    aliases: dict[str, FlirtistProvider] = {
        "openai": "openai",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "gemini": "gemini",
        "google": "gemini",
        "codex": "codex_cli",
        "codex-cli": "codex_cli",
        "codex_cli": "codex_cli",
        "mock": "mock",
        "dummy": "mock",
        "fallback": "mock",
        "": "mock",
    }
    return aliases.get(normalized, "mock")


def _default_provider(settings: Settings) -> FlirtistProvider:
    if os.environ.get("FLIRTIST_OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("FLIRTIST_GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY") or settings.openai_api_key:
        return "openai"
    preferred = _provider_alias(getattr(settings, "ai_provider", "dummy"))
    if preferred != "mock" and _has_key(preferred, settings):
        return preferred
    if _has_key("gemini", settings):
        return "gemini"
    return "mock"


def _provider_alias(raw: str | None) -> FlirtistProvider:
    normalized = (raw or "").strip().lower()
    if normalized == "openai":
        return "openai"
    if normalized in {"anthropic", "claude"}:
        return "anthropic"
    if normalized in {"gemini", "google"}:
        return "gemini"
    if normalized in {"codex", "codex-cli", "codex_cli"}:
        return "codex_cli"
    return "mock"


def _fallback_provider(raw: str | None) -> FlirtistProvider:
    normalized = (raw or "openai").strip().lower()
    aliases: dict[str, FlirtistProvider] = {
        "openai": "openai",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "gemini": "gemini",
        "google": "gemini",
        "mock": "mock",
        "dummy": "mock",
        "": "openai",
    }
    # A fallback chain must terminate in an API provider or deterministic mock.
    # Do not allow a self-referential Codex -> Codex loop from configuration.
    return aliases.get(normalized, "openai")


def _codex_reasoning_effort(raw: str | None) -> str:
    normalized = (raw or DEFAULT_FLIRTIST_CODEX_REASONING_EFFORT).strip().lower()
    if normalized == "light":
        normalized = "low"
    if normalized in {"low", "medium", "high", "xhigh", "ultra", "max"}:
        return normalized
    return DEFAULT_FLIRTIST_CODEX_REASONING_EFFORT


def _bounded_float(raw: str | None, *, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(raw) if raw else default
    except ValueError:
        value = default
    if not math.isfinite(value):
        value = default
    return min(max(value, minimum), maximum)


def _bounded_int(raw: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)


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
            return bool(
                os.environ.get("FLIRTIST_GEMINI_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
                or settings.gemini_api_key
            )
        case "codex_cli":
            # Codex authenticates through CODEX_HOME / the local credential store,
            # so the API process cannot determine login state without starting the CLI.
            return True
        case unreachable:
            assert_never(unreachable)


def provider_chain(config: FlirtistAIConfig) -> tuple[FlirtistProvider, ...]:
    if config.effective_provider != "codex_cli":
        return (config.effective_provider,)
    if config.fallback_provider == "codex_cli":
        return ("codex_cli",)
    return ("codex_cli", config.fallback_provider)


def api_provider_chain(config: FlirtistAIConfig) -> tuple[FlirtistProvider, ...]:
    """Return the provider chain for latency-sensitive API-only product features."""
    if config.effective_provider != "codex_cli":
        return (config.effective_provider,)
    if config.fallback_provider == "codex_cli":
        return ("mock",)
    return (config.fallback_provider,)
