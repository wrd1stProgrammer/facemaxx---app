from __future__ import annotations

import hashlib
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.db.supabase import get_supabase_service_client
from app.schemas.analysis import CreatePhotoRequest, PhotoOut


@dataclass(frozen=True)
class PhotoStorageLocation:
    bucket: str
    path: str


class PhotoRepository:
    def create_photo(
        self,
        user_id: str | None,
        request: CreatePhotoRequest,
        client_install_id: str | None = None,
    ) -> PhotoOut:
        settings = get_settings()
        payload = {
            "id": str(uuid4()),
            "user_id": user_id,
            "client_install_id": client_install_id,
            "storage_bucket": request.storage_bucket or settings.supabase_storage_bucket,
            "storage_path": request.storage_path,
            "mime_type": request.mime_type,
            "width": request.width,
            "height": request.height,
            "original_filename": request.original_filename,
            "sha256": request.sha256,
        }

        supabase = get_supabase_service_client()
        if supabase is None:
            return PhotoOut.model_validate(payload)

        try:
            response = supabase.table("photos").insert(payload).execute()
        except Exception as exc:
            print(f"Supabase photo record insert failed: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create photo record",
            ) from exc

        row = response.data[0] if response.data else payload
        return PhotoOut.model_validate(row)

    def upload_photo(
        self,
        user_id: str | None,
        client_install_id: str | None,
        content: bytes,
        filename: str | None,
        mime_type: str | None,
        width: int | None,
        height: int | None,
    ) -> PhotoOut:
        settings = get_settings()
        photo_id = uuid4()
        mime_type = mime_type or "application/octet-stream"
        extension = self._extension_for(mime_type, filename)
        owner_segment = f"users/{user_id}" if user_id else f"installs/{client_install_id or settings.demo_user_id}"
        local_storage_path = f"{owner_segment}/{photo_id}.{extension}"
        digest = hashlib.sha256(content).hexdigest()
        self._write_local_photo(local_storage_path, content)
        remote_location = self._upload_remote_photo(
            local_storage_path=local_storage_path,
            photo_id=photo_id,
            owner_segment=owner_segment,
            content=content,
            filename=filename,
            mime_type=mime_type,
        )

        return self.create_photo(
            user_id=user_id,
            client_install_id=client_install_id,
            request=CreatePhotoRequest(
                storage_bucket=remote_location.bucket,
                storage_path=remote_location.path,
                mime_type=mime_type,
                width=width,
                height=height,
                original_filename=filename,
                sha256=digest,
            ),
        )

    def get_public_photo_url(self, photo_id: UUID) -> str | None:
        supabase = get_supabase_service_client()
        if supabase is None:
            return None

        response = supabase.table("photos").select("storage_bucket,storage_path").eq("id", str(photo_id)).single().execute()
        if not response.data:
            return None

        bucket = response.data["storage_bucket"]
        path = response.data["storage_path"]
        if bucket == "cloudinary":
            return path

        try:
            signed = supabase.storage.from_(bucket).create_signed_url(path, 600)
            if isinstance(signed, str):
                return signed
            if not isinstance(signed, dict):
                return None
            data = signed.get("data")
            nested = data if isinstance(data, dict) else {}
            return (
                signed.get("signedURL")
                or signed.get("signedUrl")
                or signed.get("signed_url")
                or nested.get("signedUrl")
                or nested.get("signedURL")
            )
        except Exception as exc:
            print(f"Supabase signed URL unavailable: {exc}")
            return None

    def get_photo_bytes(self, photo_id: UUID) -> tuple[bytes | None, str | None]:
        storage_path: str | None = None
        mime_type: str | None = None
        supabase = get_supabase_service_client()

        if supabase is not None:
            try:
                response = (
                    supabase
                    .table("photos")
                    .select("storage_path,mime_type")
                    .eq("id", str(photo_id))
                    .single()
                    .execute()
                )
                if response.data:
                    storage_path = response.data.get("storage_path")
                    mime_type = response.data.get("mime_type")
            except Exception:
                storage_path = None

        path = self._local_path(storage_path) if storage_path else None
        if path is None or not path.exists():
            path = self._find_local_photo(photo_id)
        if path is None or not path.exists():
            return None, mime_type

        return path.read_bytes(), mime_type or mimetypes.guess_type(path.name)[0] or "image/jpeg"

    def _upload_remote_photo(
        self,
        local_storage_path: str,
        photo_id: UUID,
        owner_segment: str,
        content: bytes,
        filename: str | None,
        mime_type: str,
    ) -> PhotoStorageLocation:
        settings = get_settings()
        provider = settings.image_storage_provider

        if provider in {"auto", "cloudinary"} and settings.cloudinary_configured:
            try:
                return self._upload_cloudinary_photo(
                    photo_id=photo_id,
                    owner_segment=owner_segment,
                    content=content,
                    filename=filename,
                    mime_type=mime_type,
                )
            except Exception as exc:
                print(f"Cloudinary upload skipped: {exc}")
                if provider == "cloudinary":
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Failed to upload photo to Cloudinary",
                    ) from exc

        if provider == "cloudinary" and not settings.cloudinary_configured:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cloudinary storage is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.",
            )

        if provider in {"auto", "supabase"}:
            supabase_location = self._upload_supabase_photo(
                storage_path=local_storage_path,
                content=content,
                mime_type=mime_type,
            )
            if supabase_location is not None:
                return supabase_location

        return PhotoStorageLocation(bucket="local", path=local_storage_path)

    def _upload_cloudinary_photo(
        self,
        photo_id: UUID,
        owner_segment: str,
        content: bytes,
        filename: str | None,
        mime_type: str,
    ) -> PhotoStorageLocation:
        settings = get_settings()
        cloud_name = settings.resolved_cloudinary_cloud_name
        api_key = settings.resolved_cloudinary_api_key
        api_secret = settings.resolved_cloudinary_api_secret
        if not cloud_name or not api_key or not api_secret:
            raise RuntimeError("Cloudinary is not configured")

        timestamp = str(int(time.time()))
        folder = settings.cloudinary_folder.strip("/")
        public_id = f"{folder}/{owner_segment}/{photo_id}" if folder else f"{owner_segment}/{photo_id}"
        upload_params = {
            "public_id": public_id,
            "timestamp": timestamp,
        }
        signature = self._cloudinary_signature(upload_params, api_secret)
        url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
        files = {
            "file": (
                filename or f"{photo_id}.{self._extension_for(mime_type, filename)}",
                content,
                mime_type,
            )
        }
        data = {
            **upload_params,
            "api_key": api_key,
            "signature": signature,
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, data=data, files=files)
            response.raise_for_status()

        payload = response.json()
        secure_url = payload.get("secure_url")
        if not isinstance(secure_url, str) or not secure_url:
            raise RuntimeError("Cloudinary upload response did not include secure_url")

        return PhotoStorageLocation(bucket="cloudinary", path=secure_url)

    def _upload_supabase_photo(
        self,
        storage_path: str,
        content: bytes,
        mime_type: str,
    ) -> PhotoStorageLocation | None:
        settings = get_settings()
        supabase = get_supabase_service_client()
        if supabase is None:
            return None

        try:
            supabase.storage.from_(settings.supabase_storage_bucket).upload(
                storage_path,
                content,
                file_options={
                    "content-type": mime_type,
                    "upsert": "false",
                },
            )
        except Exception as exc:
            print(f"Supabase storage upload skipped: {exc}")
            if settings.supabase_storage_required:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to upload photo to storage",
                ) from exc
            return None

        return PhotoStorageLocation(bucket=settings.supabase_storage_bucket, path=storage_path)

    @staticmethod
    def _cloudinary_signature(params: dict[str, str], api_secret: str) -> str:
        canonical = "&".join(f"{key}={value}" for key, value in sorted(params.items()) if value)
        return hashlib.sha1(f"{canonical}{api_secret}".encode("utf-8")).hexdigest()

    @staticmethod
    def _extension_for(mime_type: str, filename: str | None) -> str:
        if filename and "." in filename:
            candidate = filename.rsplit(".", 1)[1].lower()
            if candidate in {"jpg", "jpeg", "png", "heic", "heif", "webp"}:
                return "jpg" if candidate == "jpeg" else candidate

        if mime_type == "image/jpeg":
            return "jpg"
        if mime_type == "image/heic":
            return "heic"
        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed.lstrip(".")
        return "bin"

    @classmethod
    def _local_root(cls) -> Path:
        return Path(__file__).resolve().parents[2] / ".data" / "photos"

    @classmethod
    def _local_path(cls, storage_path: str | None) -> Path | None:
        if not storage_path:
            return None
        clean_parts = [part for part in storage_path.split("/") if part and part not in {".", ".."}]
        return cls._local_root().joinpath(*clean_parts)

    @classmethod
    def _write_local_photo(cls, storage_path: str, content: bytes) -> None:
        path = cls._local_path(storage_path)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    @classmethod
    def _find_local_photo(cls, photo_id: UUID) -> Path | None:
        root = cls._local_root()
        if not root.exists():
            return None
        return next(root.rglob(f"{photo_id}.*"), None)
