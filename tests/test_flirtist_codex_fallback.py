from __future__ import annotations

import json
import unittest

from app.schemas.flirtist import FlirtistChatRequest, FlirtistResponse
from app.schemas.flirtist_product import FlirtistCoachChatRequest, FlirtistReplyStyleRequest
from app.services.flirtist_codex_cli import FlirtistCodexCLIError
from app.services.flirtist_config import FlirtistAIConfig, FlirtistProvider
from app.services.flirtist_product_ai import FlirtistProductAI
from app.services.flirtist_provider import FlirtistAIProviderGateway, FlirtistProviderError


class FlirtistCodexFallbackTest(unittest.TestCase):
    def test_legacy_gateway_uses_api_provider_after_codex_failure(self) -> None:
        fallback = _legacy_fallback()
        codex = FakeCodex(error=FlirtistCodexCLIError("timeout"))
        transport = FixedTransport(fallback.model_dump_json())
        gateway = FlirtistAIProviderGateway(
            _config(fallback_provider="gemini"),
            transport=transport,
            codex_provider=codex,
        )

        response = gateway.complete(
            action="analyze_chat",
            request=FlirtistChatRequest(messages=[{"speaker": "them", "text": "Hi"}]),
            fallback=fallback,
        )

        self.assertEqual(response, fallback)
        self.assertEqual(codex.calls, 1)
        self.assertEqual(transport.providers, ["gemini"])

    def test_training_coach_chat_uses_api_without_calling_codex(self) -> None:
        codex = FakeCodex(
            text=json.dumps(
                {
                    "message": {"role": "assistant", "text": "이 답장으로 자연스럽게 이어가 보자."},
                    "suggestions": ["짧게 보내기", "질문 하나 붙이기"],
                },
                ensure_ascii=False,
            )
        )
        transport = FixedTransport(
            json.dumps(
                {
                    "message": {"role": "assistant", "text": "API 코치 답변"},
                    "suggestions": ["하나", "둘"],
                },
                ensure_ascii=False,
            )
        )
        ai = FlirtistProductAI(
            config=_config(fallback_provider="gemini"),
            provider_transport=transport,
            codex_provider=codex,
        )

        response = ai.complete_coach_chat(
            request=FlirtistCoachChatRequest(locale="ko-KR", message="뭐라고 답할까?"),
            fallback=_coach_fallback(),
        )

        self.assertEqual(response.message.text, "API 코치 답변")
        self.assertEqual(codex.calls, 0)
        self.assertEqual(transport.providers, ["gemini"])

    def test_training_coach_chat_does_not_try_codex_when_api_is_used(self) -> None:
        codex = FakeCodex(error=FlirtistCodexCLIError("process_exit"))
        transport = FixedTransport(
            json.dumps(
                {
                    "message": {"role": "assistant", "text": "API fallback 답변"},
                    "suggestions": ["하나", "둘"],
                },
                ensure_ascii=False,
            )
        )
        ai = FlirtistProductAI(
            config=_config(fallback_provider="gemini"),
            provider_transport=transport,
            codex_provider=codex,
        )

        response = ai.complete_coach_chat(
            request=FlirtistCoachChatRequest(locale="ko-KR", message="뭐라고 답할까?"),
            fallback=_coach_fallback(),
        )

        self.assertEqual(response.message.text, "API fallback 답변")
        self.assertEqual(codex.calls, 0)
        self.assertEqual(transport.providers, ["gemini"])

    def test_other_product_features_keep_codex_as_primary_provider(self) -> None:
        codex = FakeCodex(text=json.dumps({"replyCoaching": {"headline": "Codex 스타일"}}, ensure_ascii=False))
        transport = FixedTransport("should-not-run")
        ai = FlirtistProductAI(
            config=_config(fallback_provider="gemini"),
            provider_transport=transport,
            codex_provider=codex,
        )

        response = ai.complete_style(
            request=FlirtistReplyStyleRequest(
                locale="ko-KR",
                context="상대가 오늘 뭐 했냐고 물었다.",
                baseReply="오늘은 쉬었어.",
                style="genuine",
            ),
            fallback=_style_fallback(),
        )

        self.assertEqual(response.replyCoaching.headline, "Codex 스타일")
        self.assertEqual(codex.calls, 1)
        self.assertEqual(transport.providers, [])


class FakeCodex:
    def __init__(self, *, text: str | None = None, error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls = 0

    def complete_json(self, **kwargs) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        assert self.text is not None
        return self.text


class FixedTransport:
    def __init__(self, text: str) -> None:
        self.text = text
        self.providers: list[FlirtistProvider] = []

    def complete_text(self, *, provider: FlirtistProvider, prompt: str, config: FlirtistAIConfig) -> str:
        self.providers.append(provider)
        if self.text == "should-not-run":
            raise AssertionError("API fallback ran after valid Codex output")
        return self.text


def _config(*, fallback_provider: FlirtistProvider) -> FlirtistAIConfig:
    return FlirtistAIConfig(
        requested_provider="codex_cli",
        effective_provider="codex_cli",
        openai_model="gpt-test",
        anthropic_model="claude-test",
        gemini_model="gemini-test",
        fallback_provider=fallback_provider,
    )


def _legacy_fallback() -> FlirtistResponse:
    return FlirtistResponse(
        summary="Summary",
        interestScore=60,
        vibe="Warm",
        riskFlags=[],
        nextMove="Reply",
        recommendedAction="Send",
        replies=["Hi"],
        whyItWorks=["Specific"],
        improvedDraft="Hi there",
        profileSuggestions=["Be specific"],
        confidenceScore=0.8,
        language="en",
        locale="en-US",
        aiObviousness=10,
        pressure=10,
        replyLikelihood=80,
    )


def _coach_fallback():
    from app.schemas.flirtist_product import FlirtistCoachChatResponse, FlirtistCoachMessage

    return FlirtistCoachChatResponse(
        sessionId="coach_test",
        message=FlirtistCoachMessage(role="assistant", text="fallback"),
        suggestions=["fallback suggestion"],
        memorySummary=None,
    )


def _style_fallback():
    from app.schemas.flirtist_product import (
        FlirtistReplyCoaching,
        FlirtistReplyOption,
        FlirtistReplyStyleResponse,
    )

    option = FlirtistReplyOption(
        id="reply_test",
        style="genuine",
        text="오늘은 푹 쉬었어.",
        whyItWorks="자연스럽고 부담이 적어요.",
        aiObviousness=10,
        pressure=10,
        replyLikelihood=80,
    )
    return FlirtistReplyStyleResponse(
        sessionId="style_test",
        replyCoaching=FlirtistReplyCoaching(
            headline="기본 스타일",
            summary="가볍게 이어가요.",
            nextMove="질문을 하나 덧붙여 보세요.",
            replies=[option],
        ),
    )


if __name__ == "__main__":
    unittest.main()
