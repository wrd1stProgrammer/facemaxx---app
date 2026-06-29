from __future__ import annotations

import unittest
from typing import get_args

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistReplyStyleRequest
from app.services.flirtist_product_ai_prompts import _session_prompt
from app.services.flirtist_product_ai_prompts import _style_prompt
from app.services.flirtist_product_reply_fallback import reply_coaching
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopAI
from tests.test_flirtist_product_fallback import NoopImageStorage
from tests.test_flirtist_product_fallback import NoopRepository


SUPPORTED_FLIRTIST_LANGUAGES = (
    "en",
    "ko",
    "ja",
    "zh-Hant",
    "es-MX",
    "pt-BR",
    "fr",
    "de",
    "th",
    "id",
)


class FlirtistProductI18nTest(unittest.TestCase):
    def test_flirtist_language_contract_matches_app_store_launch_locales(self) -> None:
        self.assertEqual(set(get_args(FlirtistLanguage)), set(SUPPORTED_FLIRTIST_LANGUAGES))

    def test_session_prompt_adds_culture_guidance_for_japanese(self) -> None:
        service = FlirtistProductService(
            repository=NoopRepository(),
            image_storage=NoopImageStorage(),
            ai=NoopAI(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="manual",
            language="ja",
            locale="ja-JP",
            text="Them: 今なにしてる？\nMe: 家でゆっくりしてる",
        )
        fallback = service.create_session(request)

        prompt = _session_prompt(request, fallback)

        self.assertIn("Japanese", prompt)
        self.assertIn("LINE", prompt)
        self.assertIn("Me should send next to Them", prompt)

    def test_style_prompt_adds_culture_guidance_for_brazilian_portuguese(self) -> None:
        fallback = reply_coaching("pt-BR", "genuine")
        request = FlirtistReplyStyleRequest(
            language="pt-BR",
            locale="pt-BR",
            context="Them: hoje foi puxado\nMe: quer distrair um pouco?",
            baseReply="quer distrair um pouco?",
            style="flirty",
        )

        prompt = _style_prompt(request, fallback)

        self.assertIn("Brazilian Portuguese", prompt)
        self.assertIn("WhatsApp", prompt)
        self.assertIn("Never produce a reply that Them would send to Me", prompt)
