from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


AgentRoleID = Literal["trend", "pattern", "momentum", "risk", "devil"]
AgentConcept = Literal[
    "trend_following",
    "swing_structure",
    "breakout_retest",
    "support_resistance",
    "candlestick",
    "momentum",
    "mean_reversion",
    "volatility_breakout",
    "volume_price_action",
    "moving_average",
    "divergence",
    "market_structure",
    "liquidity_sweep",
    "false_breakout",
    "risk_invalidation",
    "risk_reward",
    "reversal",
    "range_trading",
    "pullback",
    "contrarian",
]
AgentAppearanceID = Literal[
    "default_trendy",
    "default_patty",
    "default_momo",
    "default_gadi",
    "default_devil",
    "neo_quant",
    "classic_strategist",
]
ResponseLanguage = Literal[
    "en-US",
    "en",
    "ko",
    "ja",
    "de",
    "fr-FR",
    "es-MX",
    "pt-BR",
    "zh-Hant",
    "id",
    "th",
    "zh-Hans",
    "vi",
    "it",
    "tr",
    "es-ES",
    "fr-CA",
]
PRICE_LEVEL_PATTERN = r"^\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:-|–|~)\s*\d[\d,]*(?:\.\d+)?)?\s*$"


def normalize_response_language(identifier: str) -> ResponseLanguage:
    normalized = identifier.strip().replace("_", "-").lower()
    if normalized.startswith("ko"):
        return "ko"
    if normalized.startswith("ja"):
        return "ja"
    if normalized.startswith("de"):
        return "de"
    if normalized.startswith("fr-ca"):
        return "fr-CA"
    if normalized.startswith("fr"):
        return "fr-FR"
    if normalized.startswith("es-mx"):
        return "es-MX"
    if normalized.startswith("es"):
        return "es-ES"
    if normalized.startswith("pt"):
        return "pt-BR"
    if normalized.startswith("zh"):
        traditional = any(token in normalized for token in ("hant", "-tw", "-hk", "-mo"))
        return "zh-Hant" if traditional else "zh-Hans"
    if normalized.startswith("id"):
        return "id"
    if normalized.startswith("th"):
        return "th"
    if normalized.startswith("vi"):
        return "vi"
    if normalized.startswith("it"):
        return "it"
    if normalized.startswith("tr"):
        return "tr"
    if normalized == "en":
        return "en"
    return cast(ResponseLanguage, "en-US")


class APIModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AgentCustomization(APIModel):
    role_id: AgentRoleID
    display_name: str = Field(min_length=1, max_length=10)
    tone: str = Field(min_length=1, max_length=20)
    concept: AgentConcept
    appearance_id: AgentAppearanceID

    @field_validator("display_name", "tone")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(unicodedata.category(character).startswith("C") for character in normalized):
            raise ValueError("custom text must not contain control characters")
        return normalized


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
    stance_code: Literal["bullish", "bearish", "observe", "neutral"]
    stance: str = Field(min_length=1, max_length=12)
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


class NewsImpact(APIModel):
    collected_count: int = Field(ge=0, le=20)
    used_count: int = Field(ge=0, le=20)
    effect: Literal["reinforced", "softened", "changed", "none"]
    summary: str = Field(min_length=5, max_length=300)
    used_titles: list[str] = Field(max_length=20)


