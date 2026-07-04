from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.services.flirtist_config import FlirtistAIConfig
from app.services.flirtist_product_ai import FlirtistProductAI
from app.services.flirtist_product_service import _fallback_session


class FlirtistProductOpenAITimeoutTest(unittest.TestCase):
    def test_screenshot_sessions_use_vision_timeout_when_image_url_is_present(self) -> None:
        # Given
        captured_timeouts: list[float] = []
        fake_openai = _fake_openai_module(captured_timeouts)
        ai = FlirtistProductAI(
            config=FlirtistAIConfig(
                requested_provider="openai",
                effective_provider="openai",
                openai_model="gpt-test",
                anthropic_model="claude-test",
                gemini_model="gemini-test",
            )
        )

        # When / Then
        for mode, expected_timeout in (("reply_coach", 55.0), ("score_analysis", 45.0)):
            captured_timeouts.clear()
            request = FlirtistProductSessionRequest(mode=mode, source="screenshot", locale="ko-KR")
            with patch.dict(os.environ, {"FLIRTIST_OPENAI_API_KEY": "sk-test"}), patch.dict(
                sys.modules,
                {"openai": fake_openai},
            ):
                ai.complete_session(
                    request=request,
                    fallback=_fallback_session(request, None),
                    image_url="https://res.cloudinary.com/flirtcue/screenshot.jpg",
                )
            self.assertEqual(captured_timeouts, [expected_timeout])


def _fake_openai_module(captured_timeouts: list[float]) -> types.ModuleType:
    fake_openai = types.ModuleType("openai")

    class FakeOpenAIError(Exception):
        pass

    class FakeResponse:
        output_text = "{}"

    class FakeResponses:
        def create(self, **_kwargs) -> FakeResponse:
            return FakeResponse()

    class FakeOpenAI:
        def __init__(self, *, api_key: str, timeout: float) -> None:
            captured_timeouts.append(timeout)
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    fake_openai.OpenAIError = FakeOpenAIError
    return fake_openai
