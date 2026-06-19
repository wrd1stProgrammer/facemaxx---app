from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class FlirtistConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_provider_env_config_falls_back_to_mock_when_openai_key_is_absent(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "openai",
            "FLIRTIST_OPENAI_MODEL": "gpt-test",
            "FLIRTIST_OPENAI_API_KEY": "",
            "OPENAI_API_KEY": "",
        }
        settings = Settings(openai_api_key=None, openai_model="gpt-default")

        # When
        with (
            patch.dict("os.environ", env, clear=False),
            patch("app.services.flirtist_config.get_settings", return_value=settings),
        ):
            from app.services.flirtist_config import load_flirtist_ai_config

            config = load_flirtist_ai_config()

        # Then
        self.assertEqual(config.requested_provider, "openai")
        self.assertEqual(config.effective_provider, "mock")
        self.assertEqual(config.openai_model, "gpt-test")

    def test_provider_env_config_defaults_to_openai_when_flirtist_openai_key_is_present(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "",
            "FLIRTIST_OPENAI_API_KEY": "flirtist-test-key",
            "FLIRTIST_OPENAI_MODEL": "gpt-flirtist",
            "OPENAI_API_KEY": "",
            "FLIRTIST_GEMINI_API_KEY": "",
            "GEMINI_API_KEY": "",
        }
        settings = Settings(openai_api_key=None, openai_model="gpt-default")

        # When
        with (
            patch.dict("os.environ", env, clear=False),
            patch("app.services.flirtist_config.get_settings", return_value=settings),
        ):
            from app.services.flirtist_config import load_flirtist_ai_config

            config = load_flirtist_ai_config()

        # Then
        self.assertEqual(config.requested_provider, "openai")
        self.assertEqual(config.effective_provider, "openai")
        self.assertEqual(config.openai_model, "gpt-flirtist")

    def test_provider_env_config_defaults_to_settings_gemini_when_gemini_key_is_present(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "",
            "FLIRTIST_OPENAI_API_KEY": "",
            "OPENAI_API_KEY": "",
            "FLIRTIST_GEMINI_API_KEY": "",
            "GEMINI_API_KEY": "",
        }
        settings = Settings(
            ai_provider="gemini",
            gemini_api_key="settings-gemini-key",
            gemini_model="gemini-test-model",
            openai_api_key=None,
        )

        # When
        with (
            patch.dict("os.environ", env, clear=False),
            patch("app.services.flirtist_config.get_settings", return_value=settings),
        ):
            from app.services.flirtist_config import load_flirtist_ai_config

            config = load_flirtist_ai_config()

        # Then
        self.assertEqual(config.requested_provider, "gemini")
        self.assertEqual(config.effective_provider, "gemini")
        self.assertEqual(config.gemini_model, "gemini-test-model")

    def test_health_reports_flirtist_openai_separately_from_global_provider(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "openai",
            "FLIRTIST_OPENAI_API_KEY": "flirtist-test-key",
            "FLIRTIST_OPENAI_MODEL": "gpt-flirtist",
            "OPENAI_API_KEY": "",
        }
        settings = Settings(ai_provider="gemini", openai_api_key=None, openai_model="gpt-default")

        # When
        with (
            patch.dict("os.environ", env, clear=False),
            patch("app.api.routes.health.get_settings", return_value=settings),
            patch("app.services.flirtist_config.get_settings", return_value=settings),
        ):
            response = self.client.get("/health")

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ai_provider"], "gemini")
        self.assertEqual(data["flirtist_ai_requested_provider"], "openai")
        self.assertEqual(data["flirtist_ai_provider"], "openai")
        self.assertEqual(data["flirtist_openai_model"], "gpt-flirtist")


if __name__ == "__main__":
    unittest.main()
