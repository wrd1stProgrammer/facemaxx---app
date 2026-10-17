import json
import logging
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


class ContentReport(BaseModel):
    analysis_id: str = Field(max_length=100)
    reason: str = Field(min_length=3, max_length=2000)
    content: str = Field(max_length=20000)


@router.post("/v1/content-reports", status_code=201)
async def report_content(report: ContentReport) -> dict[str, str]:
    report_id = str(uuid4())
    logger.warning("ChartAgent content report %s", json.dumps(
        {"report_id": report_id, **report.model_dump()}, ensure_ascii=True,
    ))
    return {"report_id": report_id, "status": "received"}
