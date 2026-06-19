from __future__ import annotations

import json
import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.services.flirtist_config import FlirtistAIConfig, FlirtistProvider
from app.services.flirtist_product_ai import FlirtistProductAI
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopImageStorage, NoopRepository


class FlirtistProductAIProviderTest(unittest.TestCase):
    def test_product_session_uses_gemini_transport_instead_of_silent_fallback(self) -> None:
        # Given
        transport = FixedTransport(
            json.dumps(
                {
                    "replyCoaching": {
                        "summary": "광주에 오면 맛있는 걸 사주겠다는 약속을 이어가는 흐름",
                        "nextMove": "상대가 오고 싶게 느껴지는 한 문장으로 이어간다.",
                        "replies": [
                            {
                                "id": "reply_live_gemini",
                                "style": "genuine",
                                "text": "광주 오면 맛난 거 사준다는 약속 아직 유효해. 언제 올지 살짝 기대해도 돼?",
                                "whyItWorks": "대화에 나온 광주와 맛난 약속을 그대로 살려 다음 답을 쉽게 만든다.",
                                "aiObviousness": 8,
                                "pressure": 16,
                                "replyLikelihood": 90,
                            }
                        ],
                    }
                },
                ensure_ascii=False,
            )
        )
        ai = FlirtistProductAI(
            config=FlirtistAIConfig(
                requested_provider="gemini",
                effective_provider="gemini",
                openai_model="gpt-test",
                anthropic_model="claude-test",
                gemini_model="gemini-test",
            ),
            provider_transport=transport,
        )
        service = FlirtistProductService(
            ai=ai,
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            text=(
                "Them: 오늘는 광주에 사는거야?\n"
                "Me: 웅 나는 광주 살앙\n"
                "Them: 오옹 글쿠나\n"
                "Me: 나중에 광주 올 일 생기면 미리 연락해 맛난거 사줄겤ㅋㅋ\n"
                "Them: 웅 조아네"
            ),
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertEqual(transport.providers, ["gemini"])
        assert response.replyCoaching is not None
        self.assertEqual(
            response.replyCoaching.replies[0].text,
            "광주 오면 맛난 거 사준다는 약속 아직 유효해. 언제 올지 살짝 기대해도 돼?",
        )


class FixedTransport:
    def __init__(self, text: str) -> None:
        self._text = text
        self.providers: list[FlirtistProvider] = []

    def complete_text(self, *, provider: FlirtistProvider, prompt: str, config: FlirtistAIConfig) -> str:
        self.providers.append(provider)
        if "오늘는 광주에 사는거야" not in prompt:
            raise AssertionError("Product prompt did not include the OCR transcript.")
        return self._text


if __name__ == "__main__":
    unittest.main()
