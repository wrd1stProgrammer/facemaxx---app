from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, field_validator

from app.schemas.common import FacemaxxBaseModel


HabitdotLocale = Literal["ko", "en"]


class HabitdotRecentDay(FacemaxxBaseModel):
    date: str = Field(min_length=1, max_length=32)
    completed: bool = False
    count: Optional[int] = Field(default=None, ge=0, le=100)

    @field_validator("date", mode="before")
    @classmethod
    def strip_date(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class HabitdotHabit(FacemaxxBaseModel):
    title: str = Field(min_length=1, max_length=60)
    purpose: Optional[str] = Field(default=None, max_length=160)
    color_hex: Optional[str] = Field(default=None, max_length=16)
    completed_today: Optional[bool] = None
    completed_yesterday: Optional[bool] = None
    current_streak: Optional[int] = Field(default=None, ge=0, le=10000)
    weekly_completion_count: Optional[int] = Field(default=None, ge=0, le=7)
    recent_7_days: list[HabitdotRecentDay] = Field(default_factory=list, max_length=7)

    @field_validator("title", "purpose", "color_hex", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value


class HabitdotMotivationRequest(FacemaxxBaseModel):
    locale: HabitdotLocale = "ko"
    date: str = Field(min_length=1, max_length=32)
    habits: list[HabitdotHabit] = Field(default_factory=list, max_length=10)

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_locale(cls, value: str | None) -> str:
        normalized = (value or "ko").strip().lower().replace("_", "-")
        if normalized.startswith("ko"):
            return "ko"
        if normalized.startswith("en"):
            return "en"
        return normalized

    @field_validator("date", mode="before")
    @classmethod
    def strip_date(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class HabitdotMotivationResponse(FacemaxxBaseModel):
    text: str
    provider: Literal["gemini", "fallback"]
    model_name: Optional[str] = None
    generated_at: datetime
