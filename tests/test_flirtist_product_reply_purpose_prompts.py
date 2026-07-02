from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistReplyStyleRequest
from app.services.flirtist_product_ai_prompts import _session_prompt
from app.services.flirtist_product_ai_prompts import _style_prompt
from app.services.flirtist_product_reply_fallback import reply_coaching
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopAI
from tests.test_flirtist_product_fallback import NoopImageStorage
from tests.test_flirtist_product_fallback import NoopRepository


PURPOSE_RULES = (
    "genuine: keep the conversation easy to continue without pressure",
    "witty: create light banter from one real chat detail",
    "flirty: show interest clearly but do not overplay it",
    "romantic: give emotional steadiness or empathy without premature commitment",
    "nsfw: raise tension safely without explicit sexual content, coercion, or creepy pressure",
)


class FlirtistProductReplyPurposePromptTest(unittest.TestCase):
    def test_session_prompt_defines_reply_styles_by_purpose(self) -> None:
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
            text="Them: 웅 조아네\nMe: 광주 오면 맛난거 사줄게",
        )
        fallback = service.create_session(request)

        # When
        prompt = _session_prompt(request, fallback)

        # Then
        self.assertIn("Style purpose contract", prompt)
        for rule in PURPOSE_RULES:
            self.assertIn(rule, prompt)
        self.assertIn("whyItWorks must explain why that purpose fits this chat", prompt)

    def test_style_prompt_keeps_single_style_generation_on_the_same_purpose_contract(self) -> None:
        # Given
        request = FlirtistReplyStyleRequest(
            locale="ko-KR",
            context="Them: 웅 조아네\nMe: 광주 오면 맛난거 사줄게",
            baseReply="광주 오면 맛난 거 사준다는 약속 아직 유효해.",
            style="witty",
        )
        fallback = reply_coaching("ko", "witty")

        # When
        prompt = _style_prompt(request, fallback)

        # Then
        self.assertIn("Style purpose contract", prompt)
        for rule in PURPOSE_RULES:
            self.assertIn(rule, prompt)
        self.assertIn("The selected style must change the purpose, not just the adjectives", prompt)
