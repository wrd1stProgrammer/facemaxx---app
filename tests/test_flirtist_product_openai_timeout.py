from __future__ import annotations

import os
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.services.flirtist_config import FlirtistAIConfig
from app.services.flirtist_product_ai import (
    FlirtistOpenAIWallTimeout,
    FlirtistProductAI,
    FlirtistProductAIError,
    _create_openai_response,
)
from app.services.flirtist_product_image_storage import FlirtistStoredImage
from app.services.flirtist_product_service import FlirtistProductService, _fallback_session
from tests.test_flirtist_product_fallback import NoopRepository


class FlirtistProductOpenAITimeoutTest(unittest.TestCase):
    def test_openai_call_has_a_real_wall_clock_deadline(self) -> None:
        class SlowResponses:
            def create(self, **kwargs):
                time.sleep(0.25)
                return types.SimpleNamespace(output_text="{}")

        class SlowClient:
            responses = SlowResponses()

            def close(self) -> None:
                pass

        started = time.perf_counter()
        with self.assertRaises(FlirtistOpenAIWallTimeout):
            _create_openai_response(
                SlowClient(),
                timeout_seconds=0.05,
                request_kwargs={},
            )
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.15)

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

    def test_inline_screenshot_uses_bounded_vision_timeout(self) -> None:
        captured_timeouts: list[float] = []
        fake_openai = _fake_openai_module(captured_timeouts)
        ai = _openai_ai()

        for mode, expected_timeout in (("reply_coach", 40.0), ("score_analysis", 25.0)):
            captured_timeouts.clear()
            request = FlirtistProductSessionRequest(
                mode=mode,
                source="screenshot",
                locale="ko-KR",
                imageBase64="aW1hZ2U=",
                imageMimeType="image/jpeg",
            )
            with patch.dict(os.environ, {"FLIRTIST_OPENAI_API_KEY": "sk-test"}), patch.dict(
                sys.modules,
                {"openai": fake_openai},
            ):
                ai.complete_session(
                    request=request,
                    fallback=_fallback_session(request, None),
                    image_url=None,
                )

            self.assertEqual(captured_timeouts, [expected_timeout])

    def test_openai_client_disables_hidden_sdk_retries(self) -> None:
        # Given
        captured_max_retries: list[int] = []
        fake_openai = _fake_openai_module([], captured_max_retries=captured_max_retries)
        ai = _openai_ai()
        request = _screenshot_request()

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
        self.assertEqual(captured_max_retries, [0])

    def test_openai_retries_one_fast_connection_failure(self) -> None:
        # Given
        create_calls: list[int] = []
        fake_openai = _fake_openai_module(
            [],
            create_calls=create_calls,
            fail_first_connection=True,
        )
        ai = _openai_ai()
        request = _screenshot_request()

        # When
        with patch.dict(os.environ, {"FLIRTIST_OPENAI_API_KEY": "sk-test"}), patch.dict(
            sys.modules,
            {"openai": fake_openai},
        ):
            response = ai.complete_session(
                request=request,
                fallback=_fallback_session(request, None),
                image_url="https://res.cloudinary.com/flirtcue/screenshot.jpg",
            )

        # Then
        self.assertEqual(create_calls, [1, 2])
        self.assertEqual(response.mode, "score_analysis")

    def test_inline_openai_retries_one_timeout_within_total_budget(self) -> None:
        captured_timeouts: list[float] = []
        create_calls: list[int] = []
        fake_openai = _fake_openai_module(
            captured_timeouts,
            create_calls=create_calls,
            fail_first_timeout=True,
        )
        ai = _openai_ai()
        request = _screenshot_request()

        with patch.dict(os.environ, {"FLIRTIST_OPENAI_API_KEY": "sk-test"}), patch.dict(
            sys.modules,
            {"openai": fake_openai},
        ):
            response = ai.complete_session(
                request=request,
                fallback=_fallback_session(request, None),
                image_url=None,
            )

        self.assertEqual(create_calls, [1, 2])
        self.assertEqual(captured_timeouts, [25.0, 10.0])
        self.assertEqual(response.mode, "score_analysis")

    def test_openai_screenshot_analysis_starts_before_cloudinary_finishes(self) -> None:
        # Given
        ai_started = threading.Event()
        image_storage = BlockingImageStorage(ai_started)
        fake_openai = _fake_openai_module([], before_response=ai_started.set)
        service = FlirtistProductService(
            ai=_openai_ai(),
            image_storage=image_storage,
            repository=NoopRepository(),
        )
        request = _screenshot_request()

        # When
        with patch.dict(os.environ, {"FLIRTIST_OPENAI_API_KEY": "sk-test"}), patch.dict(
            sys.modules,
            {"openai": fake_openai},
        ):
            service.create_session(request)

        # Then
        self.assertTrue(
            image_storage.ai_started_while_uploading,
            "OpenAI should analyze its inline image while Cloudinary upload is still running",
        )


