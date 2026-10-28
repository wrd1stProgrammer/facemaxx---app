import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anyio
from fastapi import HTTPException

from app.api.deps import RequestIdentity
from app.repositories.purchase_repository import PurchaseRepository, ProScanReservation
from app.schemas.analysis import CreateAnalysisRunRequest
from app.services.analysis.runner import AnalysisRunner


class CreditGuardTests(unittest.TestCase):
    def runner(self, reservation):
        runner = AnalysisRunner.__new__(AnalysisRunner)
        for name in ("analysis_repository", "photo_repository", "face_scan_repository",
                     "onboarding_repository", "purchase_repository"):
            setattr(runner, name, MagicMock())
        runner.purchase_repository.status_for_identity.return_value = SimpleNamespace(
            can_use_pro_scan=True, free_trial_scan_available=False)
        runner.purchase_repository.reserve_pro_scan.return_value = reservation
        runner._provider_photo_input = MagicMock(return_value=SimpleNamespace(
            photo_id=uuid4(), photo_url=None, photo_bytes=b"image", photo_mime_type="image/jpeg"))
        return runner

    def test_lost_credit_race_never_calls_provider(self):
        async def run():
            runner = self.runner(SimpleNamespace(allowed=False))
            provider = SimpleNamespace(analyze=AsyncMock())
            with patch("app.services.analysis.runner.get_face_analysis_provider", return_value=provider):
                with self.assertRaises(HTTPException) as error:
                    await runner.run(RequestIdentity(None, str(uuid4())),
                                     CreateAnalysisRunRequest(mode_id="aesthetics", photo_id=uuid4()))
                self.assertEqual(error.exception.status_code, 402)
                provider.analyze.assert_not_awaited()
        anyio.run(run)

    def test_provider_timeout_refunds_prepaid_reservation(self):
        async def run():
            reservation = ProScanReservation("guest", True, False, False, 0, "consumable")
            runner = self.runner(reservation)
            async def fail_after_reservation(*args):
                runner.purchase_repository.reserve_pro_scan.assert_called_once()
                raise TimeoutError()
            provider = SimpleNamespace(analyze=AsyncMock(side_effect=fail_after_reservation))
            with patch("app.services.analysis.runner.get_face_analysis_provider", return_value=provider):
                with self.assertRaises(HTTPException) as error:
                    await runner.run(RequestIdentity(None, str(uuid4())),
                                     CreateAnalysisRunRequest(mode_id="aesthetics", photo_id=uuid4()))
                self.assertEqual(error.exception.status_code, 504)
                runner.purchase_repository.refund_reserved_credit.assert_called_once_with(reservation)
        anyio.run(run)

    def test_missing_credit_database_fails_closed(self):
        with patch("app.repositories.purchase_repository.get_supabase_service_client", return_value=None):
            with self.assertRaises(HTTPException) as error:
                PurchaseRepository().reserve_pro_scan(RequestIdentity(None, str(uuid4())))
            self.assertEqual(error.exception.status_code, 503)
