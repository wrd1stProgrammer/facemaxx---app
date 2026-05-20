from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.repositories.purchase_repository import (
    PRO_ENTITLEMENT_ID,
    SCAN_PACK_CREDITS_BY_PRODUCT_ID,
    SUBSCRIPTION_PRODUCT_IDS,
    PurchaseRepository,
)
from app.schemas.purchases import ProScanStatusResponse, RevenueCatWebhookResponse


class RevenueCatService:
    def __init__(self) -> None:
        self.purchase_repository = PurchaseRepository()

    async def sync_subscriber(self, app_user_id: str) -> ProScanStatusResponse:
        subscriber_payload = await self._fetch_subscriber(app_user_id)
        subscriber = subscriber_payload.get("subscriber") or {}

        original_app_user_id = subscriber.get("original_app_user_id")
        subscription_product_id, expires_at = self._active_subscription(subscriber)
        subscription_active = expires_at is None or expires_at > datetime.now(timezone.utc)
        non_subscription_product_ids = sorted((subscriber.get("non_subscriptions") or {}).keys())
        print(
            "Facemaxx RevenueCat subscriber fetched:",
            f"app_user_id={app_user_id}",
            f"original_app_user_id={original_app_user_id or 'none'}",
            f"subscription_product_id={subscription_product_id or 'none'}",
            f"subscription_active={subscription_active}",
            f"non_subscriptions={','.join(non_subscription_product_ids) or 'none'}",
        )
        self.purchase_repository.set_subscription_status(
            app_user_id=app_user_id,
            active=subscription_active,
            product_id=subscription_product_id,
            expires_at=expires_at,
            original_app_user_id=original_app_user_id,
        )

        for product_id, purchases in (subscriber.get("non_subscriptions") or {}).items():
            if product_id not in SCAN_PACK_CREDITS_BY_PRODUCT_ID:
                continue
            for purchase in purchases or []:
                transaction_id = self._transaction_id(product_id, purchase)
                did_grant = self.purchase_repository.grant_scan_pack(
                    app_user_id=app_user_id,
                    product_id=product_id,
                    transaction_id=transaction_id,
                    raw_transaction=purchase,
                )
                print(
                    "Facemaxx RevenueCat scan pack sync:",
                    f"app_user_id={app_user_id}",
                    f"product_id={product_id}",
                    f"transaction_id={transaction_id}",
                    f"credits={SCAN_PACK_CREDITS_BY_PRODUCT_ID[product_id]}",
                    f"granted={did_grant}",
                )

        return self.purchase_repository.status_for_app_user_id(app_user_id)

    def handle_webhook(self, payload: dict[str, Any]) -> RevenueCatWebhookResponse:
        event = payload.get("event") or payload
        if not isinstance(event, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid RevenueCat webhook payload")

        app_user_id = self._string_value(event, "app_user_id") or self._string_value(event, "original_app_user_id")
        if not app_user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing RevenueCat app_user_id")

        event_type = self._string_value(event, "type") or "UNKNOWN"
        product_id = (
            self._string_value(event, "product_id")
            or self._string_value(event, "product_identifier")
        )
        event_id = (
            self._string_value(event, "id")
            or self._string_value(event, "event_id")
            or self._string_value(event, "transaction_id")
            or f"{app_user_id}:{event_type}:{product_id or 'none'}:{self._string_value(event, 'event_timestamp_ms') or ''}"
        )

        is_new_event = self.purchase_repository.record_revenuecat_event(
            event_id=event_id,
            app_user_id=app_user_id,
            event_type=event_type,
            product_id=product_id,
            raw_event=event,
        )

        credits_granted = 0
        if is_new_event and product_id in SCAN_PACK_CREDITS_BY_PRODUCT_ID:
            transaction_id = (
                self._string_value(event, "transaction_id")
                or self._string_value(event, "store_transaction_id")
                or event_id
            )
            did_grant = self.purchase_repository.grant_scan_pack(
                app_user_id=app_user_id,
                product_id=product_id,
                transaction_id=transaction_id,
                raw_transaction=event,
            )
            if did_grant:
                credits_granted = SCAN_PACK_CREDITS_BY_PRODUCT_ID[product_id]

        if self._is_pro_subscription_event(event, product_id):
            expires_at = self._date_from_ms(event.get("expiration_at_ms"))
            active = self._subscription_active_for_event(event_type, expires_at)
            self.purchase_repository.set_subscription_status(
                app_user_id=app_user_id,
                active=active,
                product_id=product_id,
                expires_at=expires_at,
                original_app_user_id=self._string_value(event, "original_app_user_id"),
            )

        print(
            "Facemaxx RevenueCat webhook processed:",
            f"event_id={event_id}",
            f"event_type={event_type}",
            f"app_user_id={app_user_id}",
            f"product_id={product_id or 'none'}",
            f"is_new_event={is_new_event}",
            f"credits_granted={credits_granted}",
        )
        return RevenueCatWebhookResponse(
            ok=True,
            app_user_id=app_user_id,
            event_type=event_type,
            product_id=product_id,
            credits_granted=credits_granted,
        )

    async def _fetch_subscriber(self, app_user_id: str) -> dict[str, Any]:
        settings = get_settings()
        if not settings.revenuecat_secret_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RevenueCat secret API key is not configured.",
            )

        encoded_app_user_id = quote(app_user_id, safe="")
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                f"https://api.revenuecat.com/v1/subscribers/{encoded_app_user_id}",
                headers={
                    "Authorization": f"Bearer {settings.revenuecat_secret_api_key}",
                    "Accept": "application/json",
                },
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"RevenueCat subscriber sync failed: {response.text}",
            )

        return response.json()

    @staticmethod
    def _active_subscription(subscriber: dict[str, Any]) -> tuple[str | None, datetime | None]:
        entitlement = (subscriber.get("entitlements") or {}).get(PRO_ENTITLEMENT_ID)
        if entitlement:
            product_id = (
                RevenueCatService._string_value(entitlement, "product_identifier")
                or RevenueCatService._string_value(entitlement, "product_id")
            )
            expires_date = entitlement.get("expires_date")
            expires_at = RevenueCatService._date_from_string(str(expires_date)) if expires_date else None
            if product_id in SUBSCRIPTION_PRODUCT_IDS:
                return product_id, expires_at

        now = datetime.now(timezone.utc)
        best_product_id: str | None = None
        best_expires_at = datetime.fromtimestamp(0, tz=timezone.utc)
        for product_id, subscription in (subscriber.get("subscriptions") or {}).items():
            if product_id not in SUBSCRIPTION_PRODUCT_IDS:
                continue
            expires_at = RevenueCatService._date_from_string(str(subscription.get("expires_date") or ""))
            if expires_at is None:
                return product_id, None
            if expires_at > now and expires_at > best_expires_at:
                best_product_id = product_id
                best_expires_at = expires_at

        if best_product_id:
            return best_product_id, best_expires_at

        return None, datetime.fromtimestamp(0, tz=timezone.utc)

    @staticmethod
    def _is_pro_subscription_event(event: dict[str, Any], product_id: str | None) -> bool:
        entitlement_ids = event.get("entitlement_ids") or []
        return (
            product_id in SUBSCRIPTION_PRODUCT_IDS
            or PRO_ENTITLEMENT_ID in entitlement_ids
        )

    @staticmethod
    def _subscription_active_for_event(event_type: str, expires_at: datetime | None) -> bool:
        if event_type == "EXPIRATION":
            return False

        if expires_at is None:
            return True

        return expires_at > datetime.now(timezone.utc)

    @staticmethod
    def _transaction_id(product_id: str, purchase: dict[str, Any]) -> str:
        return (
            RevenueCatService._string_value(purchase, "id")
            or RevenueCatService._string_value(purchase, "transaction_id")
            or RevenueCatService._string_value(purchase, "store_transaction_id")
            or f"{product_id}:{RevenueCatService._string_value(purchase, 'purchase_date') or ''}"
        )

    @staticmethod
    def _date_from_ms(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _date_from_string(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _string_value(payload: dict[str, Any], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None
