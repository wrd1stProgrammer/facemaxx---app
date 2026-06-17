from fastapi import APIRouter

from app.schemas.flirtist import (
    FlirtistChatRequest,
    FlirtistDraftRequest,
    FlirtistGenerateRequest,
    FlirtistGoalRequest,
    FlirtistOCRRequest,
    FlirtistProfileRequest,
    FlirtistResponse,
)
from app.schemas.flirtist_product import (
    FlirtistCoachChatRequest,
    FlirtistCoachChatResponse,
    FlirtistProductSessionRequest,
    FlirtistProductSessionResponse,
    FlirtistReplyStyleRequest,
    FlirtistReplyStyleResponse,
)
from app.services.flirtist_product_service import FlirtistProductService
from app.services.flirtist_service import FlirtistService

router = APIRouter(prefix="/api/flirtist", tags=["flirtist"])


@router.post("/analyze-chat", response_model=FlirtistResponse)
async def analyze_chat(request: FlirtistChatRequest) -> FlirtistResponse:
    return FlirtistService().analyze_chat(request)


@router.post("/generate-replies", response_model=FlirtistResponse)
async def generate_replies(request: FlirtistGenerateRequest) -> FlirtistResponse:
    return FlirtistService().generate_replies(request)


@router.post("/check-draft", response_model=FlirtistResponse)
async def check_draft(request: FlirtistDraftRequest) -> FlirtistResponse:
    return FlirtistService().check_draft(request)


@router.post("/profile-coach", response_model=FlirtistResponse)
async def profile_coach(request: FlirtistProfileRequest) -> FlirtistResponse:
    return FlirtistService().profile_coach(request)


@router.post("/goal-coach", response_model=FlirtistResponse)
async def goal_coach(request: FlirtistGoalRequest) -> FlirtistResponse:
    return FlirtistService().goal_coach(request)


@router.post("/ocr-chat", response_model=FlirtistResponse)
async def ocr_chat(request: FlirtistOCRRequest) -> FlirtistResponse:
    return FlirtistService().ocr_chat(request)


@router.post("/sessions", response_model=FlirtistProductSessionResponse)
async def create_product_session(request: FlirtistProductSessionRequest) -> FlirtistProductSessionResponse:
    return FlirtistProductService().create_session(request)


@router.post("/reply-style", response_model=FlirtistReplyStyleResponse)
async def regenerate_reply_style(request: FlirtistReplyStyleRequest) -> FlirtistReplyStyleResponse:
    return FlirtistProductService().regenerate_reply(request)


@router.post("/coach-chat", response_model=FlirtistCoachChatResponse)
async def coach_chat(request: FlirtistCoachChatRequest) -> FlirtistCoachChatResponse:
    return FlirtistProductService().coach_chat(request)
