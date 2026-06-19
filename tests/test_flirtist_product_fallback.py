from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistProductSessionResponse
from app.schemas.flirtist_product import FlirtistPreviewMessage
from app.schemas.flirtist_product import FlirtistReplyCoaching
from app.schemas.flirtist_product import FlirtistReplyOption
from app.schemas.flirtist_product import FlirtistReplyStyleRequest
from app.schemas.flirtist_product import FlirtistReplyStyleResponse
from app.services.flirtist_product_service import FlirtistProductService


class FlirtistProductFallbackTest(unittest.TestCase):
    def test_reply_fallback_uses_chat_context_when_ai_is_unavailable(self) -> None:
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
            text="Them: 나 오늘 회계 시험 붙었어 드디어 끝났다\nMe: 진짜? 완전 축하해",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        pack_text = " ".join(
            reply.text
            for pack in response.replyCoaching.replyPacks
            for reply in pack.replies
        )
        self.assertRegex(reply_text, "회계|시험|축하")
        self.assertRegex(pack_text, "회계|시험|축하")
        self.assertNotIn("회사", reply_text)
        self.assertNotIn("힘 빠졌겠다", pack_text)

    def test_reply_fallback_ignores_ocr_message_placeholder(self) -> None:
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
            text="Them: 어제 말한 영화 봤어 진짜 재밌더라\nMe: 오 진짜? 어땠어?\nMessage...",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        preview_text = " ".join(message.text for message in response.chatPreview)
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        self.assertNotIn("Message", preview_text)
        self.assertNotIn("Message", reply_text)
        self.assertRegex(reply_text, "영화|장면|추천|스포|봐야")
        self.assertNotIn("얘기 조금 더 듣고 싶어", reply_text)

    def test_provider_reply_with_ui_placeholder_is_replaced_with_contextual_reply(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoisyProviderAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            text="Them: 어제 말한 영화 봤어 진짜 재밌더라\nMe: 오 진짜? 어땠어?\nMessage...",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        self.assertNotIn("Message", reply_text)
        self.assertRegex(reply_text, "영화|재밌|궁금|얘기")

    def test_english_reply_fallback_does_not_echo_first_person_context_as_topic(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="en-US",
            text="Them: I finally passed my accounting exam\nMe: no way congrats\nMessage...",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        self.assertNotIn("Message", reply_text)
        self.assertNotIn("after I finally passed", reply_text)
        self.assertRegex(reply_text.lower(), "congrats|celebrat|proud|exam")

    def test_style_regeneration_replaces_ui_placeholder_reply(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoisyProviderAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistReplyStyleRequest(
            locale="ko-KR",
            context="Them: 어제 말한 영화 봤어 진짜 재밌더라\nMe: 오 진짜? 어땠어?\nMessage...",
            baseReply="Message... 얘기 조금 더 듣고 싶어.",
            style="nsfw",
        )

        # When
        response = service.regenerate_reply(request)

        # Then
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        self.assertNotIn("Message", reply_text)
        self.assertRegex(reply_text, "영화|재밌|반응|스포")

    def test_reply_fallback_uses_accepted_meetup_context_after_short_positive_reply(self) -> None:
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

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        all_reply_text = " ".join(
            reply.text
            for pack in response.replyCoaching.replyPacks
            for reply in pack.replies
        )
        self.assertRegex(all_reply_text, "광주|맛난|맛있는|연락|만나")
        self.assertNotIn("무슨 상황", all_reply_text)
        self.assertNotIn("나는 이런 얘기 편하게 해주는 게 좋더라", all_reply_text)

    def test_manual_reply_fallback_handles_just_hanging_out_answer(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="manual",
            locale="ko-KR",
            text="나: 뭐해\n상대: 그냥있어",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        all_reply_text = " ".join(
            reply.text
            for pack in response.replyCoaching.replyPacks
            for reply in pack.replies
        )
        self.assertRegex(all_reply_text, "그냥|심심|잠깐|놀아|전화|보이스")
        self.assertNotIn("무슨 상황", all_reply_text)
        self.assertNotIn("앞뒤가 제일 궁금", all_reply_text)

    def test_manual_session_keeps_user_transcript_chat_preview_when_provider_returns_wrong_preview(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=WrongPreviewProviderAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="manual",
            locale="ko-KR",
            text="나: 뭐해\n상대: 그냥있어",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertEqual(
            [message.model_dump() for message in response.chatPreview],
            [
                {"role": "me", "text": "뭐해"},
                {"role": "them", "text": "그냥있어"},
            ],
        )
        assert response.replyCoaching is not None
        all_reply_text = " ".join(
            reply.text
            for pack in response.replyCoaching.replyPacks
            for reply in pack.replies
        )
        self.assertRegex(all_reply_text, "그냥|심심|잠깐|놀아|전화|보이스")
        self.assertNotIn("말도 안 되는 일", all_reply_text)


class NoopAI:
    def complete_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        fallback: FlirtistProductSessionResponse,
        image_url: str | None,
    ) -> FlirtistProductSessionResponse:
        return fallback


class WrongPreviewProviderAI:
    def complete_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        fallback: FlirtistProductSessionResponse,
        image_url: str | None,
    ) -> FlirtistProductSessionResponse:
        assert fallback.replyCoaching is not None
        wrong_reply = FlirtistReplyOption(
            id="reply_wrong_preview",
            style="genuine",
            text="잠깐, 그건 앞뒤가 제일 궁금한데. 무슨 상황이었어?",
            whyItWorks="Wrong generic provider answer.",
            aiObviousness=12,
            pressure=18,
            replyLikelihood=84,
        )
        return fallback.model_copy(
            update={
                "chatPreview": [FlirtistPreviewMessage(role="them", text="방금 진짜 말도 안 되는 일 생김")],
                "replyCoaching": FlirtistReplyCoaching(
                    headline=fallback.replyCoaching.headline,
                    summary=fallback.replyCoaching.summary,
                    nextMove=fallback.replyCoaching.nextMove,
                    replies=[wrong_reply],
                    replyPacks=[],
                ),
            }
        )


class NoisyProviderAI:
    def complete_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        fallback: FlirtistProductSessionResponse,
        image_url: str | None,
    ) -> FlirtistProductSessionResponse:
        assert fallback.replyCoaching is not None
        noisy = FlirtistReplyOption(
            id="reply_noisy",
            style="genuine",
            text="Message... 얘기 조금 더 듣고 싶어. 편할 때 이어서 말해줘.",
            whyItWorks="Looks valid but leaks OCR UI chrome.",
            aiObviousness=12,
            pressure=18,
            replyLikelihood=84,
        )
        return fallback.model_copy(
            update={
                "replyCoaching": FlirtistReplyCoaching(
                    headline=fallback.replyCoaching.headline,
                    summary=fallback.replyCoaching.summary,
                    nextMove=fallback.replyCoaching.nextMove,
                    replies=[noisy],
                    replyPacks=[],
                )
            }
        )

    def complete_style(
        self,
        *,
        request: FlirtistReplyStyleRequest,
        fallback: FlirtistReplyStyleResponse,
    ) -> FlirtistReplyStyleResponse:
        noisy = FlirtistReplyOption(
            id="reply_style_noisy",
            style=request.style,
            text="Message... 얘기 들으니까 괜히 더 궁금해졌어.",
            whyItWorks="Looks valid but leaks OCR UI chrome.",
            aiObviousness=12,
            pressure=18,
            replyLikelihood=84,
        )
        return fallback.model_copy(
            update={
                "replyCoaching": FlirtistReplyCoaching(
                    headline=fallback.replyCoaching.headline,
                    summary=fallback.replyCoaching.summary,
                    nextMove=fallback.replyCoaching.nextMove,
                    replies=[noisy],
                    replyPacks=[],
                )
            }
        )


class NoopImageStorage:
    def store_session_image(
        self,
        request: FlirtistProductSessionRequest,
        *,
        user_id: str | None = None,
        client_install_id: str | None = None,
    ) -> None:
        return None


class NoopRepository:
    def save_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        response: FlirtistProductSessionResponse,
        stored_image: None,
        user_id: str | None = None,
        client_install_id: str | None = None,
    ) -> bool:
        return False


if __name__ == "__main__":
    unittest.main()
