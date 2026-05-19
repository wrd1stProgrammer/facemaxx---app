from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.schemas.analysis import AnalysisResultPayload


@dataclass(frozen=True)
class ProviderPhotoInput:
    photo_id: UUID
    photo_url: str | None = None
    photo_bytes: bytes | None = None
    photo_mime_type: str | None = None


@dataclass(frozen=True)
class ProviderAnalysisRequest:
    user_id: str | None
    mode_id: str
    locale: str
    photo_id: UUID | None = None
    photo_ids: list[UUID] | None = None
    photo_url: str | None = None
    photo_bytes: bytes | None = None
    photo_mime_type: str | None = None
    photos: list[ProviderPhotoInput] | None = None
    face_scan_capture_id: UUID | None = None
    face_metrics: list[dict[str, Any]] | None = None
    onboarding_context: dict[str, Any] | None = None


class FaceAnalysisProvider(Protocol):
    name: str
    model_name: str | None

    async def analyze(self, request: ProviderAnalysisRequest) -> AnalysisResultPayload:
        ...
