from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import Field, field_validator

from app.schemas.common import FacemaxxBaseModel


OnboardingGoalID = Literal[
    "symmetry",
    "jawline",
    "skin",
    "glow",
    "proportions",
    "progress",
    "photos",
    "profile",
]
OnboardingGenderID = Literal["male", "female", "other"]
OnboardingAgeRangeID = Literal["18-24", "25-34", "35-44", "45+"]
OnboardingLocale = Literal[
    "en",
    "ko",
    "ja",
    "de",
    "es-419",
    "zh-Hant",
    "pt-BR",
    "fr",
    "it",
    "id",
    "tr",
    "ar",
]


class OnboardingPreferencesRequest(FacemaxxBaseModel):
    selected_goal_ids: list[OnboardingGoalID] = Field(default_factory=list, max_length=7)
    gender_id: Optional[OnboardingGenderID] = None
    age: Optional[int] = Field(default=None, ge=13, le=70)
    age_range_id: Optional[OnboardingAgeRangeID] = None
    locale: OnboardingLocale = "en"
    completed_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("selected_goal_ids")
    @classmethod
    def dedupe_selected_goal_ids(cls, values: list[OnboardingGoalID]) -> list[OnboardingGoalID]:
        deduped: list[OnboardingGoalID] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped


class OnboardingPreferencesResponse(FacemaxxBaseModel):
    selected_goal_ids: list[str] = Field(default_factory=list)
    gender_id: Optional[str] = None
    age: Optional[int] = None
    age_range_id: Optional[str] = None
    locale: Optional[str] = None
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    persisted: bool = False
