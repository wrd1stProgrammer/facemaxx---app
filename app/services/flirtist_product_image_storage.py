from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import assert_never

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.repositories.photo_repository import PhotoRepository
from app.schemas.flirtist_product import FlirtistProductSessionRequest


@dataclass(frozen=True, slots=True)
class FlirtistStoredImage:
    url: str
    storage_path: str
    mime_type: str


class FlirtistProductImageStorage:
    def __init__(self, photo_repository: PhotoRepository | None = None) -> None:
        self._photo_repository = photo_repository or PhotoRepository()

    def store_session_image(self, request: FlirtistProductSessionRequest) -> FlirtistStoredImage | None:
        if not request.imageBase64:
            return None

        settings = get_settings()
        match settings.image_storage_provider:
            case "auto" | "cloudinary":
                pass
            case "local" | "supabase":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Flirtist screenshots require Cloudinary image storage.",
                )
            case unreachable:
                assert_never(unreachable)

        if not settings.cloudinary_configured:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cloudinary storage is not configured.",
            )

        encoded = request.imageBase64
        if encoded.startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]

        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="imageBase64 must be valid base64 image data.",
            ) from exc

        photo = self._photo_repository.upload_photo(
            user_id=None,
            client_install_id=None,
            content=content,
            filename="flirtist-screenshot.jpg",
            mime_type=request.imageMimeType or "image/jpeg",
            width=None,
            height=None,
        )
        if photo.storage_bucket != "cloudinary" or not photo.storage_path.startswith("https://"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to upload Flirtist screenshot to Cloudinary.",
            )
        return FlirtistStoredImage(
            url=photo.storage_path,
            storage_path=photo.storage_path,
            mime_type=photo.mime_type or request.imageMimeType or "image/jpeg",
        )
