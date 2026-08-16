from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.analysis_jobs import AnalysisJobManager
from app.errors import AnalysisUnavailableError
from app.schemas import AnalysisPayload, AnalysisResponse, SymbolInfo


@pytest.mark.anyio
async def test_analysis_job_creation_returns_before_the_long_analysis_finishes() -> None:
    release_worker = asyncio.Event()

    async def slow_failure() -> None:
        await release_worker.wait()
        raise AnalysisUnavailableError()

    manager = AnalysisJobManager(retention_seconds=60)
    job_id = manager.submit(slow_failure)

    pending = manager.get(job_id)
    assert pending.status == "pending"
    assert pending.result is None
    assert pending.error is None

    release_worker.set()
    for _ in range(20):
        await asyncio.sleep(0)
        finished = manager.get(job_id)
        if finished.status != "pending":
            break

    assert finished.status == "failed"
    assert finished.error is not None
    assert finished.error.code == "analysis_unavailable"


@pytest.mark.anyio
async def test_analysis_job_endpoint_is_polled_until_the_result_is_ready(
    monkeypatch: pytest.MonkeyPatch,
    valid_payload: AnalysisPayload,
) -> None:
    from app import main

    expected = AnalysisResponse.create(
        provider="codex_cli",
        symbol=SymbolInfo(code="NASDAQ:AAPL", name="Apple", instrument_type="stock"),
        timeframe="1D",
        included_news=False,
        result=valid_payload,
        news=[],
    )

    async def fixed_analysis(**_: object) -> AnalysisResponse:
        return expected

    monkeypatch.setattr(main, "validate_image_bytes", lambda *_args, **_kwargs: "jpeg")
    monkeypatch.setattr(main, "_analyze_uploaded_data", fixed_analysis)
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        started = await client.post(
            "/v1/analysis-jobs",
            files={"image": ("chart.jpg", b"image", "image/jpeg")},
        )
        assert started.status_code == 202
        job_id = started.json()["job_id"]

        for _ in range(20):
            response = await client.get(f"/v1/analysis-jobs/{job_id}")
            if response.json()["status"] == "completed":
                break
            await asyncio.sleep(0)

    assert response.status_code == 200
    assert response.json()["result"]["id"] == expected.id
