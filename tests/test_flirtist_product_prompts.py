from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistProductSessionResponse
from app.schemas.flirtist_product import FlirtistCoachChatRequest
from app.schemas.flirtist_product import FlirtistCoachChatResponse
from app.schemas.flirtist_product import FlirtistCoachMessage
from app.schemas.flirtist_product import FlirtistReplyCoaching
from app.schemas.flirtist_product import FlirtistReplyOption
from app.schemas.flirtist_product import FlirtistReplyStyleRequest
from app.schemas.flirtist_product import FlirtistReplyStyleResponse
from app.services.flirtist_product_ai import _coach_prompt, _merge_response, _response_text_format, _session_prompt, _style_prompt
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
        self.assertIn("<copy-ready reply text 1>", prompt)
        self.assertNotIn("얘기 조금 더 듣고 싶어", prompt)
        self.assertNotIn("그 말 괜히 좋네", prompt)

    def test_session_prompt_requests_contextual_reply_packs_for_every_style(self) -> None:
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
            text=(
                "Them: 오늘는 광주에 사는거야?\n"
                "Me: 웅 나는 광주 살앙\n"
                "Them: 오옹 글쿠나\n"
                "Me: 나중에 광주 올 일 생기면 미리 연락해 맛난거 사줄겤ㅋㅋ\n"
                "Them: 웅 조아네"
            ),
        )
        fallback = service.create_session(request)

        # When
        prompt = _session_prompt(request, fallback)

        # Then
        self.assertIn("replyPacks", prompt)
        self.assertIn("genuine, nsfw, flirty, witty, romantic", prompt)
        self.assertIn("Each style pack must be grounded in the same latest actionable chat context", prompt)
        self.assertIn("exactly four copy-ready replies", prompt)
        self.assertIn("four different tactics", prompt)
        self.assertIn("Do not anchor all replies on the same visible noun or phrase", prompt)
        self.assertIn("same four genuine replies", prompt)
        self.assertIn("Do not invent missing plan details", prompt)
        self.assertIn("광주", prompt)
        self.assertNotIn('"sessionId"', prompt)
        self.assertNotIn("exactly one copy-ready reply", prompt)
        self.assertNotIn("include 1-3 copy-ready replies", prompt)
        self.assertNotIn("do not generate replyPacks", prompt)
        self.assertNotIn("The server will expand style packs", prompt)

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
        self.assertIn("<copy-ready reply text 1>", prompt)
        self.assertIn("Do not invent missing plan details", prompt)
        self.assertIn("Return exactly 4 alternatives", prompt)
        self.assertIn("meaningfully different", prompt)
        self.assertIn("Do not anchor every alternative on the same keyword", prompt)
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

    def test_reply_style_merge_recovers_complete_replies_from_truncated_provider_json(self) -> None:
        # Given
        fallback = FlirtistReplyStyleResponse(
            sessionId="flt_fallback",
            replyCoaching=FlirtistReplyCoaching(
                headline="AI 추천 답장",
                summary="fallback",
                nextMove="fallback",
                replies=[
                    FlirtistReplyOption(
                        id="fallback_1",
                        style="genuine",
                        text="잠깐, 그건 앞뒤가 제일 궁금한데. 무슨 상황이었어?",
                        whyItWorks="fallback",
                        aiObviousness=12,
                        pressure=18,
                        replyLikelihood=84,
                    )
                ],
                replyPacks=[],
            ),
        )
        provider_text = """
        {
          "sessionId": "flt_live",
          "replyCoaching": {
            "headline": "AI 추천 답장",
            "summary": "상대가 그냥 있다고 했으니 가볍게 시간을 열어주는 흐름",
            "nextMove": "부담 없는 제안으로 이어간다",
            "replies": [
              {
                "id": "reply_live_1",
                "style": "genuine",
                "text": "그냥 있으면 내가 잠깐 놀아줘도 돼? 심심하진 않게 해볼게.",
                "whyItWorks": "상대의 현재 상태를 받아주면서 부담 낮은 선택지를 준다.",
                "aiObviousness": 9,
                "pressure": 16,
                "replyLikelihood": 88
              }
            ],
            "replyPacks": [
        """

        # When
        response = _merge_response(provider_text, fallback, FlirtistReplyStyleResponse)

        # Then
        self.assertEqual(response.sessionId, "flt_live")
        self.assertEqual(response.replyCoaching.summary, "상대가 그냥 있다고 했으니 가볍게 시간을 열어주는 흐름")
        self.assertEqual(
            response.replyCoaching.replies[0].text,
            "그냥 있으면 내가 잠깐 놀아줘도 돼? 심심하진 않게 해볼게.",
        )
        self.assertNotIn("무슨 상황", response.replyCoaching.replies[0].text)

    def test_reply_style_merge_recovers_complete_reply_items_when_later_item_is_truncated(self) -> None:
        # Given
        fallback = FlirtistReplyStyleResponse(
            sessionId="flt_fallback",
            replyCoaching=reply_coaching("ko", "nsfw"),
        )
        provider_text = """
        {
          "sessionId": "flt_live",
          "replyCoaching": {
            "headline": "AI 추천 답장",
            "summary": "상대가 그냥 있다고 해서 가볍게 장난칠 수 있는 상황",
            "nextMove": "부담 없이 빈 시간을 잡아준다",
            "replies": [
              {
                "id": "reply_live_1",
                "style": "nsfw",
                "text": "그냥 있다니까 괜히 장난치고 싶어지는데, 받아줄 거야?",
                "whyItWorks": "상대의 빈 시간을 실제 대화 기회로 잡는다.",
                "aiObviousness": 9,
                "pressure": 18,
                "replyLikelihood": 86
              },
              {
                "id": "reply_live_2",
                "style": "nsfw",
                "text": "심심한 타이밍이면 내가 조금 위험하게 재밌게 해줘도 돼?",
                "whyItWorks": "장난의 강도를 올리되 선택권을 남긴다.",
                "aiObviousness": 10,
                "pressure": 22,
                "replyLikelihood": 84
              },
              {
                "id": "reply_live_3",
                "style": "nsfw",
                "text": "여기서 JSON이 잘리기 시작
        """

        # When
        response = _merge_response(provider_text, fallback, FlirtistReplyStyleResponse)

        # Then
        self.assertEqual(response.sessionId, "flt_live")
        self.assertEqual(
            [reply.text for reply in response.replyCoaching.replies],
            [
                "그냥 있다니까 괜히 장난치고 싶어지는데, 받아줄 거야?",
                "심심한 타이밍이면 내가 조금 위험하게 재밌게 해줘도 돼?",
            ],
        )
        self.assertNotIn("그렇게만 말하면", " ".join(reply.text for reply in response.replyCoaching.replies))

    def test_session_merge_keeps_authoritative_metadata_when_provider_returns_invalid_source(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        fallback = service.create_session(
            FlirtistProductSessionRequest(
                mode="reply_coach",
                source="screenshot",
                locale="ko-KR",
                text="Them: 웅 조아네\nMe: 광주 오면 맛난거 사줄게",
            )
        )
        provider_text = """
        {
          "source": "text",
          "mode": "reply",
          "replyCoaching": {
            "replies": [
              {
                "id": "reply_live_metadata",
                "style": "genuine",
                "text": "광주 오면 맛난 거 사준다는 약속 아직 유효해. 언제 올지 살짝 기대해도 돼?",
                "whyItWorks": "실제 대화의 광주 약속을 살린다.",
                "aiObviousness": 8,
                "pressure": 16,
                "replyLikelihood": 90
              }
            ]
          }
        }
        """

        # When
        response = _merge_response(provider_text, fallback, FlirtistProductSessionResponse)

        # Then
        self.assertEqual(response.source, "screenshot")
        self.assertEqual(response.mode, "reply_coach")
        assert response.replyCoaching is not None
        self.assertEqual(
            response.replyCoaching.replies[0].text,
            "광주 오면 맛난 거 사준다는 약속 아직 유효해. 언제 올지 살짝 기대해도 돼?",
        )

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
