from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
import time
from uuid import uuid4

from app.product_analytics import AnalyticsContext, analytics, current_context
from app.errors import ChartAgentError
from app.schemas import AnalysisJobSnapshot, AnalysisResponse, ErrorResponse


LOGGER = logging.getLogger(__name__)
AnalysisWorker = Callable[[], Awaitable[AnalysisResponse]]


@dataclass(slots=True)
class _StoredJob:
    created_at: float
    analytics_context: AnalyticsContext | None = None
    status: str = "pending"
    result: AnalysisResponse | None = None
    error: ErrorResponse | None = None


class AnalysisJobManager:
    def __init__(self, *, retention_seconds: float = 1_800) -> None:
        self.retention_seconds = retention_seconds
        self._jobs: dict[str, _StoredJob] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def submit(self, worker: AnalysisWorker) -> str:
        self._remove_expired()
        job_id = str(uuid4())
        self._jobs[job_id] = _StoredJob(created_at=time.monotonic(), analytics_context=current_context.get())
        task = asyncio.create_task(self._run(job_id, worker), name=f"chartagent-analysis-{job_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job_id

    def disable_analytics(self, job_id: str, attempt_id: str) -> None:
        job = self._jobs.get(job_id)
        if job and job.analytics_context and job.analytics_context.attempt_id.lower() == attempt_id.lower():
            job.analytics_context.enabled = False

    def get(self, job_id: str) -> AnalysisJobSnapshot:
        self._remove_expired()
        job = self._jobs.get(job_id)
        if job is None:
            return AnalysisJobSnapshot(
                job_id=job_id,
                status="failed",
                error=ErrorResponse(
                    code="analysis_job_expired",
                    message="분석 작업을 찾을 수 없습니다.",
                    recovery="같은 이미지로 분석을 다시 시작해 주세요.",
                ),
            )
        return AnalysisJobSnapshot(
            job_id=job_id,
            status=job.status,
            result=job.result,
            error=job.error,
        )

    async def _run(self, job_id: str, worker: AnalysisWorker) -> None:
        started_at = time.monotonic()
        job = self._jobs[job_id]
        try:
            job.result = await worker()
            job.status = "completed"
            LOGGER.info("Analysis job completed job_id=%s elapsed_seconds=%.2f", job_id, time.monotonic() - started_at)
        except ChartAgentError as error:
            job.status = "failed"
            job.error = ErrorResponse(code=error.code, message=error.message, recovery=error.recovery)
            LOGGER.warning(
                "Analysis job failed job_id=%s code=%s elapsed_seconds=%.2f",
                job_id,
                error.code,
                time.monotonic() - started_at,
            )
        except Exception:  # noqa: BLE001 - background task must preserve a pollable failure
            job.status = "failed"
            job.error = ErrorResponse(
                code="internal_error",
                message="분석 서버가 응답을 완료하지 못했습니다.",
                recovery="잠시 후 같은 입력으로 다시 시도해 주세요.",
            )
            LOGGER.exception(
                "Unhandled analysis job failure job_id=%s elapsed_seconds=%.2f",
                job_id,
                time.monotonic() - started_at,
            )

        finally:
            properties = {"job_id": job_id, "status": job.status, "duration_ms": int((time.monotonic() - started_at) * 1000)}
            if job.result is not None:
                properties.update(analysis_id=job.result.id, provider=job.result.provider, article_count=len(job.result.news))
            if job.error is not None:
                properties.update(error_code=job.error.code, error_stage="analysis")
            analytics.capture("analysis_job_finished", **properties)

    def _remove_expired(self) -> None:
        cutoff = time.monotonic() - self.retention_seconds
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status != "pending" and job.created_at < cutoff
        ]
        for job_id in expired:
            del self._jobs[job_id]
