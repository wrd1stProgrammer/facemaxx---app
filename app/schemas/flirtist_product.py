from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, field_validator

from app.schemas.common import FacemaxxBaseModel
from app.schemas.flirtist import FlirtistLanguage


FlirtistSessionMode = Literal["reply_coach", "score_analysis"]
FlirtistSessionSource = Literal["manual", "screenshot"]
FlirtistSessionContentKind = Literal["chat", "bio"]
FlirtistCoachRole = Literal["user", "assistant"]


class FlirtistPreviewMessage(FacemaxxBaseModel):
    role: Literal["me", "them", "system"] = "them"
    text: str = Field(min_length=1, max_length=1200)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class FlirtistProductSessionRequest(FacemaxxBaseModel):
    mode: FlirtistSessionMode
    source: FlirtistSessionSource
    language: Optional[FlirtistLanguage] = None
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    text: Optional[str] = Field(default=None, max_length=8000)
    imageBase64: Optional[str] = Field(default=None, max_length=8_000_000)
    imageMimeType: str = Field(default="image/png", max_length=64)

    @field_validator("locale", "text", "imageBase64", "imageMimeType", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class FlirtistReplyOption(FacemaxxBaseModel):
    id: str
    style: str
    text: str
    whyItWorks: str
    aiObviousness: int = Field(ge=0, le=100)
    pressure: int = Field(ge=0, le=100)
    replyLikelihood: int = Field(ge=0, le=100)


class FlirtistReplyPack(FacemaxxBaseModel):
    style: str = Field(min_length=2, max_length=40)
    label: str = Field(min_length=2, max_length=40)
    buttonTitle: str = Field(min_length=2, max_length=80)
    iconName: str = Field(min_length=2, max_length=60)
    replies: list[FlirtistReplyOption] = Field(min_length=1, max_length=8)


class FlirtistReplyCoaching(FacemaxxBaseModel):
    headline: str
    summary: str
    nextMove: str
    replies: list[FlirtistReplyOption] = Field(min_length=1, max_length=8)
    replyPacks: list[FlirtistReplyPack] = Field(default_factory=list, max_length=5)


class FlirtistInterestBreakdown(FacemaxxBaseModel):
    you: int = Field(ge=0, le=100)
    them: int = Field(ge=0, le=100)


class FlirtistMessageCount(FacemaxxBaseModel):
    you: int = Field(ge=0, le=1000)
    them: int = Field(ge=0, le=1000)


class FlirtistAnalysisCard(FacemaxxBaseModel):
    title: str
    messageCount: FlirtistMessageCount
    interestLevel: FlirtistInterestBreakdown
    meaningfulWordsYou: list[str] = Field(default_factory=list, max_length=8)
    meaningfulWordsThem: list[str] = Field(default_factory=list, max_length=8)
    redFlags: list[str] = Field(default_factory=list, max_length=8)
    greenFlags: list[str] = Field(default_factory=list, max_length=8)
    attachmentYou: str
    attachmentThem: str
    compatibilityScore: int = Field(ge=0, le=100)


class FlirtistProductSessionResponse(FacemaxxBaseModel):
    sessionId: str
    mode: FlirtistSessionMode
    source: FlirtistSessionSource
    contentKind: FlirtistSessionContentKind = "chat"
    title: str
    locale: str
    language: FlirtistLanguage
    createdAt: str
    saved: bool
    serverPersisted: bool
    imageUrl: Optional[str] = None
    imageStoragePath: Optional[str] = None
    chatPreview: list[FlirtistPreviewMessage]
    replyCoaching: Optional[FlirtistReplyCoaching] = None
    analysisCard: Optional[FlirtistAnalysisCard] = None


class FlirtistReplyStyleRequest(FacemaxxBaseModel):
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    language: Optional[FlirtistLanguage] = None
    sessionId: Optional[str] = Field(default=None, max_length=64)
    contentKind: FlirtistSessionContentKind = "chat"
    context: str = Field(min_length=1, max_length=8000)
    baseReply: str = Field(min_length=1, max_length=1200)
    style: str = Field(min_length=2, max_length=40)
    focus: Optional[str] = Field(default=None, max_length=120)
    existingReplies: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("existingReplies")
    @classmethod
    def clean_existing_replies(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        replies: list[str] = []
        for reply in value:
            cleaned = " ".join(reply.split())[:1200]
            if not cleaned or cleaned in seen:
                continue
            replies.append(cleaned)
            seen.add(cleaned)
        return replies[:40]


class FlirtistReplyStyleResponse(FacemaxxBaseModel):
    sessionId: str
    replyCoaching: FlirtistReplyCoaching


class FlirtistCoachMessage(FacemaxxBaseModel):
    role: FlirtistCoachRole
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class FlirtistCoachChatRequest(FacemaxxBaseModel):
    sessionId: Optional[str] = Field(default=None, max_length=64)
    language: Optional[FlirtistLanguage] = None
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    message: str = Field(min_length=1, max_length=4000)
    context: Optional[str] = Field(default=None, max_length=2000)
    history: list[FlirtistCoachMessage] = Field(default_factory=list, max_length=40)

    @field_validator("locale", "message", "context", mode="before")
    @classmethod
    def strip_text_fields(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class FlirtistCoachChatResponse(FacemaxxBaseModel):
    sessionId: str
    message: FlirtistCoachMessage
    suggestions: list[str] = Field(min_length=1, max_length=5)
    memorySummary: Optional[str] = Field(default=None, max_length=1200)
