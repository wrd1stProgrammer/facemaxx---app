from fastapi import APIRouter

from app.api.routes import (
    account,
    analysis,
    face_scans,
    flirtist,
    habitdot,
    health,
    modes,
    onboarding,
    photos,
    purchases,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(modes.router)
api_router.include_router(photos.router)
api_router.include_router(face_scans.router)
api_router.include_router(analysis.router)
api_router.include_router(onboarding.router)
api_router.include_router(account.router)
api_router.include_router(purchases.router)
api_router.include_router(habitdot.router)
api_router.include_router(flirtist.router)
