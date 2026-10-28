from __future__ import annotations

import fcntl
import hashlib
import logging
import os
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from openai import OpenAIError

from app.api.deps import RequestIdentity, get_request_identity
from app.core.config import get_settings
from app.repositories.purchase_repository import PurchaseRepository
from app.schemas.style_studio import StudioRequest, StudioResponse
from app.services.style_studio import decode_photo, generate_style

router = APIRouter(prefix="/style-studio", tags=["style-studio"])
logger = logging.getLogger(__name__)
RESULT_ROOT = Path(__file__).resolve().parents[3] / ".data" / "style-studio"


async def studio_identity(request: Request, identity: RequestIdentity = Depends(get_request_identity)) -> RequestIdentity:
    if (
        os.environ.get("FACEMAXX_LOCAL_SIMULATOR_TEST") == "1"
        and request.client is not None
        and request.client.host in {"127.0.0.1", "::1"}
        and request.headers.get("X-Facemaxx-Simulator-Test") == "1"
    ):
        return replace(identity, reviewer_demo_unlimited=True)
    return identity


@router.delete("/previews/{preview_id}")
async def delete_preview(preview_id: UUID, identity: RequestIdentity = Depends(get_request_identity)) -> dict[str, str]:
    owner = PurchaseRepository.app_user_id_for_identity(identity)
    directory = RESULT_ROOT / hashlib.sha256(owner.encode()).hexdigest()
    if not directory.exists():
        return {"status": "deleted"}
    with (directory / f"{preview_id}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise HTTPException(409, "Wait for generation to finish before deleting") from exc
        # Keep the input fingerprint as a receipt: retries must not charge again.
        suffixes = (".json", ".tmp") if (directory / f"{preview_id}.device").exists() else (".json", ".sha256", ".tmp")
        for suffix in suffixes:
            (directory / f"{preview_id}{suffix}").unlink(missing_ok=True)
    return {"status": "deleted"}


@router.post("/previews", response_model=StudioResponse)
async def create_preview(
    payload: StudioRequest,
    identity: RequestIdentity = Depends(studio_identity),
    x_facemaxx_device_storage: str | None = Header(default=None),
) -> StudioResponse:
    if not get_settings().openai_api_key:
        raise HTTPException(503, "Style Studio is not configured yet")
    decode_photo(payload.photo_base64)
    if payload.reference_base64:
        decode_photo(payload.reference_base64)
    repository = PurchaseRepository()
    owner = repository.app_user_id_for_identity(identity)
    owner_hash = hashlib.sha256(owner.encode()).hexdigest()
    directory = RESULT_ROOT / owner_hash
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / f"{payload.request_id}.json"
    fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    fingerprint_path = directory / f"{payload.request_id}.sha256"
    # Cross-worker lock and durable cache make retries return the original paid result.
    with (directory / f"{payload.request_id}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise HTTPException(409, "This preview is still generating. Retry shortly.") from exc
        if result_path.exists():
            if fingerprint_path.read_text() != fingerprint:
                raise HTTPException(409, "Use a new request ID for a different style")
            return StudioResponse.model_validate_json(result_path.read_text())
        if fingerprint_path.exists():
            raise HTTPException(410, "This preview was saved or expired. Use a new request ID to generate again.")
        reservation = await anyio.to_thread.run_sync(repository.reserve_pro_scan, identity)
        if not reservation.allowed:
            raise HTTPException(402, "A paid scan credit is required")
        if getattr(reservation, "consumed_source", None) == "free_trial":
            await anyio.to_thread.run_sync(repository.refund_reserved_credit, reservation)
            raise HTTPException(402, "The free trial is only available for proportions analysis")
        completed = False
        try:
            with anyio.fail_after(540):
                result = await generate_style(payload)
            fingerprint_path.write_text(fingerprint)
            temporary = result_path.with_suffix(".tmp")
            temporary.write_text(result.model_dump_json())
            temporary.replace(result_path)
            if x_facemaxx_device_storage == "1":
                (directory / f"{payload.request_id}.device").touch()
            completed = True
            return result
        except (OpenAIError, TimeoutError) as exc:
            logger.warning("Style generation failed: %s", type(exc).__name__)
            raise HTTPException(502, "Preview generation failed. Your credit will be returned; please retry.") from exc
        finally:
            if not completed:
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(repository.refund_reserved_credit, reservation)
