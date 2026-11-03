from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.api.deps import RequestIdentity, get_request_identity
from app.repositories.analysis_repository import AnalysisRepository
from app.schemas.analysis import AnalysisRunResponse, AnalysisRunSummaryResponse, CreateAnalysisRunRequest
from app.services.analysis.runner import AnalysisRunner
from app.services.analysis.jobs import AnalysisJobs, trial_preview
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/analysis-runs", tags=["analysis-runs"])


@router.put("/jobs/{run_id}", response_model=AnalysisRunResponse)
async def submit_analysis_job(
    run_id: UUID, request: CreateAnalysisRunRequest, background: BackgroundTasks,
    identity: RequestIdentity = Depends(get_request_identity),
) -> AnalysisRunResponse:
    return await AnalysisJobs(identity).submit(run_id, request, background)


@router.get("/jobs/{run_id}", response_model=AnalysisRunResponse)
async def get_analysis_job(
    run_id: UUID, identity: RequestIdentity = Depends(get_request_identity),
) -> AnalysisRunResponse:
    return await run_in_threadpool(AnalysisJobs(identity).get, run_id)


@router.post("", response_model=AnalysisRunResponse)
async def create_analysis_run(
    request: CreateAnalysisRunRequest,
    identity: RequestIdentity = Depends(get_request_identity),
) -> AnalysisRunResponse:
    return await AnalysisRunner().run(identity, request)


@router.get("", response_model=list[AnalysisRunSummaryResponse])
async def list_analysis_runs(
    limit: int = Query(default=60, ge=1, le=100),
    identity: RequestIdentity = Depends(get_request_identity),
) -> list[AnalysisRunSummaryResponse]:
    runs = AnalysisRepository().list_runs(
        user_id=identity.user_id,
        client_install_id=identity.client_install_id,
        limit=limit,
    )
    return [
        run.model_copy(update={"overall_score": None, "summary_text": None})
        if run.is_free_trial_result and run.mode_id == "aesthetics" else run
        for run in runs
    ]


@router.get("/{run_id}", response_model=AnalysisRunResponse)
async def get_analysis_run(
    run_id: UUID,
    identity: RequestIdentity = Depends(get_request_identity),
) -> AnalysisRunResponse:
    return trial_preview(AnalysisRepository().get_run(
        run_id=run_id,
        user_id=identity.user_id,
        client_install_id=identity.client_install_id,
    ))
