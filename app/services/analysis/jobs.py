"""Opt-in resumable analyses. The legacy synchronous endpoint is unchanged."""

import logging
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
from starlette.concurrency import run_in_threadpool

from app.api.deps import RequestIdentity
from app.db.supabase import get_supabase_service_client
from app.repositories.analysis_repository import AnalysisRepository
from app.schemas.analysis import AnalysisRunResponse, CreateAnalysisRunRequest
from app.services.analysis.runner import AnalysisRunner

logger = logging.getLogger(__name__)


def trial_preview(response: AnalysisRunResponse) -> AnalysisRunResponse:
    """New aesthetics trials expose only measured rings, never paid result data."""
    if not (response.is_free_trial_result and response.mode_id == "aesthetics" and response.result):
        return response
    result = response.result.model_copy(update={
        "overall_score": None, "overall_progress": None,
        "potential_score": None, "potential_progress": None,
        "summary_text": None, "summary_key": None, "metrics": [],
        "growth_opportunities": [], "photo_rankings": [], "coach_items": [],
        "look_archetype": None,
    })
    return response.model_copy(update={"result": result})


class AnalysisJobs:
    def __init__(self, identity: RequestIdentity) -> None:
        self.identity = identity
        self.repository = AnalysisRepository()

    def get(self, run_id: UUID) -> AnalysisRunResponse:
        return trial_preview(self.repository.get_run(
            run_id, self.identity.user_id, self.identity.client_install_id,
        ))

    async def submit(self, run_id: UUID, request: CreateAnalysisRunRequest,
                     background: BackgroundTasks) -> AnalysisRunResponse:
        if get_supabase_service_client() is None:
            raise HTTPException(503, "Resumable analysis requires persistent storage")
        try:
            return await run_in_threadpool(self.get, run_id)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        try:
            await run_in_threadpool(
                self.repository.create_run,
                user_id=self.identity.user_id,
                client_install_id=self.identity.client_install_id,
                mode_id=request.mode_id, photo_id=request.photo_id,
                photo_ids=request.photo_ids, source=request.source,
                face_scan_capture_id=request.face_scan_capture_id,
                onboarding_context=request.onboarding_context, run_id=run_id,
            )
        except HTTPException as creation_error:
            # A duplicate PUT must never schedule a second provider call/charge.
            # Ownership-filtered lookup also rejects another install's UUID.
            try:
                return await run_in_threadpool(self.get, run_id)
            except HTTPException as lookup_error:
                if lookup_error.status_code == 404:
                    raise creation_error
                raise
        background.add_task(self.execute, run_id, request)
        return AnalysisRunResponse(id=run_id, mode_id=request.mode_id, status="processing")

    async def execute(self, run_id: UUID, request: CreateAnalysisRunRequest) -> None:
        try:
            await AnalysisRunner(pending_run_id=run_id).run(self.identity, request)
        except HTTPException as exc:
            await run_in_threadpool(self.repository.fail_run, run_id, str(exc.status_code))
            logger.warning("Analysis job rejected run_id=%s status=%s", run_id, exc.status_code)
        except Exception:  # noqa: BROAD_EXCEPT_OK -- background-task boundary; persist terminal failure.
            logger.exception("Analysis job failed run_id=%s", run_id)
            await run_in_threadpool(self.repository.fail_run, run_id, "502")
