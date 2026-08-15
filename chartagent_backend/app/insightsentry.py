from __future__ import annotations

import logging
import time
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import Settings
from app.errors import DependencyError
from app.schemas import NewsItem, SymbolInfo


LOGGER = logging.getLogger(__name__)
type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list[JSONValue] | dict[str, JSONValue]
type JSONObject = dict[str, JSONValue]


class _SymbolSearchItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str
    name: str = ""
    type: str = "unknown"


class _SymbolSearchPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    symbols: list[_SymbolSearchItem] = Field(default_factory=list)


class _SymbolInfoPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: str
    name: str = ""
    type: str = "unknown"


class _NewsRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = ""
    source: str = ""
    content: str = ""
    published_at: int
    link: str | None = None
    related_symbols: list[str] = Field(default_factory=list)


class _NewsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: list[_NewsRow] = Field(default_factory=list)


class InsightSentryClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search_symbols(self, query: str) -> list[SymbolInfo]:
        try:
            payload = await self._get("/v3/symbols/search", params={"query": query, "page": "1"})
        except httpx.HTTPError as error:
            raise DependencyError("InsightSentry") from error
        try:
            parsed = _SymbolSearchPayload.model_validate(payload)
        except ValidationError as error:
            raise DependencyError("InsightSentry") from error
        return [
            SymbolInfo(code=item.code, name=item.name or item.code, instrument_type=item.type)
            for item in parsed.symbols[:12]
        ]

    async def resolve_symbol(self, code: str) -> SymbolInfo | None:
        try:
            payload = await self._get(f"/v3/symbols/{quote(code, safe='')}/info")
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {400, 404, 422}:
                return None
            raise DependencyError("InsightSentry") from error
        try:
            item = _SymbolInfoPayload.model_validate(payload)
        except ValidationError as error:
            raise DependencyError("InsightSentry") from error
        return SymbolInfo(code=item.code, name=item.name or item.code, instrument_type=item.type)

    async def fetch_news(self, code: str) -> list[NewsItem]:
        try:
            payload = await self._get(
                "/v3/newsfeed",
                params={"related_symbols": code, "limit": "100", "page": "1"},
            )
        except httpx.HTTPError as error:
            raise DependencyError("InsightSentry 뉴스") from error
        try:
            rows = _NewsPayload.model_validate(payload).data
        except ValidationError as error:
            raise DependencyError("InsightSentry 뉴스") from error
        selected = _select_recent_news(rows)
        return [
            NewsItem(
                title=row.title or "제목 없음",
                source=row.source or "출처 미상",
                published_at=_published_seconds(row.published_at),
                url=row.link,
                related_symbols=row.related_symbols,
                relevance=row.content[:240],
            )
            for row in selected
        ]

    async def _get(self, path: str, params: dict[str, str] | None = None) -> JSONObject:
        connection = self.settings.insightsentry_connection
        if connection is None:
            raise DependencyError("InsightSentry")
        timeout = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(
            base_url=connection.base_url,
            headers=dict(connection.headers),
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            value = response.json()
        if not isinstance(value, dict):
            raise DependencyError("InsightSentry")
        return value


def _select_recent_news(
    rows: list[_NewsRow],
    *,
    now_timestamp: int | None = None,
) -> list[_NewsRow]:
    """Return at most 10 stories from 0–24h and 10 from 24–48h."""
    now = now_timestamp if now_timestamp is not None else int(time.time())
    deduplicated: list[_NewsRow] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda item: _published_seconds(item.published_at), reverse=True):
        identity = (row.title or row.link or "").strip().casefold()
        if not identity or identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(row)

    recent: list[_NewsRow] = []
    prior: list[_NewsRow] = []
    for row in deduplicated:
        age = now - _published_seconds(row.published_at)
        if age < 0:
            continue
        if age < 86_400:
            if len(recent) < 10:
                recent.append(row)
        elif age < 172_800:
            if len(prior) < 10:
                prior.append(row)
        if len(recent) == 10 and len(prior) == 10:
            break
    return recent + prior


def _published_seconds(value: int) -> int:
    return value // 1_000 if value > 10_000_000_000 else value
