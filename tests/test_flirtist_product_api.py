from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.flirtist_product import FlirtistProductSessionRequest, FlirtistProductSessionResponse
from app.services.flirtist_product_image_storage import FlirtistStoredImage
from app.services.flirtist_product_service import FlirtistProductService


class FlirtistProductApiTest(unittest.TestCase):
    def setUp(self) -> None:
        def fake_store_session_image(request: FlirtistProductSessionRequest) -> FlirtistStoredImage | None:
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
        self.supabase_patch.start()
        self.image_patch.start()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.image_patch.stop()
        self.supabase_patch.stop()

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
            ) -> bool:
                return False

        class FixedImageStorage:
            def store_session_image(self, request: FlirtistProductSessionRequest) -> FlirtistStoredImage | None:
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

    def test_coach_chat_replies_with_training_message_and_suggestions(self) -> None:
        # Given
        payload = {
            "locale": "en-US",
            "message": "How do I ask her out after a slow chat?",
            "history": [
                {"role": "assistant", "text": "Tell me what the last message was."},
                {"role": "user", "text": "She said work has been chaotic."},
            ],
        }

        # When
        response = self.client.post("/api/flirtist/coach-chat", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertRegex(data["sessionId"], re.compile(r"^coach_"))
        self.assertEqual(data["message"]["role"], "assistant")
        self.assertGreater(len(data["message"]["text"]), 20)
        self.assertGreaterEqual(len(data["suggestions"]), 2)


if __name__ == "__main__":
    unittest.main()
