from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase_service_client() -> Client | None:
    settings = get_settings()
    if not settings.supabase_configured:
        return None

    return create_client(settings.supabase_url, settings.supabase_service_role_key)
