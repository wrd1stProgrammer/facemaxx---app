from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistProductSessionResponse
from app.services.flirtist_product_service import FlirtistProductService


class FlirtistProductFallbackTest(unittest.TestCase):
    def test_reply_fallback_uses_chat_context_when_ai_is_unavailable(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            text="Them: 나 오늘 회계 시험 붙었어 드디어 끝났다\nMe: 진짜? 완전 축하해",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        pack_text = " ".join(
            reply.text
            for pack in response.replyCoaching.replyPacks
            for reply in pack.replies
        )
        self.assertRegex(reply_text, "회계|시험|축하")
        self.assertRegex(pack_text, "회계|시험|축하")
        self.assertNotIn("회사", reply_text)
        self.assertNotIn("힘 빠졌겠다", pack_text)


class NoopAI:
    def complete_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        fallback: FlirtistProductSessionResponse,
        image_url: str | None,
    ) -> FlirtistProductSessionResponse:
        return fallback


class NoopImageStorage:
    def store_session_image(
        self,
        request: FlirtistProductSessionRequest,
        *,
        user_id: str | None = None,
        client_install_id: str | None = None,
    ) -> None:
        return None


class NoopRepository:
    def save_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        response: FlirtistProductSessionResponse,
        stored_image: None,
        user_id: str | None = None,
        client_install_id: str | None = None,
    ) -> bool:
        return False


if __name__ == "__main__":
    unittest.main()
