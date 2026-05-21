from __future__ import annotations

from typing import Any

from app.schemas.common import FacemaxxBaseModel


class ProScanStatusResponse(FacemaxxBaseModel):
    app_user_id: str
    has_active_pro_subscription: bool
    free_trial_scan_available: bool = False
    pro_scans_remaining: int
    subscription_product_id: str | None = None
    subscription_scan_limit: int = 0
    subscription_scans_remaining: int = 0
    subscription_quota_reset_at: str | None = None
    consumable_pro_scans_remaining: int = 0
    can_use_pro_scan: bool


class RevenueCatWebhookResponse(FacemaxxBaseModel):
    ok: bool
    app_user_id: str | None = None
    event_type: str | None = None
    product_id: str | None = None
    credits_granted: int = 0
    raw: dict[str, Any] | None = None
