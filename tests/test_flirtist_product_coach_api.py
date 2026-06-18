from __future__ import annotations

import re
import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.flirtist_product import FlirtistCoachChatRequest
from app.schemas.flirtist_product import FlirtistCoachMessage
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
        self.assertRegex(responses[0].message.text, "사진|분위기|칭찬")
        self.assertRegex(responses[1].message.text, "연락|속도|텀")
        self.assertRegex(responses[2].message.text, "고백|확인|타이밍")
        self.assertRegex(responses[3].message.text, "플러팅|장난|부담")

    def test_coach_fallback_gives_concrete_bar_approach_without_echoing_prompt(self) -> None:
        # Given
        service = FlirtistProductService(ai=NoopAI())
        request = FlirtistCoachChatRequest(locale="ko-KR", message="헌팅포차에서 어케 말걸지")

        # When
        response = service.coach_chat(request)

        # Then
        text = response.message.text
        self.assertRegex(text, "헌팅포차|포차|술집|옆자리|친구")
        self.assertRegex(text, "불편|괜찮|한마디|말")
        self.assertNotIn("'헌팅포차에서 어케 말걸지'", text)
        self.assertNotIn("한 번에 관계를 밀어붙이기보다", text)
        self.assertNotIn("작은 다음 행동", text)

    def test_coach_fallback_uses_previous_context_for_generic_followup(self) -> None:
        # Given
        service = FlirtistProductService(ai=NoopAI())
        request = FlirtistCoachChatRequest(
            locale="ko-KR",
            message="그니까 뭐라보낼까",
            history=[
                FlirtistCoachMessage(role="user", text="2년전 썸녀랑 술 먹고싶은데 뭐라 보내"),
                FlirtistCoachMessage(role="assistant", text="오랜만이면 바로 약속부터 밀지 마."),
            ],
        )

        # When
        response = service.coach_chat(request)

        # Then
        text = response.message.text
        self.assertRegex(text, "오랜만|술|한잔|근황")
        self.assertNotIn("'그니까 뭐라보낼까'", text)
        self.assertNotIn("한 번에 관계를 밀어붙이기보다", text)

    def test_low_value_provider_coach_response_is_repaired(self) -> None:
        # Given
        service = FlirtistProductService(ai=LowValueCoachAI())
        request = FlirtistCoachChatRequest(locale="ko-KR", message="2년전 썸녀랑 술 먹고싶은데 뭐라 보내")

        # When
        response = service.coach_chat(request)

        # Then
        text = response.message.text
        self.assertRegex(text, "오랜만|술|한잔|근황")
        self.assertNotIn("'2년전 썸녀랑 술 먹고싶은데 뭐라 보내'", text)
        self.assertNotIn("한 번에 관계를 밀어붙이기보다", text)
        self.assertNotIn("작은 다음 행동", text)


class NoopAI:
    def complete_coach_chat(
        self,
        *,
        request: FlirtistCoachChatRequest,
        fallback: FlirtistCoachChatResponse,
    ) -> FlirtistCoachChatResponse:
        return fallback


class LowValueCoachAI:
    def complete_coach_chat(
        self,
        *,
        request: FlirtistCoachChatRequest,
        fallback: FlirtistCoachChatResponse,
    ) -> FlirtistCoachChatResponse:
        return fallback.model_copy(
            update={
                "message": fallback.message.model_copy(
                    update={
                        "text": (
                            f"'{request.message}' 상황에서는 한 번에 관계를 밀어붙이기보다, "
                            "상대가 편하게 선택할 수 있는 작은 다음 행동이 좋아요. "
                            "마지막에는 질문 하나만 남기고, 답이 늦어도 추가 확인 메시지는 보내지 마세요."
                        )
                    }
                )
            }
        )


if __name__ == "__main__":
    unittest.main()
