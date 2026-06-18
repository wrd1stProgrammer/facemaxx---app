from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistReplyStyleRequest
from app.schemas.flirtist_product import FlirtistReplyStyleResponse
from app.services.flirtist_product_ai import _session_prompt, _style_prompt
from app.services.flirtist_product_reply_fallback import reply_coaching
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopAI, NoopImageStorage, NoopRepository


class FlirtistProductPromptTest(unittest.TestCase):
    def test_session_prompt_uses_quality_rubric_without_leaking_fallback_reply_text(self) -> None:
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
            text="Them: 오늘 너 생각났어 약간 웃겼음\nMe: 왜 갑자기?",
        )
        fallback = service.create_session(request)

        # When
        prompt = _session_prompt(request, fallback)

        # Then
        self.assertIn("Quality bar", prompt)
        self.assertIn("Do not copy fallback wording", prompt)
        self.assertIn("would be wrong for a different chat", prompt)
        self.assertIn("<copy-ready reply text>", prompt)
        self.assertNotIn("얘기 조금 더 듣고 싶어", prompt)
        self.assertNotIn("그 말 괜히 좋네", prompt)

    def test_style_prompt_treats_contract_as_shape_not_reply_source(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistReplyStyleRequest(
            locale="ko-KR",
            context="Them: 오늘 너 생각났어 약간 웃겼음\nMe: 왜 갑자기?",
            baseReply="그 말 괜히 좋네. 뭐 보고 내 생각났는데?",
            style="flirty",
        )
        fallback = FlirtistReplyStyleResponse(
            sessionId="flt_prompt_test",
            replyCoaching=reply_coaching("ko", request.style, focus=request.focus),
        )

        # When
        prompt = _style_prompt(request, fallback)

        # Then
        self.assertIn("Do not copy fallback wording", prompt)
        self.assertIn("<copy-ready reply text>", prompt)
        self.assertEqual(prompt.count("그 말 괜히 좋네"), 1)
        self.assertNotIn("갑자기 그렇게 말하면", prompt)


if __name__ == "__main__":
    unittest.main()
