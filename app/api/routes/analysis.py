from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import RequestIdentity, get_request_identity
from app.repositories.analysis_repository import AnalysisRepository
from app.schemas.analysis import AnalysisRunResponse, AnalysisRunSummaryResponse, CreateAnalysisRunRequest
from app.services.analysis.runner import AnalysisRunner

router = APIRouter(prefix="/analysis-runs", tags=["analysis-runs"])


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
    return AnalysisRepository().list_runs(
        user_id=identity.user_id,
        client_install_id=identity.client_install_id,
        limit=limit,
    )


@router.get("/{run_id}", response_model=AnalysisRunResponse)
async def get_analysis_run(
    run_id: UUID,
    identity: RequestIdentity = Depends(get_request_identity),
) -> AnalysisRunResponse:
    return AnalysisRepository().get_run(
        run_id=run_id,
        user_id=identity.user_id,
        client_install_id=identity.client_install_id,
    )
