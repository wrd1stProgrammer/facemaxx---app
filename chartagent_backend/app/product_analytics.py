from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import re
from collections.abc import Mapping
from uuid import UUID, uuid4

import httpx

from app.config import Settings


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AnalyticsContext:
    attempt_id: str
    distinct_id: str
    session_id: str
    environment: str
    app_version: str
    enabled: bool = True

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> AnalyticsContext | None:
        if headers.get("x-chartagent-analytics") != "1":
            return None
        try:
            ids = [headers.get(key, "") for key in (
                "x-chartagent-attempt-id", "x-posthog-distinct-id", "x-posthog-session-id"
            )]
            for value in ids:
                UUID(value)
        except (ValueError, AttributeError):
            return None
        environment = headers.get("x-chartagent-analytics-environment", "")
        version = headers.get("x-chartagent-app-version", "unknown")
        if environment not in {"development", "testflight", "production"}:
            return None
        if not re.fullmatch(r"[a-zA-Z0-9.\-]{1,32}", version):
            version = "unknown"
        return cls(*ids, environment, version)


current_context: ContextVar[AnalyticsContext | None] = ContextVar("product_analytics", default=None)


def error_code(error: BaseException) -> str:
    cause = error.__cause__ or error
    if isinstance(cause, httpx.HTTPStatusError):
        return f"http_{cause.response.status_code}"
    if isinstance(cause, httpx.TimeoutException):
        return "timeout"
    if isinstance(cause, httpx.HTTPError):
        return "network_error"
    code = getattr(error, "code", "internal_error")
    return code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,64}", code) else "internal_error"


class ProductAnalytics:
    def __init__(self, settings: Settings) -> None:
        self.token = settings.posthog_project_token
        self.host = settings.posthog_host
        self.enabled = bool(self.token and self.token.startswith("phc_") and self.host in {
            "https://us.i.posthog.com", "https://eu.i.posthog.com"
        })
        self.queue: asyncio.Queue[tuple[AnalyticsContext, dict]] = asyncio.Queue(maxsize=512)
        self.task: asyncio.Task | None = None

    def capture(self, event: str, **properties: object) -> None:
        context = current_context.get()
        if not self.enabled or context is None or not context.enabled:
            return
        allowed = {
            "job_id", "analysis_id", "status", "duration_ms", "error_code", "error_stage",
            "news_requested", "article_count", "used_count", "provider", "fetch_status",
            "assessment_status", "keyword_status", "normalized_symbol", "response_language",
        }
        safe = {key: value for key, value in properties.items() if key in allowed and (
            isinstance(value, (bool, int)) or isinstance(value, str) and len(value) <= 128
        )}
        safe.update({
            "distinct_id": context.distinct_id, "$session_id": context.session_id,
            "attempt_id": context.attempt_id, "environment": context.environment,
            "app_version": context.app_version, "event_schema_version": 1,
            "event_source": "backend", "$geoip_disable": True, "$process_person_profile": False,
        })
        payload = {"event": "chartagent_" + event, "uuid": str(uuid4()),
                   "timestamp": datetime.now(UTC).isoformat(), "properties": safe}
        try:
            self.queue.put_nowait((context, payload))
        except asyncio.QueueFull:
            LOGGER.warning("Product analytics queue full; dropping event")
            return
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._deliver(), name="chartagent-product-analytics")

    async def _deliver(self) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            while not self.queue.empty():
                batch = []
                count = 0
                while not self.queue.empty() and count < 20:
                    context, event = self.queue.get_nowait()
                    count += 1
                    if context.enabled:
                        batch.append(event)
                try:
                    if batch:
                        response = await client.post(self.host + "/batch/", json={"api_key": self.token, "batch": batch})
                        response.raise_for_status()
                except httpx.HTTPError:
                    LOGGER.warning("Product analytics batch delivery failed")
                finally:
                    for _ in range(count):
                        self.queue.task_done()

    async def close(self) -> None:
        if self.task is not None and not self.task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=2)
            except TimeoutError:
                self.task.cancel()
                await asyncio.gather(self.task, return_exceptions=True)


analytics = ProductAnalytics(Settings())
