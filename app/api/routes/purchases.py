from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import RequestIdentity, get_request_identity
from app.core.config import get_settings
from app.repositories.purchase_repository import PurchaseRepository
from app.schemas.purchases import ProScanStatusResponse, RevenueCatWebhookResponse
from app.services.revenuecat import RevenueCatService

router = APIRouter(tags=["purchases"])


@router.get("/pro-scans/status", response_model=ProScanStatusResponse)
async def pro_scan_status(
    identity: RequestIdentity = Depends(get_request_identity),
) -> ProScanStatusResponse:
    return PurchaseRepository().status_for_identity(identity)


@router.post("/pro-scans/sync", response_model=ProScanStatusResponse)
async def sync_pro_scan_status(
    identity: RequestIdentity = Depends(get_request_identity),
) -> ProScanStatusResponse:
    app_user_id = PurchaseRepository.app_user_id_for_identity(identity)
    print(
        "Facemaxx RevenueCat sync requested:",
        f"app_user_id={app_user_id}",
        f"user_id={identity.user_id or 'none'}",
        f"install_id={identity.client_install_id or 'none'}",
    )
    return await RevenueCatService().sync_subscriber(app_user_id)


@router.post("/revenuecat/webhook", response_model=RevenueCatWebhookResponse)
async def revenuecat_webhook(
    payload: dict[str, Any],
    authorization: Annotated[Optional[str], Header()] = None,
) -> RevenueCatWebhookResponse:
    expected_token = get_settings().revenuecat_webhook_bearer_token
    if expected_token:
        expected_token = _normalized_webhook_token(expected_token)
        received_token = _normalized_webhook_token(authorization)
        if received_token != expected_token:
            received_scheme = authorization.strip().split(" ", 1)[0] if authorization else "missing"
            print(
                "Facemaxx RevenueCat webhook rejected:",
                "authorization_present=" + str(bool(authorization)),
                f"authorization_scheme={received_scheme}",
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid RevenueCat webhook token")

    return RevenueCatService().handle_webhook(payload)


def _normalized_webhook_token(value: str | None) -> str | None:
    if not value:
        return None

    token = value.strip()
    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()
    return token or None
