from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class APIModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SymbolInfo(APIModel):
    code: str
    name: str
    instrument_type: str


class SymbolSearchResponse(APIModel):
    symbols: list[SymbolInfo]


class NewsItem(APIModel):
    title: str
    source: str
    published_at: int
    url: HttpUrl | None = None
    related_symbols: list[str] = Field(default_factory=list)
    relevance: str = ""


class ChartValidation(APIModel):
    is_chart: bool
    is_readable: bool
    # Retained for decoding analysis records produced before server-side auto-detection.
    symbol_matches: bool = True
    detected_symbol: str | None
    detected_timeframe: str | None = None
    reason_code: Literal["ok", "not_chart", "unreadable_chart", "symbol_mismatch", "missing_symbol", "missing_timeframe"]
    message: str


class Consensus(APIModel):
    title: str = Field(min_length=2, max_length=40)
    stance_code: Literal["bullish", "bearish", "observe", "neutral"]
    confidence: int = Field(ge=0, le=100)
    summary: str = Field(min_length=20, max_length=700)


class AnalysisScope(APIModel):
    visible: list[str] = Field(min_length=1, max_length=6)
    unavailable: list[str] = Field(max_length=6)


class AgentOpinion(APIModel):
    agent_id: Literal["trend", "pattern", "momentum", "risk", "devil"]
    stance: str = Field(min_length=1, max_length=24)
    confidence: int = Field(ge=0, le=100)
    thesis: str = Field(min_length=10, max_length=260)
    evidence: list[str] = Field(min_length=2, max_length=4)


class Scenario(APIModel):
    title: str
    condition: str
    action: str
    tone: Literal["mint", "amber", "coral", "blue", "violet"]


class StructureLevel(APIModel):
    label: str
    value: str
    note: str
    tone: Literal["mint", "amber", "coral", "blue", "violet"]


class MeetingLine(APIModel):
    stage: Literal["trend", "pattern", "momentum", "risk", "debate", "dissent", "synthesis"]
    agent_id: Literal["trend", "pattern", "momentum", "risk", "devil"]
    bubble: str = Field(min_length=4, max_length=100)
    log: str = Field(min_length=8, max_length=180)


class DataQuality(APIModel):
    chart: Literal["good", "partial", "poor"]
    price_axis: Literal["good", "partial", "missing"]
    timeframe: Literal["good", "provided", "missing"]
    news: Literal["included", "empty", "unused"]


class AnalysisPayload(APIModel):
    validation: ChartValidation
    consensus: Consensus
    scope: AnalysisScope
    agent_opinions: list[AgentOpinion] = Field(min_length=3, max_length=5)
    scenarios: list[Scenario] = Field(min_length=2, max_length=4)
    structure: list[StructureLevel] = Field(min_length=2, max_length=4)
    meeting_script: list[MeetingLine] = Field(min_length=3, max_length=8)
    data_quality: DataQuality
    follow_up_suggestions: list[str] = Field(min_length=2, max_length=4)


class AnalysisRequestContext(APIModel):
    include_news: bool
    active_agent_ids: list[Literal["trend", "pattern", "momentum", "risk", "devil"]] = Field(min_length=3, max_length=5)


class AnalysisResponse(APIModel):
    id: str
    created_at: datetime
    provider: Literal["codex_cli", "openai_fallback"]
    symbol: SymbolInfo
    timeframe: str
    included_news: bool
    result: AnalysisPayload
    news: list[NewsItem]

    @classmethod
    def create(
        cls,
        *,
        provider: Literal["codex_cli", "openai_fallback"],
        symbol: SymbolInfo,
        timeframe: str,
        included_news: bool,
        result: AnalysisPayload,
        news: list[NewsItem],
    ) -> AnalysisResponse:
        return cls(
            id=str(uuid4()),
            created_at=datetime.now(UTC),
            provider=provider,
            symbol=symbol,
            timeframe=timeframe,
            included_news=included_news,
            result=result,
            news=news,
        )


class FollowUpRequest(APIModel):
    agent_id: Literal["trend", "pattern", "momentum", "risk", "devil"]
    question: str = Field(min_length=2, max_length=800)
    analysis: AnalysisResponse


class FollowUpPayload(APIModel):
    agent_id: Literal["trend", "pattern", "momentum", "risk", "devil"]
    answer: str = Field(min_length=10, max_length=1400)
    caveat: str = Field(min_length=5, max_length=300)


class FollowUpResponse(FollowUpPayload):
    provider: Literal["codex_cli", "openai_fallback"]


class ErrorResponse(APIModel):
    code: str
    message: str
    recovery: str | None
