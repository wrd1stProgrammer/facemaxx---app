"""Bound server-side retry/staging images; permanent history belongs on the device."""
import asyncio
import fcntl
import logging
import time
from pathlib import Path

from app.repositories.photo_repository import PhotoRepository

logger = logging.getLogger(__name__)
RETENTION_SECONDS = 3600


def cleanup_expired_images() -> None:
    cutoff = time.time() - RETENTION_SECONDS
    photos = PhotoRepository._local_root() / "ephemeral"
    if photos.exists():
        for path in photos.rglob("*"):
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
    studio = Path(__file__).resolve().parents[2] / ".data" / "style-studio"
    if studio.exists():
        for marker in studio.glob("*/*.device"):
            path = marker.with_suffix(".json")
            try:
                with path.with_suffix(".lock").open("a") as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        continue
                    if path.exists() and path.stat().st_mtime < cutoff:
                        path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass


async def cleanup_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(cleanup_expired_images)
        except Exception:
            logger.exception("Temporary image cleanup failed")
        await asyncio.sleep(300)