class TradePlan(APIModel):
    direction_code: Literal["bullish", "bearish", "observe", "neutral"]
    reference_price: str = Field(min_length=1, max_length=40, pattern=PRICE_LEVEL_PATTERN)
    entry: str = Field(min_length=1, max_length=60, pattern=PRICE_LEVEL_PATTERN)
    stop: str = Field(min_length=1, max_length=60, pattern=PRICE_LEVEL_PATTERN)
    target: str = Field(min_length=1, max_length=60, pattern=PRICE_LEVEL_PATTERN)
    risk_reward: str = Field(min_length=1, max_length=20)
    trigger: str = Field(min_length=10, max_length=180)
    rationale: str = Field(min_length=15, max_length=260)

    @model_validator(mode="after")
    def entry_must_not_copy_reference_price(self) -> TradePlan:
        reference_number = _first_number(self.reference_price)
        entry_number = _first_number(self.entry)
        stop_number = _first_number(self.stop)
        target_number = _first_number(self.target)
        same_numeric_level = (
            reference_number is not None
            and entry_number is not None
            and reference_number == entry_number
        )
        same_relative_level = _normalized_level(self.reference_price) == _normalized_level(self.entry)
        if same_numeric_level or same_relative_level:
            raise ValueError("entry must be a distinct pullback, retest, or confirmed-break level")
        ratio_match = re.search(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", self.risk_reward)
        if ratio_match is None:
            raise ValueError("risk_reward must use a numeric risk:reward ratio")
        risk = Decimal(ratio_match.group(1))
        reward = Decimal(ratio_match.group(2))
        if risk <= 0 or reward / risk < Decimal("1.8"):
            raise ValueError("reward-to-risk must be at least 1.8")

        if all(value is not None for value in (reference_number, entry_number, stop_number, target_number)):
            reference = cast(Decimal, reference_number)
            entry = cast(Decimal, entry_number)
            stop = cast(Decimal, stop_number)
            target = cast(Decimal, target_number)
            if self.direction_code == "bearish":
                if entry < reference:
                    raise ValueError("bearish entry must be at or above the displayed current price")
                if stop <= entry or target >= entry:
                    raise ValueError("bearish stop must be above entry and target below entry")
            elif self.direction_code == "bullish":
                if entry > reference:
                    raise ValueError("bullish entry must be at or below the displayed current price")
                if stop >= entry or target <= entry:
                    raise ValueError("bullish stop must be below entry and target above entry")

            if self.direction_code in {"bearish", "bullish"}:
                numeric_risk = abs(entry - stop)
                numeric_reward = abs(target - entry)
                if numeric_risk <= 0 or numeric_reward / numeric_risk < Decimal("1.8"):
                    raise ValueError(
                        "numeric trade levels must provide at least 1.8 reward-to-risk; "
                        f"entry={entry}, stop={stop}, target={target}, risk={numeric_risk}, "
                        f"reward={numeric_reward}, required_reward>={numeric_risk * Decimal('1.8')}"
                    )
        return self


class AnalysisContent(APIModel):
    consensus: Consensus
    scope: AnalysisScope
    agent_opinions: list[AgentOpinion] = Field(min_length=3, max_length=5)
    scenarios: list[Scenario] = Field(min_length=2, max_length=4)
    structure: list[StructureLevel] = Field(min_length=2, max_length=4)
    meeting_script: list[MeetingLine] = Field(min_length=3, max_length=8)
    data_quality: DataQuality
    trade_plan: TradePlan
    follow_up_suggestions: list[str] = Field(min_length=2, max_length=4)


class AnalysisPayload(AnalysisContent):
    validation: ChartValidation
    news_impact: NewsImpact


class AnalysisRequestContext(APIModel):
    include_news: bool
    active_agent_ids: list[AgentRoleID] = Field(min_length=3, max_length=5)
    response_language: ResponseLanguage = "en-US"
    agent_customizations: list[AgentCustomization] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def customization_roles_must_be_unique_and_active(self) -> AnalysisRequestContext:
        role_ids = [profile.role_id for profile in self.agent_customizations]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("agent customization role ids must be unique")
        if not set(role_ids).issubset(self.active_agent_ids):
            raise ValueError("agent customizations must target active agents")
        return self


class AnalysisResponse(APIModel):
    id: str
    created_at: datetime
    provider: Literal["codex_cli", "openai_fallback"]
    symbol: SymbolInfo
    timeframe: str
    included_news: bool
    result: AnalysisPayload
    news: list[NewsItem]
    agent_profiles: list[AgentCustomization] = Field(default_factory=list, max_length=5)

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
        agent_profiles: list[AgentCustomization] | None = None,
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
            agent_profiles=agent_profiles or [],
        )


class AnalysisJobAccepted(APIModel):
    job_id: str
    status: Literal["pending"] = "pending"


class ErrorResponse(APIModel):
    code: str
    message: str
    recovery: str | None


class AnalysisJobSnapshot(APIModel):
    job_id: str
    status: Literal["pending", "completed", "failed"]
    result: AnalysisResponse | None = None
    error: ErrorResponse | None = None

    @model_validator(mode="after")
    def payload_matches_status(self) -> AnalysisJobSnapshot:
        if self.status == "completed" and self.result is None:
            raise ValueError("completed analysis job requires a result")
        if self.status == "failed" and self.error is None:
            raise ValueError("failed analysis job requires an error")
        return self


class FollowUpHistoryItem(APIModel):
    agent_id: Literal["trend", "pattern", "momentum", "risk", "devil"]
    question: str = Field(min_length=2, max_length=800)
    answer: str = Field(min_length=10, max_length=1400)


class FollowUpRequest(APIModel):
    agent_id: Literal["trend", "pattern", "momentum", "risk", "devil"]
    question: str = Field(min_length=2, max_length=800)
    analysis: AnalysisResponse
    history: list[FollowUpHistoryItem] = Field(default_factory=list, max_length=12)
    response_language: ResponseLanguage = "en-US"
    agent_profile: AgentCustomization | None = None


class FollowUpPayload(APIModel):
    agent_id: Literal["trend", "pattern", "momentum", "risk", "devil"]
    answer: str = Field(min_length=10, max_length=1400)
    caveat: str = Field(min_length=5, max_length=300)


class FollowUpResponse(FollowUpPayload):
    provider: Literal["codex_cli", "openai_fallback"]


def _first_number(value: str) -> Decimal | None:
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value)
    if match is None:
        return None
    try:
        return Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None


def _normalized_level(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())
