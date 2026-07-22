from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.config import Settings
from app.schemas.habitdot import HabitdotHabit, HabitdotMotivationRequest
from app.services.habitdot_motivation import HabitdotMotivationService


class HabitdotMotivationServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_generate_uses_openai_key_and_model_when_configured(self) -> None:
        # Given
        settings = Settings(
            _env_file=None,
            openai_api_key="openai-test-key",
            openai_model="gpt-5-mini",
            gemini_api_key="depleted-gemini-key",
        )
        request = _request()
        # When
        with patch("app.services.habitdot_motivation.AsyncOpenAI", _FakeAsyncOpenAI):
            response = await HabitdotMotivationService(settings).generate(request)

        # Then
        self.assertEqual(response.provider, "openai")
        self.assertEqual(response.model_name, "gpt-5-mini")
        self.assertEqual(response.text, "물 마시기부터, 오늘 한 잔 이어가요.")
        self.assertEqual(_FakeAsyncOpenAI.last_api_key, "openai-test-key")
        self.assertEqual(_FakeAsyncOpenAI.last_model, "gpt-5-mini")
        self.assertIn("물 마시기", _FakeAsyncOpenAI.last_input)
        self.assertEqual(_FakeAsyncOpenAI.last_reasoning, {"effort": "minimal"})

    async def test_generate_returns_fallback_without_openai_key(self) -> None:
        # Given
        settings = Settings(_env_file=None, openai_api_key=None, gemini_api_key="unused-gemini-key")

        # When
        response = await HabitdotMotivationService(settings).generate(_request())

        # Then
        self.assertEqual(response.provider, "fallback")
        self.assertIsNone(response.model_name)

    async def test_generate_returns_fallback_when_openai_fails(self) -> None:
        # Given
        settings = Settings(_env_file=None, openai_api_key="openai-test-key", openai_model="gpt-test")
        # When
        with (
            patch("app.services.habitdot_motivation.AsyncOpenAI", _FailingAsyncOpenAI),
            patch("app.services.habitdot_motivation.OpenAIError", _FakeOpenAIError),
        ):
            response = await HabitdotMotivationService(settings).generate(_request())

        # Then
        self.assertEqual(response.provider, "fallback")
        self.assertIsNone(response.model_name)


class _FakeOpenAIError(Exception):
    pass


class _FakeResponse:
    output_text = "물 마시기부터, 오늘 한 잔 이어가요."


class _FakeResponses:
    async def create(self, *, model: str, input: str, max_output_tokens: int, reasoning=None) -> _FakeResponse:
        _FakeAsyncOpenAI.last_model = model
        _FakeAsyncOpenAI.last_input = input
        _FakeAsyncOpenAI.last_reasoning = reasoning
        if max_output_tokens < 1:
            raise AssertionError("max_output_tokens must be positive")
        return _FakeResponse()


class _FakeAsyncOpenAI:
    last_api_key = ""
    last_model = ""
    last_input = ""
    last_reasoning = None

    def __init__(self, *, api_key: str) -> None:
        self.__class__.last_api_key = api_key
        self.responses = _FakeResponses()


class _FailingResponses:
    async def create(self, **kwargs) -> _FakeResponse:
        raise _FakeOpenAIError("quota exhausted")


class _FailingAsyncOpenAI:
    def __init__(self, *, api_key: str) -> None:
        self.responses = _FailingResponses()


def _request() -> HabitdotMotivationRequest:
    return HabitdotMotivationRequest(
        locale="ko",
        date="2026-07-22",
        habits=[HabitdotHabit(title="물 마시기", completed_today=False)],
    )


if __name__ == "__main__":
    unittest.main()
