from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.api.deps import RequestIdentity, get_request_identity
from app.repositories.photo_repository import PhotoRepository
from app.schemas.analysis import CreatePhotoRequest, PhotoOut

router = APIRouter(prefix="/photos", tags=["photos"])


@router.post("", response_model=PhotoOut)
async def create_photo(
    request: CreatePhotoRequest,
    identity: RequestIdentity = Depends(get_request_identity),
) -> PhotoOut:
    return PhotoRepository().create_photo(identity.user_id, request, identity.client_install_id)


@router.post("/upload", response_model=PhotoOut)
async def upload_photo(
    identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    file: UploadFile = File(...),
    width: Optional[int] = Form(default=None),
    height: Optional[int] = Form(default=None),
) -> PhotoOut:
    mime_type = file.content_type or "application/octet-stream"
    if not mime_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only image uploads are supported",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty",
        )

    return PhotoRepository().upload_photo(
        user_id=identity.user_id,
        client_install_id=identity.client_install_id,
        content=content,
        filename=file.filename,
        mime_type=mime_type,
        width=width,
        height=height,
    )


@router.get("/{photo_id}/image")
async def get_photo_image(
    photo_id: UUID,
    identity: RequestIdentity = Depends(get_request_identity),
) -> Response:
    content, mime_type = PhotoRepository().get_photo_bytes(photo_id)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo image not found")

    return Response(content=content, media_type=mime_type or "image/jpeg")
