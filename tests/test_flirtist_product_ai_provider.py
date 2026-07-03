from __future__ import annotations

import json
import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest, FlirtistReplyStyleRequest
from app.services.flirtist_config import FlirtistAIConfig, FlirtistProvider
from app.services.flirtist_provider import FlirtistProviderError
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
        self.assertIn("exactly four copy-ready replies", transport.prompts[0])
        self.assertNotIn("one short reply per style", transport.prompts[0])
        assert response.replyCoaching is not None
        self.assertEqual(
            response.replyCoaching.replies[0].text,
            "광주 오면 맛난 거 사준다는 약속 아직 유효해. 언제 올지 살짝 기대해도 돼?",
        )
        self.assertEqual(len(response.replyCoaching.replyPacks[0].replies), 4)

    def test_score_analysis_provider_failure_does_not_return_contextless_fallback(self) -> None:
        # Given
        ai = FlirtistProductAI(
            config=FlirtistAIConfig(
                requested_provider="gemini",
                effective_provider="gemini",
                openai_model="gpt-test",
                anthropic_model="claude-test",
                gemini_model="gemini-test",
            ),
            provider_transport=FailingTransport(),
        )
        service = FlirtistProductService(
            ai=ai,
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="score_analysis",
            source="screenshot",
            locale="ko-KR",
            text="Them: 오늘 회사가 정신이 하나도 없었어\nMe: 그래도 퇴근할 수 있지?",
        )

        # When / Then
        with self.assertRaisesRegex(Exception, "분석에 실패했습니다"):
            service.create_session(request)

    def test_screenshot_reply_provider_failure_does_not_return_contextless_fallback(self) -> None:
        # Given
        ai = FlirtistProductAI(
            config=FlirtistAIConfig(
                requested_provider="gemini",
                effective_provider="gemini",
                openai_model="gpt-test",
                anthropic_model="claude-test",
                gemini_model="gemini-test",
            ),
            provider_transport=FailingTransport(),
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
            text="Them: 오늘 회사가 정신이 하나도 없었어\nMe: 그래도 퇴근할 수 있지?",
        )

        # When / Then
        with self.assertRaisesRegex(Exception, "분석에 실패했습니다"):
            service.create_session(request)

    def test_reply_style_prompt_excludes_existing_replies(self) -> None:
        # Given
        transport = FixedStyleTransport()
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
        request = FlirtistReplyStyleRequest(
            locale="ko-KR",
            language="ko",
            sessionId="flt_existing",
            context="Them: 웅 조아네\nMe: 광주 오면 맛난 거 사줄게",
            baseReply="광주 오면 진짜 맛있는 거 먹이러 갈게",
            style="genuine",
            existingReplies=["광주 오면 진짜 맛있는 거 먹이러 갈게"],
        )

        # When
        response = service.regenerate_reply(request)

        # Then
        self.assertIn("existingReplies", transport.prompts[0])
        texts = [reply.text for reply in response.replyCoaching.replies]
        self.assertNotIn("광주 오면 진짜 맛있는 거 먹이러 갈게", texts)
        self.assertEqual(len(texts), 4)
        self.assertEqual(len(set(texts)), 4)

    def test_reply_style_provider_failure_raises_instead_of_returning_fallback(self) -> None:
        # Given
        ai = FlirtistProductAI(
            config=FlirtistAIConfig(
                requested_provider="gemini",
                effective_provider="gemini",
                openai_model="gpt-test",
                anthropic_model="claude-test",
                gemini_model="gemini-test",
            ),
            provider_transport=FailingTransport(),
        )
        service = FlirtistProductService(
            ai=ai,
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistReplyStyleRequest(
            locale="ko-KR",
            language="ko",
            sessionId="flt_fail",
            context="Them: 웅 조아네\nMe: 광주 오면 맛난 거 사줄게",
            baseReply="광주 오면 진짜 맛있는 거 먹이러 갈게",
            style="genuine",
        )

        # When / Then
        with self.assertRaisesRegex(Exception, "생성에 실패했습니다"):
            service.regenerate_reply(request)


class FixedTransport:
    def __init__(self, text: str) -> None:
        self._text = text
        self.providers: list[FlirtistProvider] = []
        self.prompts: list[str] = []

    def complete_text(self, *, provider: FlirtistProvider, prompt: str, config: FlirtistAIConfig) -> str:
        self.providers.append(provider)
        self.prompts.append(prompt)
        if "오늘는 광주에 사는거야" not in prompt:
            raise AssertionError("Product prompt did not include the OCR transcript.")
        return self._text


class FailingTransport:
    def complete_text(self, *, provider: FlirtistProvider, prompt: str, config: FlirtistAIConfig) -> str:
        raise FlirtistProviderError(provider=provider, reason="upstream timed out")


class FixedStyleTransport:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete_text(self, *, provider: FlirtistProvider, prompt: str, config: FlirtistAIConfig) -> str:
        self.prompts.append(prompt)
        return json.dumps(
            {
                "replyCoaching": {
                    "headline": "AI 추천 답장",
                    "summary": "광주 약속을 이어가는 흐름",
                    "nextMove": "상대가 답하기 쉽게 약속을 구체화한다.",
                    "replies": [
                        {
                            "id": "dup",
                            "style": "genuine",
                            "text": "광주 오면 진짜 맛있는 거 먹이러 갈게",
                            "whyItWorks": "기존 답장과 중복된다.",
                            "aiObviousness": 12,
                            "pressure": 18,
                            "replyLikelihood": 84,
                        },
                        {
                            "id": "new1",
                            "style": "genuine",
                            "text": "좋아ㅋㅋ 광주 오면 맛집 후보부터 골라둘게",
                            "whyItWorks": "약속을 구체화한다.",
                            "aiObviousness": 9,
                            "pressure": 16,
                            "replyLikelihood": 88,
                        },
                        {
                            "id": "new2",
                            "style": "genuine",
                            "text": "연락만 미리 줘ㅋㅋ 맛있는 데로 데려갈게",
                            "whyItWorks": "다음 행동이 쉽다.",
                            "aiObviousness": 10,
                            "pressure": 15,
                            "replyLikelihood": 87,
                        },
                        {
                            "id": "new3",
                            "style": "genuine",
                            "text": "그럼 광주 오는 날 내가 밥 담당하는 걸로",
                            "whyItWorks": "역할을 가볍게 정한다.",
                            "aiObviousness": 11,
                            "pressure": 17,
                            "replyLikelihood": 86,
                        },
                        {
                            "id": "new4",
                            "style": "genuine",
                            "text": "좋다ㅋㅋ 오기 전에 먹고 싶은 거 하나만 생각해놔",
                            "whyItWorks": "구체적인 선택지를 준다.",
                            "aiObviousness": 8,
                            "pressure": 14,
                            "replyLikelihood": 89,
                        },
                    ],
                    "replyPacks": [],
                }
            },
            ensure_ascii=False,
        )


if __name__ == "__main__":
    unittest.main()
