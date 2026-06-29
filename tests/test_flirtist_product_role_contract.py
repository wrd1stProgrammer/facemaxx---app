from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistReplyStyleRequest
from app.schemas.flirtist_product import FlirtistReplyStyleResponse
from app.services.flirtist_product_ai_prompts import _session_prompt, _style_prompt
from app.services.flirtist_product_reply_fallback import reply_coaching
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopAI, NoopImageStorage, NoopRepository


class FlirtistProductRoleContractTest(unittest.TestCase):
    def test_session_prompt_locks_screenshot_sides_to_user_reply_direction(self) -> None:
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            text="Them: 다녀와아앙\nMe: 나 운동 갔다올게",
        )
        fallback = service.create_session(request)

        prompt = _session_prompt(request, fallback)

        self.assertIn("Them = left-side incoming bubbles", prompt)
        self.assertIn("Me = right-side outgoing bubbles", prompt)
        self.assertIn("write what Me should send next to Them", prompt)
        self.assertIn("Never write the message Them should send to Me", prompt)

    def test_style_prompt_preserves_me_to_them_direction(self) -> None:
        request = FlirtistReplyStyleRequest(
            locale="ko-KR",
            context="Them: 다녀와아앙\nMe: 나 운동 갔다올게",
            baseReply="응 다녀와서 연락할게",
            style="flirty",
        )
        fallback = FlirtistReplyStyleResponse(
            sessionId="flt_role_contract",
            replyCoaching=reply_coaching("ko", "flirty"),
        )

        prompt = _style_prompt(request, fallback)

        self.assertIn("Rewrite as Me talking to Them", prompt)
        self.assertIn("Never produce a reply that Them would send to Me", prompt)
        self.assertIn("left-side incoming", prompt)
        self.assertIn("right-side outgoing", prompt)
