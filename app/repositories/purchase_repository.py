from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.api.deps import RequestIdentity
from app.core.config import get_settings
from app.db.supabase import get_supabase_service_client
from app.schemas.purchases import ProScanStatusResponse


PRO_ENTITLEMENT_ID = "pro"

SUBSCRIPTION_PRODUCT_IDS = {
    "facemaxx1wk",
    "facemaxx1mo",
}

SUBSCRIPTION_QUOTA_BY_PRODUCT_ID = {
    "facemaxx1wk": {"limit": 12, "period": "week"},
    "facemaxx1mo": {"limit": 50, "period": "month"},
}

SCAN_PACK_CREDITS_BY_PRODUCT_ID = {
    "facemaxx10scan": 10,
    "facemaxx20scan": 20,
    "facemaxx50scan": 50,
}


@dataclass(frozen=True)
class ProScanReservation:
    app_user_id: str
    allowed: bool
    subscription_active: bool
    credits_remaining: int
    consumed_source: str | None

    @property
    def consumed_credit(self) -> bool:
        return self.consumed_source in {"subscription", "consumable"}


class PurchaseRepository:
    def status_for_identity(self, identity: RequestIdentity) -> ProScanStatusResponse:
        return self.status_for_app_user_id(self.app_user_id_for_identity(identity), identity)

    def status_for_app_user_id(
        self,
        app_user_id: str,
        identity: RequestIdentity | None = None,
    ) -> ProScanStatusResponse:
        supabase = get_supabase_service_client()
        if supabase is None:
            return ProScanStatusResponse(
                app_user_id=app_user_id,
                has_active_pro_subscription=False,
                pro_scans_remaining=1,
                consumable_pro_scans_remaining=1,
                can_use_pro_scan=True,
            )

        self.ensure_account(app_user_id, identity)
        supabase.rpc("refresh_purchase_account_quota", {"p_app_user_id": app_user_id}).execute()
        response = (
            supabase.table("purchase_accounts")
            .select(
                "pro_subscription_active,pro_subscription_product_id,pro_subscription_expires_at,"
                "subscription_scan_limit,subscription_scans_remaining,subscription_quota_reset_at,"
                "consumable_pro_scans_remaining"
            )
            .eq("app_user_id", app_user_id)
            .single()
            .execute()
        )
        row = response.data or {}
        has_subscription = self._is_subscription_active(row)
        subscription_credits = max(0, int(row.get("subscription_scans_remaining") or 0)) if has_subscription else 0
        consumable_credits = max(0, int(row.get("consumable_pro_scans_remaining") or 0))
        total_credits = subscription_credits + consumable_credits
        return ProScanStatusResponse(
            app_user_id=app_user_id,
            has_active_pro_subscription=has_subscription,
            pro_scans_remaining=total_credits,
            subscription_product_id=row.get("pro_subscription_product_id"),
            subscription_scan_limit=max(0, int(row.get("subscription_scan_limit") or 0)),
            subscription_scans_remaining=subscription_credits,
            subscription_quota_reset_at=row.get("subscription_quota_reset_at"),
            consumable_pro_scans_remaining=consumable_credits,
            can_use_pro_scan=total_credits > 0,
        )

    def reserve_pro_scan(self, identity: RequestIdentity) -> ProScanReservation:
        app_user_id = self.app_user_id_for_identity(identity)
        supabase = get_supabase_service_client()
        if supabase is None:
            return ProScanReservation(
                app_user_id=app_user_id,
                allowed=True,
                subscription_active=False,
                credits_remaining=1,
                consumed_source=None,
            )

        response = supabase.rpc(
            "consume_pro_scan_credit",
            {
                "p_app_user_id": app_user_id,
                "p_user_id": identity.user_id,
                "p_client_install_id": identity.client_install_id,
            },
        ).execute()
        data = response.data or {}
        reservation = ProScanReservation(
            app_user_id=app_user_id,
            allowed=bool(data.get("allowed")),
            subscription_active=bool(data.get("subscription_active")),
            credits_remaining=max(0, int(data.get("credits_remaining") or 0)),
            consumed_source=data.get("consumed_source"),
        )
        if not reservation.allowed:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "code": "pro_scan_required",
                    "message": "Remaining Pro scan quota is required.",
                    "app_user_id": app_user_id,
                    "pro_scans_remaining": reservation.credits_remaining,
                },
            )
        return reservation

    def refund_reserved_credit(self, reservation: ProScanReservation | None) -> None:
        if reservation is None or not reservation.consumed_credit:
            return

        supabase = get_supabase_service_client()
        if supabase is None:
            return

        try:
            supabase.rpc(
                "refund_pro_scan_credit",
                {
                    "p_app_user_id": reservation.app_user_id,
                    "p_consumed_source": reservation.consumed_source,
                },
            ).execute()
        except Exception as exc:
            print(f"Pro scan credit refund skipped: {exc}")

    def ensure_account(self, app_user_id: str, identity: RequestIdentity | None = None) -> None:
        supabase = get_supabase_service_client()
        if supabase is None:
            return

        supabase.rpc(
            "ensure_purchase_account",
            {
                "p_app_user_id": app_user_id,
                "p_user_id": identity.user_id if identity else None,
                "p_client_install_id": identity.client_install_id if identity else None,
            },
        ).execute()

    def set_subscription_status(
        self,
        app_user_id: str,
        active: bool,
        product_id: str | None,
        expires_at: datetime | None,
        original_app_user_id: str | None = None,
    ) -> None:
        supabase = get_supabase_service_client()
        if supabase is None:
            return

        quota = self.subscription_quota(product_id)
        supabase.rpc(
            "set_pro_subscription_status",
            {
                "p_app_user_id": app_user_id,
                "p_active": active,
                "p_product_id": product_id,
                "p_quota_limit": quota["limit"],
                "p_quota_period": quota["period"],
                "p_expires_at": expires_at.isoformat() if expires_at else None,
                "p_original_app_user_id": original_app_user_id,
            },
        ).execute()

    def grant_scan_pack(
        self,
        app_user_id: str,
        product_id: str,
        transaction_id: str,
        raw_transaction: dict[str, Any],
    ) -> bool:
        credits = SCAN_PACK_CREDITS_BY_PRODUCT_ID.get(product_id)
        if credits is None:
            return False

        supabase = get_supabase_service_client()
        if supabase is None:
            return False

        response = supabase.rpc(
            "grant_pro_scan_credits",
            {
                "p_app_user_id": app_user_id,
                "p_product_id": product_id,
                "p_transaction_id": transaction_id,
                "p_credits": credits,
                "p_raw_transaction": raw_transaction,
            },
        ).execute()
        return bool(response.data)

    def record_revenuecat_event(
        self,
        event_id: str,
        app_user_id: str,
        event_type: str,
        product_id: str | None,
        raw_event: dict[str, Any],
    ) -> bool:
        supabase = get_supabase_service_client()
        if supabase is None:
            return False

        self.ensure_account(app_user_id)
        try:
            supabase.table("revenuecat_events").insert(
                {
                    "event_id": event_id,
                    "app_user_id": app_user_id,
                    "event_type": event_type,
                    "product_id": product_id,
                    "raw_event": raw_event,
                }
            ).execute()
            return True
        except Exception as exc:
            if "duplicate key" not in str(exc).lower() and "already exists" not in str(exc).lower():
                raise
            return False

    @staticmethod
    def app_user_id_for_identity(identity: RequestIdentity) -> str:
        if identity.user_id:
            return identity.user_id
        if identity.client_install_id:
            return identity.client_install_id
        return get_settings().demo_user_id

    @staticmethod
    def _is_subscription_active(row: dict[str, Any]) -> bool:
        if not bool(row.get("pro_subscription_active")):
            return False

        expires_at = row.get("pro_subscription_expires_at")
        if not expires_at:
            return True

        try:
            normalized = str(expires_at).replace("Z", "+00:00")
            return datetime.fromisoformat(normalized) > datetime.now(timezone.utc)
        except ValueError:
            return False

    @staticmethod
    def subscription_quota(product_id: str | None) -> dict[str, Any]:
        return SUBSCRIPTION_QUOTA_BY_PRODUCT_ID.get(product_id or "", {"limit": 0, "period": None})


def normalized_uuid_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None
