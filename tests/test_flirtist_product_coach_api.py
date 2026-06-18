from __future__ import annotations

import re
import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.flirtist_product import FlirtistCoachChatRequest
from app.schemas.flirtist_product import FlirtistCoachChatResponse
from app.services.flirtist_product_service import FlirtistProductService


class FlirtistProductCoachApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_coach_chat_replies_with_training_message_and_suggestions(self) -> None:
        # Given
        payload = {
            "locale": "en-US",
            "message": "How do I ask her out after a slow chat?",
            "history": [
                {"role": "assistant", "text": "Tell me what the last message was."},
                {"role": "user", "text": "She said work has been chaotic."},
            ],
        }

        # When
        response = self.client.post("/api/flirtist/coach-chat", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertRegex(data["sessionId"], re.compile(r"^coach_"))
        self.assertEqual(data["message"]["role"], "assistant")
        self.assertGreater(len(data["message"]["text"]), 20)
        self.assertGreaterEqual(len(data["suggestions"]), 2)

    def test_coach_fallback_is_specific_to_latest_message_and_context(self) -> None:
        # Given
        service = FlirtistProductService(ai=NoopAI())
        coffee_request = FlirtistCoachChatRequest(
            locale="ko-KR",
            message="커피숍에서 어떻게 말 걸까?",
            context="나는 연애 경험이 적고 부담 없는 대화를 선호해.",
        )
        date_request = FlirtistCoachChatRequest(
            locale="ko-KR",
            message="첫 데이트 후 뭐라고 보내?",
            context="나는 연애 경험이 적고 부담 없는 대화를 선호해.",
        )

        # When
        coffee_response = service.coach_chat(coffee_request)
        date_response = service.coach_chat(date_request)

        # Then
        self.assertNotEqual(coffee_response.message.text, date_response.message.text)
        self.assertIn("커피", coffee_response.message.text)
        self.assertIn("데이트", date_response.message.text)

    def test_coach_fallback_varies_for_general_korean_training_prompts(self) -> None:
        # Given
        service = FlirtistProductService(ai=NoopAI())
        requests = [
            FlirtistCoachChatRequest(locale="ko-KR", message="프로필 사진 칭찬 어떻게 해?"),
            FlirtistCoachChatRequest(locale="ko-KR", message="연락 빈도는 어떻게 맞춰?"),
            FlirtistCoachChatRequest(locale="ko-KR", message="고백 타이밍은 언제가 좋아?"),
            FlirtistCoachChatRequest(locale="ko-KR", message="부담 없이 플러팅 연습"),
        ]

        # When
        responses = [service.coach_chat(request) for request in requests]
        response_texts = {response.message.text for response in responses}
        response_suggestions = {tuple(response.suggestions) for response in responses}

        # Then
        self.assertEqual(len(response_texts), len(requests))
        self.assertEqual(len(response_suggestions), len(requests))
        self.assertIn("프로필/사진 칭찬", responses[0].message.text)
        self.assertIn("연락 빈도 조율", responses[1].message.text)
        self.assertIn("고백 타이밍", responses[2].message.text)
        self.assertIn("부담 낮은 플러팅", responses[3].message.text)


class NoopAI:
    def complete_coach_chat(
        self,
        *,
        request: FlirtistCoachChatRequest,
        fallback: FlirtistCoachChatResponse,
    ) -> FlirtistCoachChatResponse:
        return fallback


if __name__ == "__main__":
    unittest.main()
