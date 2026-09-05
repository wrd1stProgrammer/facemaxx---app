import asyncio
from uuid import uuid4
import httpx
import pytest
from app import product_analytics as product
from app.analysis_jobs import AnalysisJobManager
from app.config import Settings
from app.errors import AnalysisUnavailableError, DependencyError


def headers():
    return {"x-chartagent-analytics": "1", "x-chartagent-attempt-id": str(uuid4()).upper(),
            "x-posthog-distinct-id": str(uuid4()), "x-posthog-session-id": str(uuid4()),
            "x-chartagent-analytics-environment": "development", "x-chartagent-app-version": "1.0.3"}


def test_old_clients_and_invalid_identity_do_not_enable_analytics():
    assert product.AnalyticsContext.from_headers({}) is None
    values = headers()
    assert product.AnalyticsContext.from_headers(values).attempt_id == values["x-chartagent-attempt-id"]
    values["x-posthog-distinct-id"] = "someone@example.com"
    assert product.AnalyticsContext.from_headers(values) is None


def test_dependency_status_does_not_include_response_body():
    response = httpx.Response(429, request=httpx.Request("GET", "https://example.test"), text="secret")
    try:
        response.raise_for_status()
    except httpx.HTTPError as cause:
        try:
            raise DependencyError("private provider context") from cause
        except DependencyError as error:
            assert product.error_code(error) == "http_429"


@pytest.mark.anyio
async def test_background_context_and_private_fields(monkeypatch):
    captured = []
    original_client = httpx.AsyncClient
    def receive(request):
        import json
        captured.extend(json.loads(request.content)["batch"])
        return httpx.Response(200, json={"status": "ok"})
    monkeypatch.setattr(product.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(receive), **kwargs))
    sender = product.ProductAnalytics(Settings(posthog_project_token="phc_test"))
    monkeypatch.setattr("app.analysis_jobs.analytics", sender)
    ready = asyncio.Event()
    async def work():
        await ready.wait()
        sender.capture("news_fetch_finished", status="empty", question="private", image="private")
        raise AnalysisUnavailableError()
    context = product.AnalyticsContext.from_headers(headers())
    token = product.current_context.set(context)
    manager = AnalysisJobManager()
    job_id = manager.submit(work)
    product.current_context.reset(token)
    ready.set()
    await asyncio.gather(*manager._tasks)
    await sender.close()
    assert [event["event"] for event in captured] == ["chartagent_news_fetch_finished", "chartagent_analysis_job_finished"]
    assert captured[1]["properties"]["job_id"] == job_id
    assert captured[1]["properties"]["attempt_id"] == context.attempt_id
    assert captured[1]["properties"]["status"] == "failed"
    assert "question" not in captured[0]["properties"] and "image" not in captured[0]["properties"]


@pytest.mark.anyio
async def test_opt_out_propagates_to_running_job(monkeypatch):
    sender = product.ProductAnalytics(Settings(posthog_project_token="phc_test"))
    monkeypatch.setattr("app.analysis_jobs.analytics", sender)
    ready = asyncio.Event()
    async def work():
        await ready.wait()
        raise AnalysisUnavailableError()
    context = product.AnalyticsContext.from_headers(headers())
    token = product.current_context.set(context)
    manager = AnalysisJobManager()
    job_id = manager.submit(work)
    product.current_context.reset(token)
    manager.disable_analytics(job_id, "wrong-attempt")
    assert context.enabled
    manager.disable_analytics(job_id, context.attempt_id)
    ready.set()
    await asyncio.gather(*manager._tasks)
    assert not context.enabled and sender.queue.empty() and sender.task is None


@pytest.mark.anyio
async def test_delivery_outage_does_not_raise(monkeypatch):
    original_client = httpx.AsyncClient
    def fail(request):
        raise httpx.ConnectError("offline", request=request)
    monkeypatch.setattr(product.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(fail), **kwargs))
    sender = product.ProductAnalytics(Settings(posthog_project_token="phc_test"))
    token = product.current_context.set(product.AnalyticsContext.from_headers(headers()))
    sender.capture("analysis_job_finished", status="completed")
    product.current_context.reset(token)
    await sender.close()
    assert sender.queue.empty()
