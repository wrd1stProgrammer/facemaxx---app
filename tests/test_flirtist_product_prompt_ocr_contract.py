from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistReplyStyleRequest
from app.schemas.flirtist_product import FlirtistReplyStyleResponse
from app.services.flirtist_product_ai import _session_prompt
from app.services.flirtist_product_ai import _style_prompt
from app.services.flirtist_product_reply_fallback import reply_coaching
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopAI
from tests.test_flirtist_product_fallback import NoopImageStorage
from tests.test_flirtist_product_fallback import NoopRepository


class FlirtistProductPromptOCRContractTest(unittest.TestCase):
    def test_session_prompt_excludes_non_chat_ocr_text_from_reasoning(self) -> None:
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
            text="LTE\nThem: 오늘 회사가 정신이 하나도 없었어\nMe: 그래도 퇴근은 했어?",
        )
        fallback = service.create_session(request)

        # When
        prompt = _session_prompt(request, fallback)

        # Then
        self.assertIn("Only use text that belongs to visible chat bubbles", prompt)
        self.assertIn("Do not use status bars, navigation bars, dates, timestamps, notification badges", prompt)
        self.assertIn("chatPreview must contain only Me/Them chat messages", prompt)

    def test_style_prompt_excludes_non_chat_ocr_text_from_regeneration_context(self) -> None:
        # Given
        request = FlirtistReplyStyleRequest(
            locale="ko-KR",
            context="LTE\nThem: 오늘 회사가 정신이 하나도 없었어\nMe: 그래도 퇴근은 했어?",
            baseReply="퇴근했으면 오늘은 조금 풀어도 되겠다.",
            style="genuine",
        )
        fallback = FlirtistReplyStyleResponse(
            sessionId="flt_prompt_test",
            replyCoaching=reply_coaching("ko", request.style, focus=request.focus),
        )

        # When
        prompt = _style_prompt(request, fallback)

        # Then
        self.assertIn("Only use text that belongs to visible chat bubbles", prompt)
        self.assertIn("Do not use status bars, navigation bars, dates, timestamps, notification badges", prompt)
