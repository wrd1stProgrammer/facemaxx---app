from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistCoachChatRequest
from app.schemas.flirtist_product import FlirtistCoachChatResponse
from app.schemas.flirtist_product import FlirtistCoachMessage
from app.schemas.flirtist_product import FlirtistReplyStyleRequest
from app.schemas.flirtist_product import FlirtistReplyStyleResponse
from app.services.flirtist_product_ai import _coach_prompt, _response_text_format, _session_prompt, _style_prompt
from app.services.flirtist_product_reply_fallback import reply_coaching
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopAI, NoopImageStorage, NoopRepository


class FlirtistProductPromptTest(unittest.TestCase):
    def test_session_prompt_uses_quality_rubric_without_leaking_fallback_reply_text(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            text="Them: 오늘 너 생각났어 약간 웃겼음\nMe: 왜 갑자기?",
        )
        fallback = service.create_session(request)

        # When
        prompt = _session_prompt(request, fallback)

        # Then
        self.assertIn("Quality bar", prompt)
        self.assertIn("Do not copy fallback wording", prompt)
        self.assertIn("would be wrong for a different chat", prompt)
        self.assertIn("<copy-ready reply text>", prompt)
        self.assertNotIn("얘기 조금 더 듣고 싶어", prompt)
        self.assertNotIn("그 말 괜히 좋네", prompt)

    def test_style_prompt_treats_contract_as_shape_not_reply_source(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistReplyStyleRequest(
            locale="ko-KR",
            context="Them: 오늘 너 생각났어 약간 웃겼음\nMe: 왜 갑자기?",
            baseReply="그 말 괜히 좋네. 뭐 보고 내 생각났는데?",
            style="flirty",
        )
        fallback = FlirtistReplyStyleResponse(
            sessionId="flt_prompt_test",
            replyCoaching=reply_coaching("ko", request.style, focus=request.focus),
        )

        # When
        prompt = _style_prompt(request, fallback)

        # Then
        self.assertIn("Do not copy fallback wording", prompt)
        self.assertIn("<copy-ready reply text>", prompt)
        self.assertEqual(prompt.count("그 말 괜히 좋네"), 1)
        self.assertNotIn("갑자기 그렇게 말하면", prompt)

    def test_openai_response_format_uses_json_schema_not_loose_json_object(self) -> None:
        # When
        text_format = _response_text_format(FlirtistReplyStyleResponse)

        # Then
        assert isinstance(text_format, dict)
        json_format = text_format["format"]
        assert isinstance(json_format, dict)
        self.assertEqual(json_format["type"], "json_schema")
        self.assertEqual(json_format["name"], "FlirtistReplyStyleResponse")
        self.assertIn("schema", json_format)

    def test_coach_prompt_blocks_echoed_user_questions_and_template_filler(self) -> None:
        # Given
        request = FlirtistCoachChatRequest(
            locale="ko-KR",
            message="그니까 뭐라보낼까",
            history=[FlirtistCoachMessage(role="user", text="2년전 썸녀랑 술 먹고싶은데 뭐라 보내")],
        )
        fallback = FlirtistCoachChatResponse(
            sessionId="coach_prompt_test",
            message=FlirtistCoachMessage(role="assistant", text="오랜만이면 가볍게 열어봐."),
            suggestions=["더 짧게"],
        )

        # When
        prompt = _coach_prompt(request, fallback)

        # Then
        self.assertIn("Do not quote", prompt)
        self.assertIn("그니까 뭐라보낼까", prompt)
        self.assertIn("previous meaningful user message", prompt)
        self.assertIn("Avoid templated coaching filler", prompt)
        self.assertIn("copy-ready line or spoken opener", prompt)

    def test_coach_prompt_instructs_model_to_use_compact_memory(self) -> None:
        # Given
        request = FlirtistCoachChatRequest(
            locale="ko-KR",
            message="그니까 뭐라보낼까",
            context="Coach memory:\n- 2년 전 썸녀에게 술 한잔 제안하려 함.",
            history=[],
        )
        fallback = FlirtistCoachChatResponse(
            sessionId="coach_memory_prompt_test",
            message=FlirtistCoachMessage(role="assistant", text="오랜만이면 가볍게 열어봐."),
            suggestions=["더 짧게"],
        )

        # When
        prompt = _coach_prompt(request, fallback)

        # Then
        self.assertIn("Coach memory", prompt)
        self.assertIn("compact rolling memory", prompt)
        self.assertIn("memorySummary", prompt)


if __name__ == "__main__":
    unittest.main()
