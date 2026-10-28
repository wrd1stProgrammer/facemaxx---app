import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.repositories.photo_repository import PhotoRepository, PhotoStorageLocation
from app.services.transient_image_cleanup import cleanup_expired_images, RETENTION_SECONDS


class TransientPhotoTests(unittest.TestCase):
    def test_legacy_photo_preserves_remote_storage_without_opt_in(self):
        repository = PhotoRepository()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(PhotoRepository, "_local_root", return_value=Path(directory)), \
                patch("app.repositories.photo_repository.get_settings", return_value=SimpleNamespace(demo_user_id="demo")), \
                patch.object(repository, "_upload_remote_photo", return_value=PhotoStorageLocation("cloudinary", "https://example.test/photo.jpg")) as remote, \
                patch.object(repository, "create_photo") as record:
            repository.upload_photo(None, "guest", b"image", "photo.jpg", "image/jpeg", 100, 100)
            remote.assert_called_once()
            self.assertFalse(remote.call_args.kwargs["local_storage_path"].startswith("ephemeral/"))
            self.assertEqual(record.call_args.kwargs["request"].storage_bucket, "cloudinary")

    def test_new_photo_never_uploads_to_cloud_storage(self):
        repository = PhotoRepository()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(PhotoRepository, "_local_root", return_value=Path(directory)), \
                patch("app.repositories.photo_repository.get_settings", return_value=SimpleNamespace(demo_user_id="demo")), \
                patch.object(repository, "_upload_remote_photo") as remote, \
                patch.object(repository, "create_photo") as record:
            repository.upload_photo(None, "guest", b"image", "photo.jpg", "image/jpeg", 100, 100, device_storage=True)
            remote.assert_not_called()
            request = record.call_args.kwargs["request"]
            self.assertEqual(request.storage_bucket, "temporary")
            self.assertTrue(request.storage_path.startswith("ephemeral/installs/guest/"))
            self.assertEqual((Path(directory) / request.storage_path).read_bytes(), b"image")

    def test_cleanup_removes_expired_staging_not_legacy_photos(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(PhotoRepository, "_local_root", return_value=Path(directory)):
            root = Path(directory)
            (root / "ephemeral").mkdir()
            old = root / "ephemeral/old.jpg"
            fresh = root / "ephemeral/fresh.jpg"
            legacy = root / "legacy.jpg"
            for path in (old, fresh, legacy):
                path.write_bytes(b"image")
            expired = time.time() - RETENTION_SECONDS - 60
            os.utime(old, (expired, expired))
            os.utime(legacy, (expired, expired))
            # Isolate style cache discovery too; this test must never touch local assets.
            with patch("app.services.transient_image_cleanup.Path", return_value=root / "missing/services/cleanup.py"):
                cleanup_expired_images()
            self.assertFalse(old.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(legacy.exists())

    def test_style_cleanup_only_removes_device_opted_in_results(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(PhotoRepository, "_local_root", return_value=Path(directory) / "photos"):
            root = Path(directory)
            studio = root / ".data/style-studio/owner"
            studio.mkdir(parents=True)
            legacy = studio / "legacy.json"
            modern = studio / "modern.json"
            for path in (legacy, modern):
                path.write_text("{}")
                expired = time.time() - RETENTION_SECONDS - 60
                os.utime(path, (expired, expired))
            modern.with_suffix(".device").touch()
            with patch("app.services.transient_image_cleanup.Path", return_value=root / "missing/services/cleanup.py"):
                cleanup_expired_images()
            self.assertTrue(legacy.exists())
            self.assertFalse(modern.exists())
