from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.flirtist import FlirtistPickupLinesRequest, FlirtistPickupLinesResponse
from app.services.flirtist_pickup_lines import curate_pickup_lines, pickup_lines_prompt


CLICHE_FRAGMENTS = (
    "smooth opener",
    "perfect line",
    "least rehearsed",
    "wanted to meet you",
    "risk a slightly awkward hello",
    "점수 후하게",
    "연습 중",
    "말 걸까 말까",
    "핑계를 찾다가",
    "그냥 지나가기 아쉬",
)


class FlirtistPickupLinesQualityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict("os.environ", {"FLIRTIST_AI_PROVIDER": "mock"}, clear=False)
        self.env_patch.start()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_pickup_lines_are_specific_and_not_cliche_when_bookstore_context_is_given(self) -> None:
        # Given
        payload = {
            "locale": "en-US",
            "situation": "They are reading a Murakami novel in a quiet bookstore cafe on a rainy afternoon.",
        }

        # When
        response = self.client.post("/api/flirtist/pickup-lines", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        lines = response.json()["lines"]
        joined = " ".join(lines).lower()
        self.assertEqual(len(lines), 20)
        self.assertEqual(len({line.lower() for line in lines}), 20)
        self.assertGreaterEqual(sum("book" in line.lower() or "rain" in line.lower() or "murakami" in line.lower() for line in lines), 10)
        self.assertFalse(any(fragment in joined for fragment in CLICHE_FRAGMENTS))

    def test_korean_pickup_lines_use_context_without_repeating_permission_openers(self) -> None:
        # Given
        payload = {
            "locale": "ko-KR",
            "situation": "비 오는 날 조용한 북카페에서 상대가 무라카미 소설을 읽고 있음",
        }

        # When
        response = self.client.post("/api/flirtist/pickup-lines", json=payload)

        # Then
        self.assertEqual(response.status_code, 200)
        lines = response.json()["lines"]
        joined = " ".join(lines)
        self.assertEqual(len(lines), 20)
        self.assertEqual(len({line for line in lines}), 20)
        self.assertGreaterEqual(sum("북카페" in line or "비" in line or "무라카미" in line or "소설" in line for line in lines), 10)
        self.assertLessEqual(sum(line.startswith("혹시") for line in lines), 4)
        self.assertNotIn("소설는", joined)
        self.assertNotIn("책랑", joined)
        self.assertFalse(any(fragment in joined for fragment in CLICHE_FRAGMENTS))

    def test_pickup_prompt_treats_channel_relationship_goal_and_negation_as_constraints(self) -> None:
        # Given
        situation = (
            "헬스장에서 자주 마주치던 사람이 인스타 스토리에 러닝 사진을 올렸어. "
            "아직 말은 거의 안 해봤고 DM 답장으로 운동 훈수처럼 보이지 않게 가볍게 대화를 시작하고 싶어."
        )
        request = FlirtistPickupLinesRequest(locale="ko-KR", situation=situation)
        fallback = FlirtistPickupLinesResponse(
            situation=situation,
            lines=[f"fallback {index}" for index in range(20)],
            language="ko",
            locale="ko-KR",
        )

        # When
        prompt = pickup_lines_prompt(request=request, fallback=fallback)

        # Then
        self.assertIn(situation, prompt)
        self.assertIn("communication channel", prompt)
        self.assertIn("relationship stage", prompt)
        self.assertIn("desired conversational outcome", prompt)
        self.assertIn("Negated preferences are hard constraints", prompt)
        self.assertIn("Do not ask for information already present", prompt)
        self.assertIn("narrator's casual wording", prompt)
        self.assertIn("barely spoken, default to natural Korean 존댓말", prompt)
        self.assertIn("no advice, warning, correction, or technique question", prompt)
        self.assertNotIn("fallback 0", prompt)

    def test_curator_enforces_no_coaching_constraint(self) -> None:
        situation = (
            "헬스장에서 자주 마주치던 사람이 인스타 스토리에 러닝 사진을 올렸어. "
            "아직 말은 거의 안 해봤고 운동 훈수처럼 보이지 않게 가볍게 대화를 시작하고 싶어."
        )
        unsafe = [
            "러닝 팁 하나만 알려주실래요?",
            "페이스 조절은 어떻게 하세요?",
            "운동 루틴 추천해 주세요!",
            "달릴 때 호흡은 어떤 편이에요",
            "꾸준히 뛸 수 있는 비결이 궁금해요",
            "다음번엔 같이 한 바퀴 돌면 좋겠네요",
        ]

        lines = curate_pickup_lines(unsafe, "ko", situation)

        self.assertEqual(len(lines), 20)
        self.assertFalse(any(term in " ".join(lines) for term in ("팁", "추천", "어떻게", "루틴", "알려")))
        self.assertFalse(any(fragment in " ".join(lines) for fragment in ("러닝가", "러닝를", "러닝는")))

    def test_curator_does_not_hallucinate_running_or_questions_for_bookstore_request(self) -> None:
        situation = "조용한 북카페에서 책 읽는 사람에게 조언이나 질문 없이 가볍게 한마디 하고 싶어."
        unsafe = [
            "무슨 책 읽고 계세요",
            "오늘은 어떤 작가 좋아하세요",
            "지금 읽는 책 제목이 뭐예요",
        ] * 7

        lines = curate_pickup_lines(unsafe, "ko", situation)
        joined = " ".join(lines)

        self.assertEqual(len(lines), 20)
        self.assertEqual(len(set(lines)), 20)
        self.assertTrue(all("북카페" in line for line in lines))
        self.assertNotIn("?", joined)
        self.assertFalse(any(term in joined for term in ("러닝", "운동", "뛰", "루틴", "알려", "신경 쓰")))
