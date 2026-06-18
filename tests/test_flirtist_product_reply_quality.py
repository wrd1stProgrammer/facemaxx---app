from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.schemas.flirtist_product import FlirtistProductSessionResponse
from app.schemas.flirtist_product import FlirtistReplyCoaching
from app.schemas.flirtist_product import FlirtistReplyOption
from app.services.flirtist_product_service import FlirtistProductService


class FlirtistProductReplyQualityTest(unittest.TestCase):
    def test_affection_fallback_sounds_like_a_real_reply_without_echoing_source(self) -> None:
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

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        self.assertNotIn("오늘 너 생각났어 약간 웃겼음 얘기", reply_text)
        self.assertNotIn("쪽으로 더 얘기", reply_text)
        self.assertRegex(reply_text, "왜|뭐|순간|생각|기분|웃긴")

    def test_provider_low_value_echo_reply_is_repaired(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=LowValueProviderAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="reply_coach",
            source="screenshot",
            locale="ko-KR",
            text="Them: 오늘 너 생각났어 약간 웃겼음\nMe: 왜 갑자기?",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        self.assertNotIn("오늘 너 생각났어 약간 웃겼음 얘기", reply_text)
        self.assertNotIn("편할 때 이어서", reply_text)
        self.assertRegex(reply_text, "왜|뭐|순간|생각|기분|웃긴")

    def test_english_affection_fallback_does_not_echo_source_as_topic(self) -> None:
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
            text="Them: I randomly thought of you today lol\nMe: wait why?",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        self.assertNotIn("I want to hear more about I randomly thought", reply_text)
        self.assertRegex(reply_text.lower(), "thought|mind|what made|what was|why")

    def test_generic_fallback_asks_for_context_without_full_source_echo(self) -> None:
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
            text="Them: 방금 진짜 말도 안 되는 일 생김\nMe: 뭐야",
        )

        # When
        response = service.create_session(request)

        # Then
        self.assertIsNotNone(response.replyCoaching)
        assert response.replyCoaching is not None
        reply_text = " ".join(reply.text for reply in response.replyCoaching.replies)
        self.assertNotIn("방금 진짜 말도 안 되는 일 생김 얘기", reply_text)
        self.assertNotIn("편할 때 이어서", reply_text)
        self.assertRegex(reply_text, "무슨|앞뒤|상황|일|맥락")


class NoopAI:
    def complete_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        fallback: FlirtistProductSessionResponse,
        image_url: str | None,
    ) -> FlirtistProductSessionResponse:
        return fallback


class LowValueProviderAI:
    def complete_session(
        self,
        *,
        request: FlirtistProductSessionRequest,
        fallback: FlirtistProductSessionResponse,
        image_url: str | None,
    ) -> FlirtistProductSessionResponse:
        assert fallback.replyCoaching is not None
        weak = FlirtistReplyOption(
            id="reply_low_value",
            style="genuine",
            text="오늘 너 생각났어 약간 웃겼음 얘기 조금 더 듣고 싶어. 편할 때 이어서 말해줘.",
            whyItWorks="It echoes source text and offers no situational value.",
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
                    replies=[weak],
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
