from __future__ import annotations

import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.analysis import PhotoOut
from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistProductSessionResponse
from app.services.flirtist_product_ai import FlirtistProductAIError
from app.services.flirtist_product_image_storage import FlirtistProductImageStorage
from app.services.flirtist_product_image_storage import FlirtistStoredImage
from app.services.flirtist_product_service import FlirtistProductService


class FlirtistProductApiTest(unittest.TestCase):
    def setUp(self) -> None:
        def fake_store_session_image(
            request: FlirtistProductSessionRequest,
            *,
            user_id: str | None = None,
            client_install_id: str | None = None,
        ) -> FlirtistStoredImage | None:
            if not request.imageBase64:
                return None
            return FlirtistStoredImage(
                url="https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg",
                storage_path="flirtist/test.jpg",
                mime_type=request.imageMimeType,
            )

        self.supabase_patch = patch(
            "app.services.flirtist_product_repository.get_supabase_service_client",
            return_value=None,
        )
        self.image_patch = patch(
            "app.services.flirtist_product_image_storage.FlirtistProductImageStorage.store_session_image",
            side_effect=fake_store_session_image,
        )
        self.env_patch = patch.dict("os.environ", {"FLIRTIST_AI_PROVIDER": "mock"}, clear=False)
        self.env_patch.start()
        self.supabase_patch.start()
        self.image_patch.start()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.image_patch.stop()
        self.supabase_patch.stop()
        self.env_patch.stop()

    def test_reply_session_returns_album_ready_coaching_when_text_is_submitted(self) -> None:
        # Given
        payload = {
            "mode": "reply_coach",
            "source": "manual",
            "locale": "ko-KR",
            "text": "상대: 오늘 회사가 정신이 하나도 없었어\n나: 그래도 퇴근할 수 있지?",
        }

        # When
        response = self.client.post("/api/flirtist/sessions", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode"], "reply_coach")
        self.assertEqual(data["source"], "manual")
        self.assertRegex(data["sessionId"], re.compile(r"^flt_"))
        self.assertTrue(data["saved"])
        self.assertGreaterEqual(len(data["chatPreview"]), 2)
        self.assertIsNotNone(data["replyCoaching"])
        self.assertGreaterEqual(len(data["replyCoaching"]["replies"]), 1)
        self.assertEqual(len(data["replyCoaching"]["replyPacks"]), 5)
        self.assertEqual(
            {pack["style"] for pack in data["replyCoaching"]["replyPacks"]},
            {"genuine", "nsfw", "flirty", "witty", "romantic"},
        )
        self.assertEqual(len(data["replyCoaching"]["replies"]), 4)
        self.assertTrue(all(len(pack["replies"]) == 4 for pack in data["replyCoaching"]["replyPacks"]))
        self.assertRegex(data["replyCoaching"]["replies"][0]["text"], re.compile("[가-힣]"))

    def test_score_session_returns_wrapped_card_when_screenshot_is_submitted(self) -> None:
        # Given
        payload = {
            "mode": "score_analysis",
            "source": "screenshot",
            "locale": "en-US",
            "imageBase64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
            "imageMimeType": "image/png",
        }

        # When
        response = self.client.post("/api/flirtist/sessions", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode"], "score_analysis")
        self.assertEqual(data["source"], "screenshot")
        self.assertIsNone(data["replyCoaching"])
        self.assertIsNotNone(data["analysisCard"])
        self.assertGreaterEqual(data["analysisCard"]["compatibilityScore"], 0)
        self.assertLessEqual(data["analysisCard"]["compatibilityScore"], 100)
        self.assertGreaterEqual(len(data["analysisCard"]["redFlags"]), 1)
        self.assertNotIn(payload["imageBase64"], data["title"])
        self.assertTrue(data["imageUrl"].startswith("https://res.cloudinary.com/"))

    def test_score_session_returns_failure_when_live_analysis_fails(self) -> None:
        # Given
        payload = {
            "mode": "score_analysis",
            "source": "screenshot",
            "locale": "ko-KR",
            "text": "Them: 오늘 회사가 정신이 하나도 없었어\nMe: 그래도 퇴근할 수 있지?",
        }

        # When
        with patch(
            "app.services.flirtist_product_service.FlirtistProductService.create_session",
            side_effect=FlirtistProductAIError(reason="분석에 실패했습니다. 잠시 후 다시 시도해 주세요."),
        ):
            response = self.client.post("/api/flirtist/sessions", json=payload)

        # Then
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "분석에 실패했습니다. 잠시 후 다시 시도해 주세요.")

    def test_session_upload_passes_install_id_header_to_image_storage(self) -> None:
        # Given
        install_id = "11111111-2222-3333-4444-555555555555"
        captured_client_install_ids: list[str | None] = []

        def fake_store_session_image(
            request: FlirtistProductSessionRequest,
            *,
            user_id: str | None = None,
            client_install_id: str | None = None,
        ) -> FlirtistStoredImage | None:
            captured_client_install_ids.append(client_install_id)
            return FlirtistStoredImage(
                url="https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg",
                storage_path="flirtist/test.jpg",
                mime_type=request.imageMimeType,
            )

        payload = {
            "mode": "reply_coach",
            "source": "screenshot",
            "locale": "ko-KR",
            "imageBase64": "aW1hZ2U=",
            "imageMimeType": "image/jpeg",
        }

        # When
        with patch(
            "app.services.flirtist_product_image_storage.FlirtistProductImageStorage.store_session_image",
            side_effect=fake_store_session_image,
        ):
            response = self.client.post(
                "/api/flirtist/sessions",
                json=payload,
                headers={"X-Facemaxx-Install-Id": install_id},
            )

        # Then
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_client_install_ids, [install_id])

    def test_session_upload_accepts_install_id_when_supabase_auth_is_enabled(self) -> None:
        # Given
        install_id = "11111111-2222-3333-4444-555555555555"
        settings = SimpleNamespace(
            auth_disabled=False,
            reviewer_demo_enabled=False,
            reviewer_demo_access_code=None,
            demo_user_id="00000000-0000-0000-0000-000000000001",
        )
        payload = {
            "mode": "reply_coach",
            "source": "manual",
            "locale": "ko-KR",
            "text": "상대: 오늘 회사가 정신이 하나도 없었어",
        }

        # When
        with patch("app.api.deps.get_settings", return_value=settings):
            response = self.client.post(
                "/api/flirtist/sessions",
                json=payload,
                headers={"X-Facemaxx-Install-Id": install_id},
            )

        # Then
        self.assertEqual(response.status_code, 200)

    def test_image_storage_uses_install_id_for_photo_record_when_screenshot_is_stored(self) -> None:
        # Given
        self.image_patch.stop()
        install_id = "11111111-2222-3333-4444-555555555555"

        class CapturingPhotoRepository:
            captured_client_install_id: str | None = None

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
                self.captured_client_install_id = client_install_id
                return PhotoOut(
                    id="22222222-2222-2222-2222-222222222222",
                    storage_bucket="cloudinary",
                    storage_path="https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg",
                    mime_type=mime_type,
                    width=width,
                    height=height,
                    sha256=None,
                )

        repository = CapturingPhotoRepository()
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            imageBase64="aW1hZ2U=",
            imageMimeType="image/jpeg",
        )
        settings = SimpleNamespace(
            image_storage_provider="cloudinary",
            cloudinary_configured=True,
            demo_user_id="00000000-0000-0000-0000-000000000001",
        )

        # When
        with patch("app.services.flirtist_product_image_storage.get_settings", return_value=settings):
            stored_image = FlirtistProductImageStorage(photo_repository=repository).store_session_image(
                request,
                client_install_id=install_id,
            )

        # Then
        self.assertEqual(repository.captured_client_install_id, install_id)
        self.assertEqual(stored_image.url, "https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg")

    def test_product_service_sends_cloudinary_url_to_openai_when_screenshot_is_submitted(self) -> None:
        # Given
        class CapturingAI:
            image_url: str | None = None

            def complete_session(
                self,
                *,
                request: FlirtistProductSessionRequest,
                fallback: FlirtistProductSessionResponse,
                image_url: str | None,
            ) -> FlirtistProductSessionResponse:
                self.image_url = image_url
                return fallback

        class NoopRepository:
            def save_session(
                self,
                *,
                request: FlirtistProductSessionRequest,
                response: FlirtistProductSessionResponse,
                stored_image: FlirtistStoredImage | None,
                user_id: str | None = None,
                client_install_id: str | None = None,
            ) -> bool:
                return False

        class FixedImageStorage:
            def store_session_image(
                self,
                request: FlirtistProductSessionRequest,
                *,
                user_id: str | None = None,
                client_install_id: str | None = None,
            ) -> FlirtistStoredImage | None:
                return FlirtistStoredImage(
                    url="https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg",
                    storage_path="flirtist/test.jpg",
                    mime_type="image/jpeg",
                )

        ai = CapturingAI()
        service = FlirtistProductService(
            ai=ai,
            repository=NoopRepository(),
            image_storage=FixedImageStorage(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="en-US",
            imageBase64="aW1hZ2U=",
            imageMimeType="image/jpeg",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertEqual(response.imageUrl, "https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg")
        self.assertEqual(ai.image_url, response.imageUrl)

    def test_score_session_sends_cloudinary_url_to_ai_when_screenshot_is_submitted(self) -> None:
        # Given
        class CapturingAI:
            image_url: str | None = None

            def complete_session(
                self,
                *,
                request: FlirtistProductSessionRequest,
                fallback: FlirtistProductSessionResponse,
                image_url: str | None,
            ) -> FlirtistProductSessionResponse:
                self.image_url = image_url
                return fallback

        class NoopRepository:
            def save_session(
                self,
                *,
                request: FlirtistProductSessionRequest,
                response: FlirtistProductSessionResponse,
                stored_image: FlirtistStoredImage | None,
                user_id: str | None = None,
                client_install_id: str | None = None,
            ) -> bool:
                return False

        class FixedImageStorage:
            def store_session_image(
                self,
                request: FlirtistProductSessionRequest,
                *,
                user_id: str | None = None,
                client_install_id: str | None = None,
            ) -> FlirtistStoredImage | None:
                return FlirtistStoredImage(
                    url="https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg",
                    storage_path="flirtist/test.jpg",
                    mime_type="image/jpeg",
                )

        ai = CapturingAI()
        service = FlirtistProductService(
            ai=ai,
            repository=NoopRepository(),
            image_storage=FixedImageStorage(),
        )
        request = FlirtistProductSessionRequest(
            mode="score_analysis",
            source="screenshot",
            locale="ko-KR",
            text="Them: 오늘 회사가 정신이 하나도 없었어\nMe: 그래도 퇴근할 수 있지?",
            imageBase64="aW1hZ2U=",
            imageMimeType="image/jpeg",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertEqual(response.imageUrl, "https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg")
        self.assertEqual(ai.image_url, response.imageUrl)

    def test_product_service_prefers_screenshot_image_over_legacy_ocr_text(self) -> None:
        # Given
        class CapturingAI:
            image_url: str | None = None

            def complete_session(
                self,
                *,
                request: FlirtistProductSessionRequest,
                fallback: FlirtistProductSessionResponse,
                image_url: str | None,
            ) -> FlirtistProductSessionResponse:
                self.image_url = image_url
                return fallback

        class NoopRepository:
            def save_session(
                self,
                *,
                request: FlirtistProductSessionRequest,
                response: FlirtistProductSessionResponse,
                stored_image: FlirtistStoredImage | None,
                user_id: str | None = None,
                client_install_id: str | None = None,
            ) -> bool:
                return False

        class FixedImageStorage:
            def store_session_image(
                self,
                request: FlirtistProductSessionRequest,
                *,
                user_id: str | None = None,
                client_install_id: str | None = None,
            ) -> FlirtistStoredImage | None:
                return FlirtistStoredImage(
                    url="https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg",
                    storage_path="flirtist/test.jpg",
                    mime_type="image/jpeg",
                )

        ai = CapturingAI()
        service = FlirtistProductService(
            ai=ai,
            repository=NoopRepository(),
            image_storage=FixedImageStorage(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            text="상대: 웅 조아네\n나: 나중에 광주 올 일 생기면 미리 연락해 맛난거 사줄게",
            imageBase64="aW1hZ2U=",
            imageMimeType="image/jpeg",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertEqual(response.imageUrl, "https://res.cloudinary.com/demo/image/upload/flirtist/test.jpg")
        self.assertEqual(response.imageStoragePath, "flirtist/test.jpg")
        self.assertEqual(ai.image_url, response.imageUrl)


if __name__ == "__main__":
    unittest.main()
