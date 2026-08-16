from __future__ import annotations

import logging
import json
from pathlib import Path
import tempfile

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import ORJSONResponse

from app.analysis_service import AnalysisService
from app.analysis_jobs import AnalysisJobManager
from app.config import get_settings
from app.errors import ChartAgentError
from app.image_validation import validate_image_bytes
from app.insightsentry import InsightSentryClient
from app.providers.codex_cli import CodexCLIProvider
from app.providers.openai_api import OpenAIAPIProvider
from app.schemas import (
    AgentCustomization,
    AnalysisJobAccepted,
    AnalysisJobSnapshot,
    AnalysisRequestContext,
    AnalysisResponse,
    ErrorResponse,
    FollowUpRequest,
    FollowUpResponse,
    SymbolSearchResponse,
    normalize_response_language,
)


_AGENT_IDS = {"trend", "pattern", "momentum", "risk", "devil"}
LOGGER = logging.getLogger(__name__)
settings = get_settings()
market_data = InsightSentryClient(settings)
service = AnalysisService(
    market_data=market_data,
    codex=CodexCLIProvider(settings),
    fallback=OpenAIAPIProvider(settings),
)
analysis_jobs = AnalysisJobManager()

app = FastAPI(
    title="ChartAgent API",
    version="1.0.0",
    default_response_class=ORJSONResponse,
)


@app.exception_handler(ChartAgentError)
async def chartagent_error_handler(_: Request, error: ChartAgentError) -> ORJSONResponse:
    payload = ErrorResponse(code=error.code, message=error.message, recovery=error.recovery)
    return ORJSONResponse(status_code=error.status_code, content=payload.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, error: Exception) -> ORJSONResponse:
    LOGGER.error(
        "Unhandled ChartAgent request error",
        exc_info=(type(error), error, error.__traceback__),
    )
    payload = ErrorResponse(
        code="internal_error",
        message="분석 서버가 응답을 완료하지 못했습니다.",
        recovery="잠시 후 같은 입력으로 다시 시도해 주세요.",
    )
    return ORJSONResponse(status_code=500, content=payload.model_dump(mode="json"))


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "chartagent",
        "codex_model": settings.codex_model,
        "codex_reasoning_effort": settings.codex_reasoning_effort,
        "openai_fallback_configured": bool(settings.openai_api_key),
        "insightsentry_configured": settings.insightsentry_connection is not None,
    }


@app.get("/v1/symbols/search", response_model=SymbolSearchResponse)
async def search_symbols(query: str = Query(min_length=2, max_length=50)) -> SymbolSearchResponse:
    return SymbolSearchResponse(symbols=await market_data.search_symbols(query.strip()))


@app.post(
    "/v1/analyses",
    response_model=AnalysisResponse,
    responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def create_analysis(
    image: UploadFile = File(),
    include_news: bool = Form(default=False),
    active_agent_ids: str = Form(default="trend,pattern,momentum,risk,devil"),
    locale: str = Form(default="en-US"),
    agent_profiles: str = Form(default="[]"),
) -> AnalysisResponse:
    context = _analysis_context(
        include_news=include_news,
        active_agent_ids=active_agent_ids,
        locale=locale,
        agent_profiles=agent_profiles,
    )
    data = await image.read()
    image_format = validate_image_bytes(data, max_bytes=settings.max_image_bytes)
    return await _analyze_uploaded_data(data=data, image_format=image_format, context=context)


@app.post(
    "/v1/analysis-jobs",
    response_model=AnalysisJobAccepted,
    status_code=202,
    responses={422: {"model": ErrorResponse}},
)
async def create_analysis_job(
    image: UploadFile = File(),
    include_news: bool = Form(default=False),
    active_agent_ids: str = Form(default="trend,pattern,momentum,risk,devil"),
    locale: str = Form(default="en-US"),
    agent_profiles: str = Form(default="[]"),
) -> AnalysisJobAccepted:
    context = _analysis_context(
        include_news=include_news,
        active_agent_ids=active_agent_ids,
        locale=locale,
        agent_profiles=agent_profiles,
    )
    data = await image.read()
    image_format = validate_image_bytes(data, max_bytes=settings.max_image_bytes)
    job_id = analysis_jobs.submit(
        lambda: _analyze_uploaded_data(data=data, image_format=image_format, context=context)
    )
    return AnalysisJobAccepted(job_id=job_id)


@app.get("/v1/analysis-jobs/{job_id}", response_model=AnalysisJobSnapshot)
async def get_analysis_job(job_id: str) -> AnalysisJobSnapshot:
    return analysis_jobs.get(job_id)


def _analysis_context(
    *,
    include_news: bool,
    active_agent_ids: str,
    locale: str,
    agent_profiles: str,
) -> AnalysisRequestContext:
    requested_agents = [value.strip() for value in active_agent_ids.split(",") if value.strip()]
    if not 3 <= len(requested_agents) <= 5 or len(set(requested_agents)) != len(requested_agents) or not set(requested_agents).issubset(_AGENT_IDS):
        from app.errors import InvalidChartError

        raise InvalidChartError("invalid_agents", "분석 에이전트 구성은 서로 다른 3~5명이어야 합니다.")
    from app.errors import InvalidChartError

    try:
        raw_profiles = json.loads(agent_profiles)
        parsed_profiles = [AgentCustomization.model_validate(item) for item in raw_profiles]
    except (json.JSONDecodeError, TypeError, ValueError):
        raise InvalidChartError("invalid_agent_profiles", "에이전트 커스터마이징 정보를 읽을 수 없습니다.") from None

    return AnalysisRequestContext(
        include_news=include_news,
        active_agent_ids=requested_agents,
        response_language=normalize_response_language(locale),
        agent_customizations=parsed_profiles,
    )


async def _analyze_uploaded_data(
    *,
    data: bytes,
    image_format: str,
    context: AnalysisRequestContext,
) -> AnalysisResponse:
    suffix = {"png": ".png", "webp": ".webp"}.get(image_format, ".jpg")
    with tempfile.TemporaryDirectory(prefix="chartagent-upload-") as temp_dir:
        image_path = Path(temp_dir) / f"chart{suffix}"
        image_path.write_bytes(data)
        return await service.analyze(context=context, image_path=image_path)


@app.post(
    "/v1/follow-ups",
    response_model=FollowUpResponse,
    responses={502: {"model": ErrorResponse}},
)
async def follow_up(request: FollowUpRequest) -> FollowUpResponse:
    # The original image is intentionally not retained server-side. The compact report is the evidence boundary.
    return await service.follow_up(request=request)
