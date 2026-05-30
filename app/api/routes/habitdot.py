from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Annotated, Deque
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import RequestIdentity
from app.repositories.habitdot_repository import HabitdotRepository
from app.schemas.habitdot import (
    HabitdotBugReportRequest,
    HabitdotFeedbackRequest,
    HabitdotMotivationRequest,
    HabitdotMotivationResponse,
    HabitdotOnboardingRequest,
    HabitdotPersistedResponse,
)
from app.services.habitdot_motivation import HabitdotMotivationService

router = APIRouter(prefix="/habitdot", tags=["habitdot"])

_REQUEST_LOGS: dict[str, Deque[datetime]] = defaultdict(deque)
_PER_MINUTE_LIMIT = 6
_PER_DAY_LIMIT = 40


@router.post("/motivation", response_model=HabitdotMotivationResponse)
async def create_habitdot_motivation(
    request: HabitdotMotivationRequest,
    raw_request: Request,
    x_facemaxx_install_id: Annotated[str | None, Header()] = None,
) -> HabitdotMotivationResponse:
    _enforce_rate_limit(_rate_limit_key(raw_request, x_facemaxx_install_id))
    return await HabitdotMotivationService().generate(request)


@router.post("/onboarding", response_model=HabitdotPersistedResponse)
async def save_habitdot_onboarding(
    request: HabitdotOnboardingRequest,
    raw_request: Request,
    x_facemaxx_install_id: Annotated[str | None, Header()] = None,
) -> HabitdotPersistedResponse:
    _enforce_rate_limit(f"onboarding:{_rate_limit_key(raw_request, x_facemaxx_install_id)}")
    identity = _install_identity(x_facemaxx_install_id)
    return HabitdotRepository().save_onboarding(
        identity=identity,
        request=request,
        inferred_country_code=_country_from_headers(raw_request),
    )


@router.post("/feedback", response_model=HabitdotPersistedResponse)
async def save_habitdot_feedback(
    request: HabitdotFeedbackRequest,
    raw_request: Request,
    x_facemaxx_install_id: Annotated[str | None, Header()] = None,
) -> HabitdotPersistedResponse:
    _enforce_rate_limit(f"feedback:{_rate_limit_key(raw_request, x_facemaxx_install_id)}")
    identity = _install_identity(x_facemaxx_install_id)
    return HabitdotRepository().save_feedback(
        identity=identity,
        request=request,
        inferred_country_code=_country_from_headers(raw_request),
    )


@router.post("/bugs", response_model=HabitdotPersistedResponse)
async def save_habitdot_bug_report(
    request: HabitdotBugReportRequest,
    raw_request: Request,
    x_facemaxx_install_id: Annotated[str | None, Header()] = None,
) -> HabitdotPersistedResponse:
    _enforce_rate_limit(f"bugs:{_rate_limit_key(raw_request, x_facemaxx_install_id)}")
    identity = _install_identity(x_facemaxx_install_id)
    return HabitdotRepository().save_bug_report(
        identity=identity,
        request=request,
        inferred_country_code=_country_from_headers(raw_request),
    )


def _install_identity(install_id: str | None) -> RequestIdentity:
    normalized = (install_id or "").strip()
    if not normalized:
        return RequestIdentity(user_id=None, client_install_id=None)

    try:
        return RequestIdentity(user_id=None, client_install_id=str(UUID(normalized)))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Facemaxx-Install-Id header",
        ) from exc


def _country_from_headers(request: Request) -> str | None:
    for header_name in (
        "cf-ipcountry",
        "x-vercel-ip-country",
        "cloudfront-viewer-country",
        "x-appengine-country",
    ):
        value = (request.headers.get(header_name) or "").strip().upper()
        if value and value not in {"XX", "T1"}:
            return value[:8]
    return None


def _rate_limit_key(request: Request, install_id: str | None) -> str:
    normalized_install_id = (install_id or "").strip()
    if normalized_install_id:
        return f"install:{normalized_install_id[:80]}"

    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    host = forwarded_for or (request.client.host if request.client else "unknown")
    return f"ip:{host}"


def _enforce_rate_limit(key: str) -> None:
    now = datetime.now(UTC)
    one_day_ago = now - timedelta(days=1)
    one_minute_ago = now - timedelta(minutes=1)

    requests = _REQUEST_LOGS[key]
    while requests and requests[0] < one_day_ago:
        requests.popleft()

    per_minute_count = sum(1 for item in requests if item >= one_minute_ago)
    if per_minute_count >= _PER_MINUTE_LIMIT or len(requests) >= _PER_DAY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Habitdot motivation rate limit exceeded",
        )

    requests.append(now)
