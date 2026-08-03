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

    def test_provider_env_config_defaults_to_openai_when_global_openai_key_is_present(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "",
            "FLIRTIST_OPENAI_API_KEY": "",
            "OPENAI_API_KEY": "global-openai-key",
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
        self.assertEqual(config.requested_provider, "openai")
        self.assertEqual(config.effective_provider, "openai")

    def test_flirtist_openai_model_defaults_to_fast_product_model(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "",
            "FLIRTIST_OPENAI_MODEL": "",
            "FLIRTIST_OPENAI_API_KEY": "",
            "OPENAI_API_KEY": "global-openai-key",
            "FLIRTIST_GEMINI_API_KEY": "",
            "GEMINI_API_KEY": "",
        }
        settings = Settings(openai_api_key=None, openai_model="gpt-5-mini")

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
        self.assertEqual(config.openai_model, "gpt-4.1-mini")

    def test_provider_env_config_can_still_force_gemini(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "gemini",
            "FLIRTIST_OPENAI_API_KEY": "",
            "OPENAI_API_KEY": "global-openai-key",
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

    def test_codex_cli_uses_luna_light_defaults_and_api_fallback(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "codex",
            "FLIRTIST_AI_FALLBACK_PROVIDER": "openai",
            "FLIRTIST_CODEX_MODEL": "gpt-5.6-luna",
            "FLIRTIST_CODEX_REASONING_EFFORT": "light",
            "FLIRTIST_CODEX_TIMEOUT_SECONDS": "61",
            "FLIRTIST_CODEX_MAX_CONCURRENCY": "3",
            "CODEX_HOME": "/tmp/flirtist-codex-home",
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
        self.assertEqual(config.requested_provider, "codex_cli")
        self.assertEqual(config.effective_provider, "codex_cli")
        self.assertEqual(config.fallback_provider, "openai")
        self.assertEqual(config.codex_model, "gpt-5.6-luna")
        self.assertEqual(config.codex_reasoning_effort, "low")
        self.assertEqual(config.codex_timeout_seconds, 61.0)
        self.assertEqual(config.codex_max_concurrency, 3)
        self.assertEqual(config.codex_home, "/tmp/flirtist-codex-home")

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
