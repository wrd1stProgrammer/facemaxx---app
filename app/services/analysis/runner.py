import traceback
from uuid import UUID

from fastapi import HTTPException, status

from app.api.deps import RequestIdentity
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.face_scan_repository import FaceScanRepository
from app.repositories.onboarding_repository import OnboardingRepository
from app.repositories.photo_repository import PhotoRepository
from app.repositories.purchase_repository import PurchaseRepository
from app.schemas.analysis import AnalysisRunResponse, CreateAnalysisRunRequest, MULTI_PHOTO_MINIMUMS
from app.services.ai.base import ProviderAnalysisRequest, ProviderPhotoInput
from app.services.ai.factory import get_face_analysis_provider


PRO_SCAN_MODE_IDS = {
    "proportions",
    "aesthetics",
    "glow-up-coach",
    "look-archetype",
    "best-photo-selector",
    "best-angle-finder",
    "dating-profile-score",
    "instagram-profile-score",
}


class AnalysisRunner:
    def __init__(self) -> None:
        self.analysis_repository = AnalysisRepository()
        self.photo_repository = PhotoRepository()
        self.face_scan_repository = FaceScanRepository()
        self.onboarding_repository = OnboardingRepository()
        self.purchase_repository = PurchaseRepository()

    async def run(self, identity: RequestIdentity, request: CreateAnalysisRunRequest) -> AnalysisRunResponse:
        photo_ids = self._analysis_photo_ids(request)
        minimum_photo_count = MULTI_PHOTO_MINIMUMS.get(request.mode_id, 1)
        if len(photo_ids) < minimum_photo_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{request.mode_id} requires at least {minimum_photo_count} photos.",
            )

        stored_onboarding_context = self.onboarding_repository.context_for_user(identity.user_id)
        request_onboarding_context = self.onboarding_repository.normalized_context(request.onboarding_context)
        onboarding_context = stored_onboarding_context or request_onboarding_context

        pro_scan_reservation = None
        if request.mode_id in PRO_SCAN_MODE_IDS:
            pro_scan_reservation = self.purchase_repository.reserve_pro_scan(identity)
        is_free_trial_result = bool(pro_scan_reservation and pro_scan_reservation.consumed_free_trial)

        try:
            run_id = self.analysis_repository.create_run(
                user_id=identity.user_id,
                client_install_id=identity.client_install_id,
                mode_id=request.mode_id,
                photo_id=photo_ids[0] if photo_ids else None,
                photo_ids=photo_ids,
                source=request.source,
                face_scan_capture_id=request.face_scan_capture_id,
                onboarding_context=onboarding_context,
                is_free_trial_result=is_free_trial_result,
            )
        except Exception:
            self.purchase_repository.refund_reserved_credit(pro_scan_reservation)
            raise

        provider = get_face_analysis_provider()
        photos = [self._provider_photo_input(photo_id) for photo_id in photo_ids]
        primary_photo = photos[0] if photos else None
        photo_url = primary_photo.photo_url if primary_photo else None
        photo_bytes = primary_photo.photo_bytes if primary_photo else None
        photo_mime_type = primary_photo.photo_mime_type if primary_photo else None
        face_metrics = (
            self.face_scan_repository.get_capture_metrics(request.face_scan_capture_id)
            if request.face_scan_capture_id
            else []
        )

        try:
            print(
                "Facemaxx analysis provider:",
                getattr(provider, "name", provider.__class__.__name__),
                "model=",
                getattr(provider, "model_name", None),
                "mode=",
                request.mode_id,
                "photos=",
                len(photos),
                "photo_bytes=",
                bool(photo_bytes),
                "photo_url=",
                bool(photo_url),
                "metrics=",
                len(face_metrics),
                "onboarding=",
                bool(onboarding_context),
            )
            result = await provider.analyze(
                ProviderAnalysisRequest(
                    user_id=identity.user_id,
                    mode_id=request.mode_id,
                    locale=request.locale,
                    photo_id=primary_photo.photo_id if primary_photo else None,
                    photo_ids=photo_ids,
                    photo_url=photo_url,
                    photo_bytes=photo_bytes,
                    photo_mime_type=photo_mime_type,
                    photos=photos,
                    face_scan_capture_id=request.face_scan_capture_id,
                    face_metrics=face_metrics,
                    onboarding_context=onboarding_context,
                )
            )
            print(
                "Facemaxx analysis completed:",
                "provider=",
                result.provider,
                "mode=",
                result.mode_id,
                "rings=",
                len(result.rings),
                "metrics=",
                len(result.metrics),
                "coach_items=",
                len(result.coach_items),
                "has_archetype=",
                bool(result.look_archetype),
            )
        except Exception as exc:
            print("Facemaxx analysis provider failed:", repr(exc))
            traceback.print_exc()
            self.purchase_repository.refund_reserved_credit(pro_scan_reservation)
            self.analysis_repository.fail_run(run_id, str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Analysis provider failed: {exc}",
            ) from exc

        try:
            self.analysis_repository.complete_run(run_id, result)
        except Exception as exc:
            print("Facemaxx analysis persistence failed:", repr(exc))
            traceback.print_exc()
            self.purchase_repository.refund_reserved_credit(pro_scan_reservation)
            self.analysis_repository.fail_run(run_id, str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Analysis persistence failed: {exc}",
            ) from exc

        return AnalysisRunResponse(
            id=run_id,
            status="completed",
            mode_id=request.mode_id,
            is_free_trial_result=is_free_trial_result,
            photo_id=primary_photo.photo_id if primary_photo else None,
            photo_ids=photo_ids,
            face_scan_capture_id=request.face_scan_capture_id,
            result=result,
        )

    def _analysis_photo_ids(self, request: CreateAnalysisRunRequest) -> list[UUID]:
        if request.mode_id in MULTI_PHOTO_MINIMUMS:
            return request.photo_ids or []
        return [request.photo_id] if request.photo_id else []

    def _provider_photo_input(self, photo_id: UUID) -> ProviderPhotoInput:
        photo_url = self.photo_repository.get_public_photo_url(photo_id)
        photo_bytes, photo_mime_type = self.photo_repository.get_photo_bytes(photo_id)
        return ProviderPhotoInput(
            photo_id=photo_id,
            photo_url=photo_url,
            photo_bytes=photo_bytes,
            photo_mime_type=photo_mime_type,
        )
