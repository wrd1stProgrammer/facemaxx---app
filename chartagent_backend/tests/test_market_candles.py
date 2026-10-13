from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_candles_reject_unsupported_timeframe() -> None:
    # Given / When
    response = TestClient(app).get(
        "/v1/market/candles", params={"symbol": "NASDAQ:AAPL", "timeframe": "2m"}
    )
    # Then
    assert response.status_code == 422


def test_candles_contract_sorts_deduplicates_and_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    from app.market_candles import candle_service

    async def transport(request: httpx.Request) -> httpx.Response:
        bars = [
            {"time": t, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 5}
            for t in range(1000, 1601)
        ]
        return httpx.Response(200, json={"series": list(reversed(bars)) + [bars[0]]})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            **{**kwargs, "transport": httpx.MockTransport(transport)}
        ),
    )
    monkeypatch.setattr(
        candle_service.market.settings, "insightsentry_api_key", "test-key"
    )
    candle_service.cache.clear()
    client = TestClient(app)
    # When
    response = client.get(
        "/v1/market/candles",
        params={"symbol": "NASDAQ:AAPL", "timeframe": "1d", "before": 1550},
    )
    # Then
    assert response.status_code == 200
    payload = response.json()
    assert [row["time"] for row in payload["candles"]] == list(range(1050, 1550))
    assert payload["has_more"] is True
    assert set(payload["candles"][0]) == {
        "time",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }


def test_intraday_cursor_loads_previous_month(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.market_candles import candle_service

    requested_months: list[str] = []

    async def transport(request: httpx.Request) -> httpx.Response:
        month = request.url.params["start_date"]
        requested_months.append(month)
        bars = (
            []
            if month == "2026-09"
            else [{"time": 1788134400, "open": 10, "high": 12, "low": 9, "close": 11}]
        )
        assert request.url.params["bar_type"] == "hour"
        assert request.url.params["bar_interval"] == "4"
        return httpx.Response(200, json={"series": bars})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            **{**kwargs, "transport": httpx.MockTransport(transport)}
        ),
    )
    monkeypatch.setattr(
        candle_service.market.settings, "insightsentry_api_key", "test-key"
    )
    candle_service.cache.clear()
    response = TestClient(app).get(
        "/v1/market/candles",
        params={"symbol": "NASDAQ:AAPL", "timeframe": "4h", "before": 1788220801},
    )
    assert response.status_code == 200
    assert requested_months == ["2026-09", "2026-08"]
    assert response.json()["candles"][0]["volume"] == 0


def test_dependency_failure_is_not_empty_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.market_candles import candle_service

    async def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            **{**kwargs, "transport": httpx.MockTransport(transport)}
        ),
    )
    monkeypatch.setattr(
        candle_service.market.settings, "insightsentry_api_key", "test-key"
    )
    candle_service.cache.clear()
    response = TestClient(app).get(
        "/v1/market/candles", params={"symbol": "NASDAQ:AAPL"}
    )
    assert response.status_code == 503
    assert response.json()["code"] == "dependency_unavailable"
