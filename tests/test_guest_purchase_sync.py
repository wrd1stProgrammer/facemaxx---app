import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.deps import RequestIdentity
from app.api.routes.purchases import sync_pro_scan_status
from app.services.revenuecat import RevenueCatService


class GuestPurchaseSyncTest(unittest.IsolatedAsyncioTestCase):
    async def test_guest_queries_swift_identity_but_keeps_database_identity(self):
        guest_id = "abcdefab-1234-4567-8901-abcdefabcdef"
        service = MagicMock()
        service.sync_subscriber = AsyncMock()
        with patch("app.api.routes.purchases.RevenueCatService", return_value=service):
            await sync_pro_scan_status(RequestIdentity(None, guest_id))
        service.sync_subscriber.assert_awaited_once_with(
            guest_id, revenuecat_app_user_id=guest_id.upper()
        )

    async def test_subscription_is_saved_under_status_lookup_identity(self):
        guest_id = "abcdefab-1234-4567-8901-abcdefabcdef"
        service = RevenueCatService()
        service.purchase_repository = MagicMock()
        service._fetch_subscriber = AsyncMock(return_value={"subscriber": {
            "entitlements": {"pro": {"product_identifier": "facemaxx1mo", "expires_date": "2099-01-01T00:00:00Z"}}
        }})
        await service.sync_subscriber(guest_id, revenuecat_app_user_id=guest_id.upper())
        service._fetch_subscriber.assert_awaited_once_with(guest_id.upper())
        saved = service.purchase_repository.set_subscription_status.call_args.kwargs
        self.assertEqual(saved["app_user_id"], guest_id)
        self.assertTrue(saved["active"])
        self.assertEqual(saved["product_id"], "facemaxx1mo")
        service.purchase_repository.status_for_app_user_id.assert_called_once_with(guest_id)
