from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anyio
import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.deps import RequestIdentity
from app.schemas.analysis import AnalysisResultPayload, AnalysisRunResponse, CreateAnalysisRunRequest, ScoreRing
from app.services.analysis.jobs import AnalysisJobs, trial_preview
from app.services.analysis.runner import AnalysisRunner
from app.repositories.purchase_repository import ProScanReservation


@pytest.mark.parametrize("new_client,mode,allowed", [
    (False, "proportions", True), (False, "aesthetics", False),
    (True, "proportions", False), (True, "aesthetics", True),
])
def test_trial_policy_preserves_legacy_clients(new_client, mode, allowed):
    async def scenario():
        # Given the same single free-trial balance on either API contract.
        runner = AnalysisRunner(pending_run_id=uuid4() if new_client else None)
        for name in ("analysis_repository", "photo_repository", "face_scan_repository", "onboarding_repository", "purchase_repository"):
            setattr(runner, name, MagicMock())
        runner.purchase_repository.status_for_identity.return_value = SimpleNamespace(
            free_trial_scan_available=True, can_use_pro_scan=True, app_user_id="test", pro_scans_remaining=0)
        runner.purchase_repository.reserve_pro_scan.return_value = ProScanReservation("test", True, False, False, 0, "free_trial")
        photo = uuid4()
        runner._provider_photo_input = MagicMock(return_value=SimpleNamespace(
            photo_id=photo, photo_url=None, photo_bytes=b"image", photo_mime_type="image/jpeg"))
        runner.analysis_repository.create_run.return_value = uuid4()
        provider = SimpleNamespace(analyze=AsyncMock(return_value=AnalysisResultPayload(mode_id=mode, provider="test")))
        # When the client requests a trial analysis.
        with patch("app.services.analysis.runner.get_face_analysis_provider", return_value=provider):
            if allowed:
                response = await runner.run(RequestIdentity(None, "test"), CreateAnalysisRunRequest(mode_id=mode, photo_id=photo))
                # Then exactly one trial is reserved and the result remains marked as trial.
                assert response.is_free_trial_result
                runner.purchase_repository.reserve_pro_scan.assert_called_once()
                provider.analyze.assert_awaited_once()
            else:
                with pytest.raises(HTTPException) as exc:
                    await runner.run(RequestIdentity(None, "test"), CreateAnalysisRunRequest(mode_id=mode, photo_id=photo))
                assert exc.value.status_code == 402
                provider.analyze.assert_not_awaited()
                runner.purchase_repository.reserve_pro_scan.assert_not_called()
    anyio.run(scenario)


def test_new_trial_response_exposes_only_nine_rings():
    # Given a full private result.
    result = AnalysisResultPayload(mode_id="aesthetics", provider="test", overall_score=8,
        summary_text="Private report", rings=[ScoreRing(metric_id=str(i), title_key="ring", score=7,
        display_value="7.0", tint="green", sort_order=i) for i in range(9)])
    full = AnalysisRunResponse(id=uuid4(), status="completed", mode_id="aesthetics", is_free_trial_result=True, result=result)
    # When projected for the client.
    preview = trial_preview(full)
    # Then score rings survive, other result data does not, and the stored object is untouched.
    assert len(preview.result.rings) == 9
    assert preview.result.overall_score is None
    assert preview.result.summary_text is None
    assert preview.result.metrics == []
    assert full.result.summary_text == "Private report"


@pytest.mark.parametrize("trial,mode", [(False, "aesthetics"), (True, "proportions")])
def test_paid_and_legacy_results_are_unchanged(trial, mode):
    # Given paid content or a 1.0.4 trial result.
    response = AnalysisRunResponse(id=uuid4(), status="completed", mode_id=mode, is_free_trial_result=trial,
        result=AnalysisResultPayload(mode_id=mode, provider="test", overall_score=8, summary_text="Original"))
    # When read through the API projection, then legacy/paid fields are preserved.
    assert trial_preview(response) == response


def test_duplicate_submission_recovers_without_scheduling_or_charging():
    async def scenario():
        # Given an existing job owned by this installation.
        job = AnalysisJobs(RequestIdentity(None, "test"))
        existing = AnalysisRunResponse(id=uuid4(), status="processing", mode_id="aesthetics")
        job.repository = MagicMock()
        job.repository.get_run.return_value = existing
        background = BackgroundTasks()
        # When the initial PUT response was lost and is retried.
        with patch("app.services.analysis.jobs.get_supabase_service_client", return_value=True):
            recovered = await job.submit(existing.id, CreateAnalysisRunRequest(mode_id="aesthetics", photo_id=uuid4()), background)
        # Then no second task / reservation is created.
        assert recovered.id == existing.id
        assert background.tasks == []
        job.repository.create_run.assert_not_called()
    anyio.run(scenario)


def test_job_failure_is_persisted_for_returning_client():
    async def scenario():
        # Given a terminal provider failure.
        jobs = AnalysisJobs(RequestIdentity(None, "test"))
        jobs.repository = MagicMock()
        run_id = uuid4()
        runner = SimpleNamespace(run=AsyncMock(side_effect=HTTPException(504, "timeout")))
        # When the app is no longer connected but the job finishes.
        with patch("app.services.analysis.jobs.AnalysisRunner", return_value=runner):
            await jobs.execute(run_id, CreateAnalysisRunRequest(mode_id="aesthetics", photo_id=uuid4()))
        # Then the returning client can observe a terminal error rather than an endless spinner.
        jobs.repository.fail_run.assert_called_once_with(run_id, "504")
    anyio.run(scenario)
