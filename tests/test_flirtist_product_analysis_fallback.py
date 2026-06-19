from __future__ import annotations

import unittest

from app.schemas.flirtist_product import FlirtistProductSessionRequest
from app.services.flirtist_product_service import FlirtistProductService
from tests.test_flirtist_product_fallback import NoopAI, NoopImageStorage, NoopRepository


class FlirtistProductAnalysisFallbackTest(unittest.TestCase):
    def test_score_analysis_fallback_uses_transcript_keywords(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="score_analysis",
            source="screenshot",
            locale="ko-KR",
            text=(
                "Them: 운빈 할머니집 차안에서 기다리구 우웅\n"
                "Me: 점심 먹고 낮잠 자다가 나갈게\n"
                "Them: 다녀와아앙 ㅎㅎ"
            ),
        )

        # When
        response = service.create_session(request)

        # Then
        assert response.analysisCard is not None
        card = response.analysisCard
        self.assertEqual(card.title, "대화 분석")
        self.assertIn("점심", card.meaningfulWordsYou)
        self.assertIn("낮잠", card.meaningfulWordsYou)
        self.assertIn("운빈", card.meaningfulWordsThem)
        self.assertIn("할머니집", card.meaningfulWordsThem)
        self.assertNotIn("커피", card.meaningfulWordsYou)
        self.assertNotIn("회사", card.meaningfulWordsThem)

    def test_score_analysis_fallback_detects_plan_signals(self) -> None:
        # Given
        service = FlirtistProductService(
            ai=NoopAI(),
            image_storage=NoopImageStorage(),
            repository=NoopRepository(),
        )
        request = FlirtistProductSessionRequest(
            mode="score_analysis",
            source="screenshot",
            locale="ko-KR",
            text=(
                "Them: 오늘는 광주에 사는거야?\n"
                "Me: 웅 나는 광주 살앙\n"
                "Me: 나중에 광주 올 일 생기면 미리 연락해 맛난거 사줄겤ㅋㅋ\n"
                "Them: 웅 조아네"
            ),
        )

        # When
        response = service.create_session(request)

        # Then
        assert response.analysisCard is not None
        card = response.analysisCard
        self.assertGreaterEqual(card.compatibilityScore, 70)
        self.assertTrue(any("약속" in flag or "장소" in flag for flag in card.greenFlags))
        self.assertIn("광주", card.meaningfulWordsYou)
        self.assertNotIn("퇴근", card.meaningfulWordsYou)


if __name__ == "__main__":
    unittest.main()
