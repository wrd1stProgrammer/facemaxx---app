from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudioMode(StrEnum):
    HAIRSTYLE = "hairstyle"
    BANGS = "bangs"
    HAIR_COLOR = "hair-color"
    GLASSES = "glasses"
    EYEBROWS = "eyebrows"
    BEARD = "beard"
    MAKEUP = "makeup"
    EYE_MAKEUP = "eye-makeup"
    LIP_COLOR = "lip-color"
    CLOTHING_COLOR = "clothing-color"
    SALON_CARD = "salon-card"


class StudioRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: UUID
    mode: StudioMode
    style: str = Field(min_length=1, max_length=160)
    photo_base64: str = Field(min_length=100, max_length=8_000_000)
    reference_base64: str | None = Field(default=None, max_length=8_000_000)
    locale: str = Field(default="en", max_length=16)


class SalonInstructions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consultation: str
    cut: str
    texture: str
    styling: str
    maintenance: str


class StudioResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    mode: StudioMode
    style: str
    image_base64: str
    salon: SalonInstructions | None = None
