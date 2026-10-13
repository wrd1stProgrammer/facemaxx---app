from __future__ import annotations

from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Annotated, Final, Literal
from urllib.parse import quote

import anyio
import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings
from app.errors import ChartAgentError, DependencyError
from app.insightsentry import InsightSentryClient

Timeframe = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
INTERVALS: Final[dict[Timeframe, tuple[str, str]]] = {
    "1m": ("minute", "1"),
    "5m": ("minute", "5"),
    "15m": ("minute", "15"),
    "30m": ("minute", "30"),
    "1h": ("hour", "1"),
    "4h": ("hour", "4"),
    "1d": ("day", "1"),
    "1w": ("week", "1"),
}
PAGE_SIZE: Final = 500


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore", allow_inf_nan=False)
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0


class CandlePage(BaseModel):
    model_config = ConfigDict(frozen=True)
    candles: list[Candle]
    has_more: bool


class CandleQuery(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    symbol: str = Field(min_length=3, max_length=100, pattern=r"^[^\s/:]+:[^\s/]+$")
    timeframe: Timeframe = "1h"
    before: int | None = Field(default=None, gt=0, le=253402300799)


class _Series(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    series: list[Candle] = Field(default_factory=list)
    error: str | None = None


class CandleService:
    def __init__(self, market: InsightSentryClient) -> None:
        self.market = market
        self.cache: OrderedDict[
            tuple[str, tuple[tuple[str, str], ...]], tuple[float, _Series]
        ] = OrderedDict()
        self.limiter = anyio.CapacityLimiter(4)

    async def fetch(self, query: CandleQuery) -> CandlePage:
        bar_type, interval = INTERVALS[query.timeframe]
        params = {"bar_type": bar_type, "bar_interval": interval}
        path = f"/v3/symbols/{quote(query.symbol, safe='')}"
        try:
            with anyio.fail_after(25):
                async with self.limiter:
                    if query.before is None or bar_type in {"day", "week"}:
                        count = (
                            "30000" if query.before is not None else str(PAGE_SIZE + 1)
                        )
                        series = await self._request(
                            path + "/series", {**params, "dp": count}
                        )
                        rows = self._before(series, query.before)
                        return CandlePage(
                            candles=rows[-PAGE_SIZE:],
                            has_more=len(rows) > PAGE_SIZE,
                        )
                    period = datetime.fromtimestamp(query.before - 1, UTC).replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    )
                    for _ in range(3):
                        series = await self._request(
                            path + "/history",
                            {**params, "start_date": period.strftime("%Y-%m")},
                        )
                        rows = self._before(series, query.before)
                        if rows:
                            return CandlePage(candles=rows[-PAGE_SIZE:], has_more=True)
                        period = (period - timedelta(days=1)).replace(day=1)
                    return CandlePage(candles=[], has_more=False)
        except (httpx.HTTPError, ValidationError, TimeoutError) as error:
            raise DependencyError("InsightSentry 캔들") from error

    async def _request(self, path: str, params: dict[str, str]) -> _Series:
        key = (path, tuple(sorted(params.items())))
        cached = self.cache.get(key)
        if cached is not None and monotonic() - cached[0] < 60:
            self.cache.move_to_end(key)
            return cached[1]
        try:
            result = _Series.model_validate(await self.market._get(path, params))
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {400, 404, 422}:
                raise ChartAgentError(
                    "market_data_unavailable",
                    "이 종목의 캔들 데이터를 사용할 수 없습니다.",
                    422,
                    "다른 종목을 검색해 주세요.",
                ) from error
            raise
        if result.error is not None and result.error != "data_unavailable":
            raise DependencyError("InsightSentry 캔들")
        self.cache[key] = (monotonic(), result)
        self.cache.move_to_end(key)
        while len(self.cache) > 16:
            self.cache.popitem(last=False)
        return result

    @staticmethod
    def _before(series: _Series, before: int | None) -> list[Candle]:
        unique = {
            bar.time: bar
            for bar in series.series
            if before is None or bar.time < before
        }
        return sorted(unique.values(), key=lambda bar: bar.time)


router = APIRouter(prefix="/v1/market", tags=["market"])
candle_service = CandleService(InsightSentryClient(get_settings()))


@router.get("/candles", response_model=CandlePage)
async def get_candles(query: Annotated[CandleQuery, Query()]) -> CandlePage:
    return await candle_service.fetch(query)
