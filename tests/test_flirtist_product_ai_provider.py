from __future__ import annotations

import json
import unittest
from typing import TypeAlias

from app.schemas.flirtist_product import FlirtistProductSessionRequest, FlirtistReplyStyleRequest
from app.services.flirtist_config import FlirtistAIConfig, FlirtistProvider
from app.services.flirtist_provider import FlirtistProviderError
from app.services.flirtist_product_ai import FlirtistProductAI, FlirtistProductAIError
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopImageStorage, NoopRepository

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


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
                        "replyPacks": _complete_reply_packs_payload(),
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
            imageBase64="aW1hZ2U=",
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
        self.assertIn("server derives top-level replies", transport.prompts[0])
        self.assertNotIn("one short reply per style", transport.prompts[0])
        assert response.replyCoaching is not None
        self.assertEqual(
            {pack.style for pack in response.replyCoaching.replyPacks},
            {"genuine", "witty", "flirty", "romantic", "nsfw"},
        )
        self.assertTrue(all(len(pack.replies) == 4 for pack in response.replyCoaching.replyPacks))
        self.assertEqual(
            response.replyCoaching.replies[0].text,
            "광주 오면 맛난 거 사준다는 약속 아직 유효해. 언제 올지 살짝 기대해도 돼?",
        )

    def test_screenshot_reply_provider_incomplete_reply_packs_raise_instead_of_contextless_fallback(self) -> None:
        # Given
        transport = FixedTransport(
            json.dumps(
                {
                    "replyCoaching": {
                        "summary": "광주에 오면 맛있는 걸 사주겠다는 약속을 이어가는 흐름",
                        "nextMove": "상대가 오고 싶게 느껴지는 한 문장으로 이어간다.",
                        "replies": [
                            {
                                "id": f"reply_live_gemini_{index}",
                                "style": "genuine",
                                "text": text,
                                "whyItWorks": "대화에 나온 광주와 맛난 약속을 그대로 살려 다음 답을 쉽게 만든다.",
                                "aiObviousness": 8,
                                "pressure": 16,
                                "replyLikelihood": 90,
                            }
                            for index, text in enumerate(
                                [
                                    "광주 오면 맛난 거 사준다는 약속 아직 유효해. 언제 올지 살짝 기대해도 돼?",
                                    "그럼 광주 올 일 생기면 나한테 먼저 연락하기. 맛난 거 리스트 비워둘게.",
                                    "광주 얘기 나온 김에, 너 오면 내가 맛난 곳 하나는 제대로 데려갈게.",
                                    "오케이, 광주 오면 내가 진짜 맛난 걸로 갚아볼게. 기대해도 돼?",
                                ],
                                start=1,
                            )
                        ],
                        "replyPacks": [
                            {"style": "genuine", "label": "Genuine", "buttonTitle": "Genuine", "iconName": "heart"},
                            {"style": "witty", "label": "Witty", "buttonTitle": "Witty", "iconName": "smile"},
                            {"style": "flirty", "label": "Flirty", "buttonTitle": "Flirty", "iconName": "fire"},
                            {"style": "romantic", "label": "Romantic", "buttonTitle": "Romantic", "iconName": "rose"},
                            {"style": "nsfw", "label": "Spicy", "buttonTitle": "Spicy", "iconName": "flame"},
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
            imageBase64="aW1hZ2U=",
            text=(
                "Them: 오늘는 광주에 사는거야?\n"
                "Me: 웅 나는 광주 살앙\n"
                "Them: 오옹 글쿠나\n"
                "Me: 나중에 광주 올 일 생기면 미리 연락해 맛난거 사줄겤ㅋㅋ\n"
                "Them: 웅 조아네"
            ),
        )

        # When / Then
        with self.assertRaisesRegex(FlirtistProductAIError, "분석에 실패했습니다"):
            service.create_session(request)

    def test_profile_bio_screenshot_returns_bio_content_kind_and_openers(self) -> None:
        # Given
        transport = FixedTransport(
            json.dumps(
                {
                    "contentKind": "bio",
                    "chatPreview": [
                        {
                            "role": "them",
                            "text": "Profile bio: Weekend climber, bad at choosing ramen spots, ask me about Jeju.",
                        }
                    ],
                    "replyCoaching": {
                        "headline": "First messages",
                        "summary": "Open from a real bio detail instead of pretending there is a chat.",
                        "nextMove": "Send one profile-specific opener with an easy question.",
                        "replies": [
                            {
                                "id": "bio_genuine_1",
                                "style": "genuine",
                                "text": "Your Jeju line got me curious. What memory should I ask about first?",
                                "whyItWorks": "It uses a real profile hook.",
                                "aiObviousness": 8,
                                "pressure": 14,
                                "replyLikelihood": 89,
                            },
                            {
                                "id": "bio_genuine_2",
                                "style": "genuine",
                                "text": "Weekend climber and ramen scout is a strong combo. Which one came first?",
                                "whyItWorks": "It combines two bio details.",
                                "aiObviousness": 9,
                                "pressure": 16,
                                "replyLikelihood": 87,
                            },
                            {
                                "id": "bio_genuine_3",
                                "style": "genuine",
                                "text": "I need the Jeju story before I trust your ramen rankings.",
                                "whyItWorks": "It gives an easy reply path.",
                                "aiObviousness": 10,
                                "pressure": 17,
                                "replyLikelihood": 86,
                            },
                            {
                                "id": "bio_genuine_4",
                                "style": "genuine",
                                "text": "Bad at choosing ramen spots sounds fixable. What makes a place worth it?",
                                "whyItWorks": "It asks from the bio.",
                                "aiObviousness": 11,
                                "pressure": 15,
                                "replyLikelihood": 88,
                            },
                        ],
                        "replyPacks": _complete_bio_opener_packs_payload(),
                    },
                },
                ensure_ascii=False,
            ),
            required_prompt_fragment="Profile bio:",
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
            locale="en-US",
            imageBase64="aW1hZ2U=",
            text="Profile bio: Weekend climber, bad at choosing ramen spots, ask me about Jeju.",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertEqual(response.contentKind, "bio")
        self.assertIn("first-message openers", transport.prompts[0])
        self.assertNotIn("answer the latest meaningful Them message", response.replyCoaching.summary)
        assert response.replyCoaching is not None
        self.assertEqual(response.replyCoaching.replies[0].text, "Your Jeju line got me curious. What memory should I ask about first?")
        self.assertTrue(all(len(pack.replies) == 4 for pack in response.replyCoaching.replyPacks))

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
    def __init__(self, text: str, required_prompt_fragment: str = "오늘는 광주에 사는거야") -> None:
        self._text = text
        self._required_prompt_fragment = required_prompt_fragment
        self.providers: list[FlirtistProvider] = []
        self.prompts: list[str] = []

    def complete_text(self, *, provider: FlirtistProvider, prompt: str, config: FlirtistAIConfig) -> str:
        self.providers.append(provider)
        self.prompts.append(prompt)
        if self._required_prompt_fragment not in prompt:
            raise AssertionError("Product prompt did not include the submitted transcript text.")
        return self._text


def _complete_reply_packs_payload() -> list[JsonValue]:
    pack_specs = (
        ("genuine", "Natural", "Natural replies", "bolt.fill"),
        ("witty", "Witty", "Witty replies", "sparkles"),
        ("flirty", "Flirty", "Flirty replies", "heart.fill"),
        ("romantic", "Warm", "Warm replies", "heart.circle.fill"),
        ("nsfw", "Bold", "Bolder replies", "flame.fill"),
    )
    return [
        {
            "style": style,
            "label": label,
            "buttonTitle": button_title,
            "iconName": icon_name,
            "replies": [
                {
                    "id": f"{style}_{index}",
                    "style": style,
                    "text": f"광주 맛난 약속을 {style} 톤으로 이어가기 {index}",
                    "whyItWorks": "광주와 맛난 약속을 살린다.",
                    "aiObviousness": 8 + index,
                    "pressure": 14 + index,
                    "replyLikelihood": 84 + index,
                }
                for index in range(1, 5)
            ],
        }
        for style, label, button_title, icon_name in pack_specs
    ]


def _complete_bio_opener_packs_payload() -> list[JsonValue]:
    pack_specs = (
        ("genuine", "Natural", "Natural openers", "bolt.fill"),
        ("witty", "Witty", "Witty openers", "sparkles"),
        ("flirty", "Flirty", "Flirty openers", "heart.fill"),
        ("romantic", "Warm", "Warm openers", "heart.circle.fill"),
        ("nsfw", "Bold", "Bolder openers", "flame.fill"),
    )
    return [
        {
            "style": style,
            "label": label,
            "buttonTitle": button_title,
            "iconName": icon_name,
            "replies": [
                {
                    "id": f"bio_{style}_{index}",
                    "style": style,
                    "text": f"Bio-specific {style} opener about Jeju and ramen {index}",
                    "whyItWorks": f"It uses a profile detail {index}.",
                    "aiObviousness": 8 + index,
                    "pressure": 14 + index,
                    "replyLikelihood": 84 + index,
                }
                for index in range(1, 5)
            ],
        }
        for style, label, button_title, icon_name in pack_specs
    ]


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
