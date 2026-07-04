from __future__ import annotations

from typing import assert_never

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.services.flirtist_config import FlirtistProvider


def provider_image_url(
    request: FlirtistProductSessionRequest,
    stored_image_url: str | None,
    provider: FlirtistProvider,
) -> str | None:
    match provider:
        case "openai":
            return _openai_inline_image_url(request) or stored_image_url
        case "anthropic" | "gemini" | "mock":
            return stored_image_url
        case unreachable:
            assert_never(unreachable)


def _openai_inline_image_url(request: FlirtistProductSessionRequest) -> str | None:
    if request.source != "screenshot" or not request.imageBase64:
        return None
    encoded = request.imageBase64
    if encoded.startswith("data:"):
        return encoded
    return f"data:{request.imageMimeType or 'image/jpeg'};base64,{encoded}"
