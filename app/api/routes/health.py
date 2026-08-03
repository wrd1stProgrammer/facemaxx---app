from typing import TypedDict

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.flirtist_codex_cli import codex_cli_installed
from app.services.flirtist_config import FlirtistProvider, load_flirtist_ai_config

router = APIRouter(tags=["health"])


class HealthResponse(TypedDict):
    status: str
    env: str
    supabase_configured: bool
    ai_provider: str
    facemaxx_ai_provider: str
    facemaxx_ai_requested_provider: str
    facemaxx_openai_model: str
    flirtist_ai_provider: FlirtistProvider
    flirtist_ai_requested_provider: FlirtistProvider
    flirtist_ai_fallback_provider: FlirtistProvider
    flirtist_openai_model: str
    flirtist_codex_model: str
    flirtist_codex_reasoning_effort: str
    flirtist_codex_cli_installed: bool


@router.get("/health")
async def health() -> HealthResponse:
    settings = get_settings()
    flirtist_ai = load_flirtist_ai_config()
    return {
        "status": "ok",
        "env": settings.app_env,
        "supabase_configured": settings.supabase_configured,
        "ai_provider": settings.ai_provider,
        "facemaxx_ai_provider": "dummy" if settings.ai_provider == "dummy" else "openai",
        "facemaxx_ai_requested_provider": settings.ai_provider,
        "facemaxx_openai_model": settings.openai_model,
        "flirtist_ai_provider": flirtist_ai.effective_provider,
        "flirtist_ai_requested_provider": flirtist_ai.requested_provider,
        "flirtist_ai_fallback_provider": flirtist_ai.fallback_provider,
        "flirtist_openai_model": flirtist_ai.openai_model,
        "flirtist_codex_model": flirtist_ai.codex_model,
        "flirtist_codex_reasoning_effort": flirtist_ai.codex_reasoning_effort,
        "flirtist_codex_cli_installed": codex_cli_installed(flirtist_ai),
    }
