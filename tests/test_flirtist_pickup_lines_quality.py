from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app


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