def _fake_openai_module(
    captured_timeouts: list[float],
    captured_image_urls: list[str] | None = None,
    *,
    captured_max_retries: list[int] | None = None,
    create_calls: list[int] | None = None,
    fail_first_connection: bool = False,
    fail_first_timeout: bool = False,
    before_response=None,
) -> types.ModuleType:
    fake_openai = types.ModuleType("openai")

    class FakeOpenAIError(Exception):
        pass

    class FakeAPIConnectionError(FakeOpenAIError):
        pass

    class FakeRateLimitError(FakeOpenAIError):
        pass

    class FakeInternalServerError(FakeOpenAIError):
        pass

    class FakeAPITimeoutError(FakeOpenAIError):
        pass

    class FakeResponse:
        output_text = "{}"

    class FakeResponses:
        def create(self, **kwargs) -> FakeResponse:
            if create_calls is not None:
                create_calls.append(len(create_calls) + 1)
                if fail_first_connection and len(create_calls) == 1:
                    raise FakeAPIConnectionError("connection reset")
                if fail_first_timeout and len(create_calls) == 1:
                    raise FakeAPITimeoutError("request timed out")
            if captured_image_urls is not None:
                for item in kwargs["input"][0]["content"]:
                    if item.get("type") == "input_image":
                        captured_image_urls.append(item["image_url"])
            if before_response is not None:
                before_response()
            return FakeResponse()

    class FakeOpenAI:
        def __init__(self, *, api_key: str, timeout: float, max_retries: int = 2) -> None:
            captured_timeouts.append(timeout)
            if captured_max_retries is not None:
                captured_max_retries.append(max_retries)
            self.responses = FakeResponses()

    fake_openai.OpenAI = FakeOpenAI
    fake_openai.OpenAIError = FakeOpenAIError
    fake_openai.APIConnectionError = FakeAPIConnectionError
    fake_openai.RateLimitError = FakeRateLimitError
    fake_openai.InternalServerError = FakeInternalServerError
    fake_openai.APITimeoutError = FakeAPITimeoutError
    return fake_openai


def _openai_ai() -> FlirtistProductAI:
    return FlirtistProductAI(
        config=FlirtistAIConfig(
            requested_provider="openai",
            effective_provider="openai",
            openai_model="gpt-test",
            anthropic_model="claude-test",
            gemini_model="gemini-test",
        )
    )


def _screenshot_request() -> FlirtistProductSessionRequest:
    return FlirtistProductSessionRequest(
        mode="score_analysis",
        source="screenshot",
        locale="ko-KR",
        imageBase64="aW1hZ2U=",
        imageMimeType="image/jpeg",
    )


class BlockingImageStorage:
    def __init__(self, ai_started: threading.Event) -> None:
        self._ai_started = ai_started
        self.ai_started_while_uploading = False

    def store_session_image(
        self,
        request: FlirtistProductSessionRequest,
        *,
        user_id: str | None = None,
        client_install_id: str | None = None,
    ) -> FlirtistStoredImage:
        del request, user_id, client_install_id
        self.ai_started_while_uploading = self._ai_started.wait(timeout=0.25)
        return FlirtistStoredImage(
            url="https://res.cloudinary.com/flirtcue/screenshot.jpg",
            storage_path="https://res.cloudinary.com/flirtcue/screenshot.jpg",
            mime_type="image/jpeg",
        )
