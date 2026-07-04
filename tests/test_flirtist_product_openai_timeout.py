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

    def test_openai_receives_inline_image_data_instead_of_refetching_cloudinary(self) -> None:
        # Given
        captured_image_urls: list[str] = []
        fake_openai = _fake_openai_module([], captured_image_urls)
        ai = FlirtistProductAI(
            config=FlirtistAIConfig(
                requested_provider="openai",
                effective_provider="openai",
                openai_model="gpt-test",
                anthropic_model="claude-test",
                gemini_model="gemini-test",
            )
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            imageBase64="aW1hZ2U=",
            imageMimeType="image/jpeg",
        )

        # When
        with patch.dict(os.environ, {"FLIRTIST_OPENAI_API_KEY": "sk-test"}), patch.dict(
            sys.modules,
            {"openai": fake_openai},
        ):
            ai.complete_session(
                request=request,
                fallback=_fallback_session(request, None),
                image_url="https://res.cloudinary.com/flirtcue/screenshot.jpg",
            )

        # Then
        self.assertEqual(captured_image_urls, ["data:image/jpeg;base64,aW1hZ2U="])


def _fake_openai_module(
    captured_timeouts: list[float],
    captured_image_urls: list[str] | None = None,
) -> types.ModuleType:
    fake_openai = types.ModuleType("openai")

    class FakeOpenAIError(Exception):
        pass

    class FakeResponse:
        output_text = "{}"

    class FakeResponses:
        def create(self, **kwargs) -> FakeResponse:
            if captured_image_urls is not None:
                for item in kwargs["input"][0]["content"]:
                    if item.get("type") == "input_image":
                        captured_image_urls.append(item["image_url"])
            return FakeResponse()

    class FakeOpenAI:
        def __init__(self, *, api_key: str, timeout: float) -> None:
            captured_timeouts.append(timeout)
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    fake_openai.OpenAIError = FakeOpenAIError
    return fake_openai
