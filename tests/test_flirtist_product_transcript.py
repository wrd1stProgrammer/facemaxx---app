from __future__ import annotations

import unittest

from app.services.flirtist_product_transcript import preview_messages
from app.services.flirtist_product_transcript import sanitized_transcript_text


class FlirtistProductTranscriptTest(unittest.TestCase):
    def test_sanitized_transcript_removes_status_bar_and_scan_chrome(self) -> None:
        # Given
        transcript = "\n".join(
            [
                "11:01",
                "LTE",
                "AI coach is extracting hidden chemistry & interest signals",
                "Them: 오늘 회사가 정신이 하나도 없었어",
                "Me: 그래도 퇴근은 했어?",
                "Enter a message",
                "999+",
            ]
        )

        # When
        sanitized = sanitized_transcript_text(transcript)

        # Then
        assert sanitized is not None
        self.assertIn("Them: 오늘 회사가 정신이 하나도 없었어", sanitized)
        self.assertIn("Me: 그래도 퇴근은 했어?", sanitized)
        self.assertNotIn("LTE", sanitized)
        self.assertNotIn("AI coach", sanitized)
        self.assertNotIn("Enter a message", sanitized)
        self.assertNotIn("999+", sanitized)

    def test_preview_messages_keeps_roles_after_noise_cleanup(self) -> None:
        # Given
        transcript = "\n".join(
            [
                "5G",
                "Them: 웅 조아네",
                "Me: 광주 오면 맛난 거 사줄게",
                "Reading the chat",
            ]
        )

        # When
        messages = preview_messages("ko", transcript)

        # Then
        self.assertEqual(
            [(message.role, message.text) for message in messages],
            [
                ("them", "웅 조아네"),
                ("me", "광주 오면 맛난 거 사줄게"),
            ],
        )
