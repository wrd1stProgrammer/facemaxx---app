from __future__ import annotations

import unittest

from app.services.ai.base import ProviderAnalysisRequest
from app.services.ai.gemini import GeminiFaceAnalysisProvider


PLACEHOLDER_MARKERS = (
    "photo estimate",
    "a balanced overall outline",
    "eyes that anchor",
    "a mouth shape",
    "하안부 높이를 전체 얼굴 높이와 비교한 값입니다",
)


class GeminiProportionsQualityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = GeminiFaceAnalysisProvider.__new__(GeminiFaceAnalysisProvider)
        self.provider.model_name = "test-model"

    def test_normalize_payload_removes_template_markers_when_proportions_result_is_generic(self) -> None:
        request = ProviderAnalysisRequest(
            user_id=None,
            mode_id="proportions",
            locale="en",
            face_metrics=[],
        )
        payload = {
            "metrics": [
                {
                    "section": "shapes",
                    "metric_id": "face-shape",
                    "title_key": "analysis.aestheticsResults.shape.faceShape",
                    "value_text": "Photo estimate · a balanced overall outline and length",
                    "detail_text": "This is a face shape metric definition, not a user read.",
                    "sort_order": 10,
                },
                {
                    "section": "shapes",
                    "metric_id": "lip-shape",
                    "title_key": "analysis.aestheticsResults.shape.lipShape",
                    "value_text": "Photo estimate · a mouth shape that supports lower-face balance",
                    "detail_text": "A mouth shape tells how the lower face reads.",
                    "sort_order": 40,
                },
            ],
        }

        normalized = self.provider._normalize_payload(payload, request)

        combined = " ".join(
            f"{item.get('value_text', '')} {item.get('detail_text', '')}".lower()
            for item in normalized["metrics"]
        )
        for marker in PLACEHOLDER_MARKERS:
            self.assertNotIn(marker.lower(), combined)
        self.assertIn("your", combined)
        self.assertIn("photo", combined)

    def test_normalize_payload_removes_template_markers_from_unknown_proportions_metric(self) -> None:
        request = ProviderAnalysisRequest(
            user_id=None,
            mode_id="proportions",
            locale="en",
            face_metrics=[],
        )
        payload = {
            "metrics": [
                {
                    "section": "proportions",
                    "metric_id": "extra-template-row",
                    "value_text": "Photo estimate · a balanced overall outline and length",
                    "detail_text": "The extra row helps explain the whole face balance.",
                    "sort_order": 999,
                },
            ],
        }

        normalized = self.provider._normalize_payload(payload, request)

        combined = " ".join(
            f"{item.get('value_text', '')} {item.get('detail_text', '')}".lower()
            for item in normalized["metrics"]
        )
        for marker in PLACEHOLDER_MARKERS:
            self.assertNotIn(marker.lower(), combined)
        self.assertNotIn("helps explain", combined)
        self.assertIn("retake", combined)

    def test_normalize_payload_preserves_measured_korean_value_when_placeholder_is_sanitized(self) -> None:
        request = ProviderAnalysisRequest(
            user_id=None,
            mode_id="proportions",
            locale="ko",
            face_metrics=[
                {
                    "metric_id": "face-width-height-ratio",
                    "numeric_value": 1.58,
                    "display_value": "1.58 · 균형",
                    "interpretation_label_ko": "균형",
                    "unit": None,
                },
            ],
        )
        payload = {
            "metrics": [
                {
                    "section": "proportions",
                    "metric_id": "face-width-height-ratio",
                    "title_key": "analysis.aestheticsResults.proportion.faceWidthHeightRatio",
                    "value_text": "Photo estimate · a stable width-to-height balance",
                    "detail_text": "얼굴 외곽 윤곽의 가로와 세로 균형을 보는 지표입니다.",
                    "sort_order": 70,
                },
            ],
        }

        normalized = self.provider._normalize_payload(payload, request)

        metric = normalized["metrics"][0]
        combined = f"{metric.get('value_text', '')} {metric.get('detail_text', '')}"
        self.assertEqual(metric["value_text"], "1.58 · 균형")
        self.assertEqual(metric["numeric_value"], 1.58)
        self.assertIn("사용자", combined)
        self.assertNotIn("보는 지표입니다", combined)

    def test_normalize_payload_removes_korean_definition_copy_when_metric_is_generic(self) -> None:
        request = ProviderAnalysisRequest(
            user_id=None,
            mode_id="proportions",
            locale="ko",
            face_metrics=[],
        )
        payload = {
            "metrics": [
                {
                    "section": "proportions",
                    "metric_id": "lower-full-face-ratio",
                    "title_key": "analysis.aestheticsResults.proportion.lowerFullFaceRatio",
                    "value_text": "0.69",
                    "detail_text": "하안부 높이를 전체 얼굴 높이와 비교한 값입니다.",
                    "sort_order": 130,
                },
            ],
        }

        normalized = self.provider._normalize_payload(payload, request)

        metric = normalized["metrics"][0]
        combined = f"{metric.get('value_text', '')} {metric.get('detail_text', '')}"
        for marker in PLACEHOLDER_MARKERS:
            self.assertNotIn(marker, combined)
        self.assertIn("사용자", combined)
        self.assertIn("사진", combined)

    def test_normalize_payload_uses_non_template_detail_when_non_proportions_detail_is_missing(self) -> None:
        request = ProviderAnalysisRequest(
            user_id=None,
            mode_id="aesthetics",
            locale="en",
            face_metrics=[],
        )
        payload = {
            "metrics": [
                {
                    "section": "detailed_metrics",
                    "metric_id": "jawline",
                    "title_key": "analysis.results.metric.jawline",
                    "value_text": "7.1 · balanced",
                    "sort_order": 10,
                },
            ],
        }

        normalized = self.provider._normalize_payload(payload, request)

        detail_text = normalized["metrics"][0]["detail_text"].lower()
        self.assertNotIn("this result", detail_text)
        self.assertNotIn("helps explain", detail_text)
        self.assertIn("photo", detail_text)
        self.assertIn("retake", detail_text)


if __name__ == "__main__":
    unittest.main()
