from __future__ import annotations

import json
import builtins
import importlib
import sys
import types
import unittest
from typing import TypeAlias
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.analysis import AnalysisResultPayload
from app.services.ai.base import ProviderAnalysisRequest, ProviderPhotoInput

JsonValue: TypeAlias = str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]


class FacemaxxAIProviderTest(unittest.IsolatedAsyncioTestCase):
    def test_default_facemaxx_provider_is_openai(self) -> None:
        # Given
        env = {
            "AI_PROVIDER": "",
            "OPENAI_API_KEY": "",
            "GEMINI_API_KEY": "",
        }

        # When
        with patch.dict("os.environ", env, clear=False):
            settings = Settings(_env_file=None)

        # Then
        self.assertEqual(settings.ai_provider, "openai")

    def test_legacy_gemini_provider_setting_routes_facemaxx_to_openai(self) -> None:
        # Given
        from app.services.ai.factory import get_face_analysis_provider
        from app.services.ai.openai_provider import OpenAIFaceAnalysisProvider

        settings = Settings(
            _env_file=None,
            ai_provider="gemini",
            openai_api_key="test-openai-key",
            openai_model="gpt-test",
        )

        # When
        with patch("app.services.ai.factory.get_settings", return_value=settings):
            provider = get_face_analysis_provider()

        # Then
        self.assertIsInstance(provider, OpenAIFaceAnalysisProvider)
        self.assertEqual(provider.name, "openai")
        self.assertEqual(provider.model_name, "gpt-test")

    async def test_openai_provider_analyze_normalizes_response_without_gemini_dependency(self) -> None:
        # Given
        OpenAIFaceAnalysisProvider = _openai_provider_class_without_gemini_import()
        settings = Settings(_env_file=None, openai_api_key="test-openai-key", openai_model="gpt-test")
        provider = OpenAIFaceAnalysisProvider(settings)
        fake_module = types.SimpleNamespace(AsyncOpenAI=_FakeAsyncOpenAI)
        request = ProviderAnalysisRequest(
            user_id=None,
            mode_id="aesthetics",
            locale="en",
            photo_id=_FakeAsyncOpenAI.photo_id,
            photos=[
                ProviderPhotoInput(
                    photo_id=_FakeAsyncOpenAI.photo_id,
                    photo_bytes=b"image-bytes",
                    photo_mime_type="image/png",
                )
            ],
        )

        # When
        with patch.dict("sys.modules", {"openai": fake_module}):
            result = await provider.analyze(request)

        # Then
        self.assertIsInstance(result, AnalysisResultPayload)
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.model_name, "gpt-test")
        self.assertEqual(result.mode_id, "aesthetics")
        self.assertEqual(result.metrics[0].metric_id, "jawline")
        self.assertTrue(_FakeAsyncOpenAI.last_image_url.startswith("data:image/png;base64,"))
        self.assertEqual(_FakeAsyncOpenAI.last_text_format["format"]["type"], "json_schema")
        self.assertEqual(_FakeAsyncOpenAI.last_text_format["format"]["name"], "AnalysisResultPayload")

    def test_gemini_retry_error_classification_works_from_class(self) -> None:
        # Given
        from app.services.ai.gemini import GeminiFaceAnalysisProvider

        self.assertEqual(GeminiFaceAnalysisProvider._exception_status_code(_StatusError(429)), 429)
        self.assertTrue(GeminiFaceAnalysisProvider._is_transient_model_error(_StatusError(429)))
        self.assertTrue(GeminiFaceAnalysisProvider._is_transient_model_error(RuntimeError("timeout")))


class FacemaxxHealthTest(unittest.TestCase):
    def test_health_reports_facemaxx_openai_provider_and_model(self) -> None:
        # Given
        settings = Settings(
            _env_file=None,
            ai_provider="openai",
            openai_api_key="test-openai-key",
            openai_model="gpt-health",
        )
        client = TestClient(create_app())

        # When
        with (
            patch("app.api.routes.health.get_settings", return_value=settings),
            patch("app.services.flirtist_config.get_settings", return_value=settings),
        ):
            response = client.get("/health")

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ai_provider"], "openai")
        self.assertEqual(data["facemaxx_ai_provider"], "openai")
        self.assertEqual(data["facemaxx_openai_model"], "gpt-health")


class _FakeResponse:
    output_text = json.dumps(
        {
            "overall_score": 8.2,
            "overall_progress": 0.82,
            "summary_text": "OpenAI generated analysis.",
            "metrics": [
                {
                    "section": "detailed_metrics",
                    "metric_id": "jawline",
                    "value_text": "8.2",
                    "detail_text": "Clear jawline read from the submitted photo.",
                    "sort_order": 10,
                }
            ],
        }
    )


class _FakeResponses:
    async def create(self, *, model: str, input: list[dict[str, JsonValue]], text: dict[str, JsonValue]) -> _FakeResponse:
        _FakeAsyncOpenAI.last_model = model
        _FakeAsyncOpenAI.last_text_format = text
        user_message = input[0]
        content = user_message["content"]
        if not isinstance(content, list):
            raise AssertionError("OpenAI input content must be a list.")
        image_items = [item for item in content if isinstance(item, dict) and item.get("type") == "input_image"]
        if not image_items:
            raise AssertionError("OpenAI input must include the submitted image.")
        image_url = image_items[0].get("image_url")
        if not isinstance(image_url, str):
            raise AssertionError("OpenAI image input must include image_url.")
        _FakeAsyncOpenAI.last_image_url = image_url
        return _FakeResponse()


class _FakeAsyncOpenAI:
    from uuid import UUID

    photo_id = UUID("11111111-1111-1111-1111-111111111111")
    last_model: str | None = None
    last_image_url = ""
    last_text_format: dict[str, JsonValue] = {}

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.responses = _FakeResponses()


class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(status_code)
        self.status_code = status_code


def _openai_provider_class_without_gemini_import() -> type:
    original_import = builtins.__import__

    def guarded_import(name: str, *args, **kwargs) -> types.ModuleType:
        if name == "app.services.ai.gemini" or name.startswith("app.services.ai.gemini."):
            raise AssertionError("OpenAI provider imported Gemini provider at runtime.")
        return original_import(name, *args, **kwargs)

    sys.modules.pop("app.services.ai.openai_provider", None)
    sys.modules.pop("app.services.ai.gemini", None)
    with patch("builtins.__import__", side_effect=guarded_import):
        module = importlib.import_module("app.services.ai.openai_provider")
    return module.OpenAIFaceAnalysisProvider


if __name__ == "__main__":
    unittest.main()
