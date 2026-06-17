from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, field_validator

from app.schemas.common import FacemaxxBaseModel


FlirtistLanguage = Literal["en", "ko"]


class FlirtistMessage(FacemaxxBaseModel):
    speaker: Literal["me", "them", "user", "match", "system"] = "them"
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class FlirtistChatRequest(FacemaxxBaseModel):
    language: Optional[FlirtistLanguage] = None
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    messages: list[FlirtistMessage] = Field(min_length=1, max_length=80)
    situation: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("locale", "situation", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class FlirtistGenerateRequest(FlirtistChatRequest):
    draft: Optional[str] = Field(default=None, max_length=1000)
    tone: Optional[str] = Field(default=None, max_length=64)


class FlirtistPickupLinesRequest(FacemaxxBaseModel):
    language: Optional[FlirtistLanguage] = None
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    situation: str = Field(min_length=1, max_length=2000)

    @field_validator("locale", "situation", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class FlirtistPickupLinesResponse(FacemaxxBaseModel):
    situation: str
    lines: list[str] = Field(min_length=20, max_length=20)
    language: FlirtistLanguage
    locale: str


class FlirtistDraftRequest(FacemaxxBaseModel):
    language: Optional[FlirtistLanguage] = None
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    draft: str = Field(min_length=1, max_length=2000)
    context: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("locale", "draft", "context", mode="before")
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class FlirtistProfileRequest(FacemaxxBaseModel):
    language: Optional[FlirtistLanguage] = None
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    bio: str = Field(min_length=1, max_length=2000)
    platform: str = Field(default="Hinge", max_length=64)
    photo_notes: Optional[str] = Field(default=None, max_length=2000)


class FlirtistGoalRequest(FacemaxxBaseModel):
    language: Optional[FlirtistLanguage] = None
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    goal: str = Field(min_length=1, max_length=500)
    context: Optional[str] = Field(default=None, max_length=2000)


class FlirtistOCRRequest(FacemaxxBaseModel):
    language: Optional[FlirtistLanguage] = None
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    imageBase64: Optional[str] = Field(default=None, max_length=6_000_000)
    text: Optional[str] = Field(default=None, max_length=5000)


class FlirtistResponse(FacemaxxBaseModel):
    summary: str
    interestScore: int = Field(ge=0, le=100)
    vibe: str
    riskFlags: list[str]
    nextMove: str
    recommendedAction: str
    replies: list[str]
    whyItWorks: list[str]
    improvedDraft: str
    profileSuggestions: list[str]
    confidenceScore: float = Field(ge=0, le=1)
    language: FlirtistLanguage
    locale: str
    aiObviousness: int = Field(ge=0, le=100)
    pressure: int = Field(ge=0, le=100)
    replyLikelihood: int = Field(ge=0, le=100)
