from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.db.supabase import get_supabase_service_client


@dataclass(frozen=True)
class RequestIdentity:
    user_id: str | None
    client_install_id: str | None


def _normalized_uuid(value: str | None) -> str | None:
    if not value:
        return None

    try:
        return str(UUID(value.strip()))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Facemaxx-Install-Id header",
        ) from exc


async def get_current_user_id(
    authorization: Annotated[Optional[str], Header()] = None,
    x_facemaxx_user_id: Annotated[Optional[str], Header()] = None,
) -> str:
    settings = get_settings()

    if settings.auth_disabled:
        return x_facemaxx_user_id or settings.demo_user_id

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Supabase bearer token",
        )

    token = authorization.split(" ", 1)[1].strip()
    supabase = get_supabase_service_client()
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured",
        )

    try:
        user_response = supabase.auth.get_user(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase bearer token",
        ) from exc

    user = getattr(user_response, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase bearer token",
        )

    return str(user.id)


async def get_request_identity(
    authorization: Annotated[Optional[str], Header()] = None,
    x_facemaxx_install_id: Annotated[Optional[str], Header()] = None,
    x_facemaxx_user_id: Annotated[Optional[str], Header()] = None,
) -> RequestIdentity:
    settings = get_settings()
    client_install_id = _normalized_uuid(x_facemaxx_install_id)

    if settings.auth_disabled:
        return RequestIdentity(
            user_id=None,
            client_install_id=client_install_id or _normalized_uuid(x_facemaxx_user_id) or settings.demo_user_id,
        )

    user_id = await get_current_user_id(
        authorization=authorization,
        x_facemaxx_user_id=x_facemaxx_user_id,
    )
    return RequestIdentity(user_id=user_id, client_install_id=client_install_id)
