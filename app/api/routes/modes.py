from fastapi import APIRouter

from app.repositories.analysis_repository import AnalysisRepository
from app.schemas.analysis import AnalysisModeOut

router = APIRouter(prefix="/analysis-modes", tags=["analysis-modes"])


@router.get("", response_model=list[AnalysisModeOut])
async def list_analysis_modes() -> list[dict]:
    return AnalysisRepository().list_modes()

