from fastapi import APIRouter, Depends

from app.api.deps import RequestIdentity, get_request_identity
from app.repositories.face_scan_repository import FaceScanRepository
from app.schemas.analysis import CreateFaceScanCaptureRequest, FaceScanCaptureResponse

router = APIRouter(prefix="/face-scans", tags=["face-scans"])


@router.post("", response_model=FaceScanCaptureResponse)
async def create_face_scan_capture(
    request: CreateFaceScanCaptureRequest,
    identity: RequestIdentity = Depends(get_request_identity),
) -> FaceScanCaptureResponse:
    return FaceScanRepository().create_capture(identity.user_id, request, identity.client_install_id)
