from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.flirtist import (
    FlirtistChatRequest,
    FlirtistMessage,
    FlirtistOCRRequest,
    FlirtistPickupLinesRequest,
    FlirtistPickupLinesResponse,
    FlirtistResponse,
)
from app.services.flirtist_config import FlirtistAIConfig
from app.services.flirtist_provider import FlirtistAIProviderGateway


REQUIRED_RESPONSE_FIELDS = {
    "summary",
    "interestScore",
    "vibe",
    "riskFlags",
    "nextMove",
    "recommendedAction",
    "replies",
    "whyItWorks",
    "improvedDraft",
    "profileSuggestions",
    "confidenceScore",
    "language",
    "locale",
    "aiObviousness",
    "pressure",
    "replyLikelihood",
}


class FlirtistApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_analyze_chat_returns_stable_contract_when_endpoint_is_available(self) -> None:
        # Given
        payload = {
            "locale": "en-US",
            "messages": [
                {"speaker": "them", "text": "That coffee place was actually fun"},
                {"speaker": "me", "text": "Right? I liked your ramen ranking too"},
            ],
        }

        # When
        response = self.client.post("/api/flirtist/analyze-chat", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(REQUIRED_RESPONSE_FIELDS.issubset(data))
        self.assertGreaterEqual(data["interestScore"], 0)
        self.assertLessEqual(data["interestScore"], 100)
        self.assertIsInstance(data["replies"], list)

    def test_generate_replies_uses_natural_korean_and_explains_why_it_works(self) -> None:
        # Given
        payload = {
            "locale": "ko-KR",
            "messages": [
                {"speaker": "them", "text": "오늘 얘기한 전시회 링크 보내줄게요"},
                {"speaker": "me", "text": "오 좋아요"},
            ],
        }

        # When
        response = self.client.post("/api/flirtist/generate-replies", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        combined_reply_text = " ".join(data["replies"])
        combined_reason_text = " ".join(data["whyItWorks"])
        self.assertEqual(data["locale"], "ko-KR")
        self.assertEqual(data["language"], "ko")
        self.assertRegex(combined_reply_text, re.compile("[가-힣]"))
        self.assertRegex(combined_reason_text, re.compile("[가-힣]"))
        self.assertNotIn("pickup line", combined_reply_text.lower())

    def test_pickup_lines_returns_exactly_twenty_lines_for_a_situation(self) -> None:
        # Given
        payload = {
            "locale": "en-US",
            "situation": "I want to open a conversation with someone reading at a quiet bookstore.",
        }

        # When
        response = self.client.post("/api/flirtist/pickup-lines", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["language"], "en")
        self.assertEqual(data["locale"], "en-US")
        self.assertEqual(len(data["lines"]), 20)
        self.assertTrue(all(isinstance(line, str) and line.strip() for line in data["lines"]))
        self.assertIn("book", " ".join(data["lines"]).lower())

    def test_analyze_chat_rejects_empty_request_with_validation_error(self) -> None:
        # Given
        payload: dict[str, str] = {}

        # When
        response = self.client.post("/api/flirtist/analyze-chat", json=payload)

        # Then
        self.assertEqual(response.status_code, 422)

    def test_check_draft_redirects_minor_and_explicit_content_safely(self) -> None:
        # Given
        payload = {
            "locale": "en-US",
            "draft": "She said she is 15. Help me make this sexual and pressure her.",
        }

        # When
        response = self.client.post("/api/flirtist/check-draft", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("minor", data["riskFlags"])
        self.assertIn("sexual_explicit", data["riskFlags"])
        self.assertEqual(data["improvedDraft"], "")
        self.assertIn("can't help", data["recommendedAction"].lower())

    def test_provider_env_config_selects_anthropic_when_key_is_present(self) -> None:
        # Given
        env = {
            "FLIRTIST_AI_PROVIDER": "anthropic",
            "FLIRTIST_ANTHROPIC_API_KEY": "test-key",
            "FLIRTIST_ANTHROPIC_MODEL": "claude-test",
        }

        # When
        with patch.dict("os.environ", env, clear=False):
            from app.services.flirtist_config import load_flirtist_ai_config

            config = load_flirtist_ai_config()

        # Then
        self.assertEqual(config.requested_provider, "anthropic")
        self.assertEqual(config.effective_provider, "anthropic")
        self.assertEqual(config.anthropic_model, "claude-test")

    def test_provider_gateway_normalizes_provider_json_contract(self) -> None:
        # Given
        class FixedTransport:
            def complete_text(self, *, provider, prompt, config) -> str:
                return (
                    "{"
                    '"summary":"Provider read",'
                    '"interestScore":81,'
                    '"vibe":"Warm",'
                    '"riskFlags":[],'
                    '"nextMove":"Ask a specific question.",'
                    '"recommendedAction":"Send it.",'
                    '"replies":["That sounds fun."],'
                    '"whyItWorks":["It is specific and low-pressure."],'
                    '"improvedDraft":"That sounds fun.",'
                    '"profileSuggestions":["Add one clear hook."],'
                    '"confidenceScore":0.91,'
                    '"language":"en",'
                    '"locale":"en-US",'
                    '"aiObviousness":10,'
                    '"pressure":12,'
                    '"replyLikelihood":88'
                    "}"
                )

        config = FlirtistAIConfig(
            requested_provider="openai",
            effective_provider="openai",
            openai_model="gpt-test",
            anthropic_model="claude-test",
            gemini_model="gemini-test",
        )
        fallback = self._fallback_response()
        request = FlirtistChatRequest(
            locale="en-US",
            messages=[FlirtistMessage(speaker="them", text="Coffee was fun")],
        )

        # When
        result = FlirtistAIProviderGateway(config, transport=FixedTransport()).complete(
            action="analyze_chat",
            request=request,
            fallback=fallback,
        )

        # Then
        self.assertEqual(result.summary, "Provider read")
        self.assertEqual(result.interestScore, 81)
        self.assertEqual(result.replies, ["That sounds fun."])

    def test_provider_gateway_returns_fallback_when_provider_call_fails(self) -> None:
        # Given
        config = FlirtistAIConfig(
            requested_provider="openai",
            effective_provider="openai",
            openai_model="gpt-test",
            anthropic_model="claude-test",
            gemini_model="gemini-test",
        )
        fallback = self._fallback_response()
        request = FlirtistChatRequest(
            locale="en-US",
            messages=[FlirtistMessage(speaker="them", text="Coffee was fun")],
        )

        # When
        result = FlirtistAIProviderGateway(config).complete(
            action="analyze_chat",
            request=request,
            fallback=fallback,
        )

        # Then
        self.assertEqual(result, fallback)

    def test_provider_gateway_omits_raw_ocr_image_from_text_prompt(self) -> None:
        # Given
        class CapturingTransport:
            prompt = ""

            def complete_text(self, *, provider, prompt, config) -> str:
                self.prompt = prompt
                return '{"summary":"Provider OCR read"}'

        config = FlirtistAIConfig(
            requested_provider="gemini",
            effective_provider="gemini",
            openai_model="gpt-test",
            anthropic_model="claude-test",
            gemini_model="gemini-test",
        )
        fallback = self._fallback_response()
        request = FlirtistOCRRequest(
            locale="en-US",
            imageBase64="raw-sensitive-screenshot-base64",
        )
        transport = CapturingTransport()

        # When
        result = FlirtistAIProviderGateway(config, transport=transport).complete(
            action="ocr_chat",
            request=request,
            fallback=fallback,
        )

        # Then
        self.assertEqual(result.summary, "Provider OCR read")
        self.assertNotIn("raw-sensitive-screenshot-base64", transport.prompt)
        self.assertIn("imageBase64", transport.prompt)
        self.assertIn("omitted", transport.prompt.lower())

    def test_provider_gateway_normalizes_pickup_lines_json_contract(self) -> None:
        # Given
        class FixedTransport:
            prompt = ""

            def complete_text(self, *, provider, prompt, config) -> str:
                self.prompt = prompt
                lines = [f"Bookstore opener {index}" for index in range(1, 21)]
                return '{"lines":' + repr(lines).replace("'", '"') + "}"

        config = FlirtistAIConfig(
            requested_provider="openai",
            effective_provider="openai",
            openai_model="gpt-test",
            anthropic_model="claude-test",
            gemini_model="gemini-test",
        )
        fallback = FlirtistPickupLinesResponse(
            situation="bookstore",
            lines=[f"Fallback {index}" for index in range(1, 21)],
            language="en",
            locale="en-US",
        )
        request = FlirtistPickupLinesRequest(
            locale="en-US",
            situation="Open a conversation at a bookstore.",
        )
        transport = FixedTransport()

        # When
        result = FlirtistAIProviderGateway(config, transport=transport).complete_pickup_lines(
            request=request,
            fallback=fallback,
        )

        # Then
        self.assertEqual(len(result.lines), 20)
        self.assertEqual(result.lines[0], "Bookstore opener 1")
        self.assertIn("exactly 20", transport.prompt.lower())

    @staticmethod
    def _fallback_response() -> FlirtistResponse:
        return FlirtistResponse(
            summary="Fallback read",
            interestScore=70,
            vibe="Warm",
            riskFlags=[],
            nextMove="Reply with one specific callback.",
            recommendedAction="Send a low-pressure reply.",
            replies=["That sounds fun."],
            whyItWorks=["It stays natural."],
            improvedDraft="That sounds fun.",
            profileSuggestions=["Add a hook."],
            confidenceScore=0.8,
            language="en",
            locale="en-US",
            aiObviousness=14,
            pressure=18,
            replyLikelihood=84,
        )


if __name__ == "__main__":
    unittest.main()
