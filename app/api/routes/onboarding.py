from fastapi import APIRouter, Depends

from app.api.deps import RequestIdentity, get_request_identity
from app.repositories.onboarding_repository import OnboardingRepository
from app.schemas.onboarding import OnboardingPreferencesRequest, OnboardingPreferencesResponse

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.put("/preferences", response_model=OnboardingPreferencesResponse)
async def save_onboarding_preferences(
    request: OnboardingPreferencesRequest,
    identity: RequestIdentity = Depends(get_request_identity),
) -> OnboardingPreferencesResponse:
    return OnboardingRepository().save_preferences(identity.user_id, request)


@router.get("/preferences", response_model=OnboardingPreferencesResponse)
async def get_onboarding_preferences(
    identity: RequestIdentity = Depends(get_request_identity),
) -> OnboardingPreferencesResponse:
    return OnboardingRepository().get_preferences(identity.user_id)
