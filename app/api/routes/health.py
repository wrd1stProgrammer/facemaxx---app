from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "env": settings.app_env,
        "supabase_configured": settings.supabase_configured,
        "ai_provider": settings.ai_provider,
    }

