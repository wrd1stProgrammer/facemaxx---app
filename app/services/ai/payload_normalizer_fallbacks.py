from __future__ import annotations


class FaceAnalysisPayloadFallbackMixin:
    @staticmethod
    def _fallback_metric_detail(metric_id: str, value_text: str | None, status_text: str | None, locale: str) -> str:
        value_part = value_text or status_text
        if locale == "ko":
            if value_part:
                return (
                    f"{value_part}로 보이지만, 현재 사진만으로는 이 항목의 세부 판단을 과하게 단정하지 않는 편이 안전합니다. "
                    "정면에 가까운 밝은 사진에서 다시 촬영하면 얼굴 구조와 표정 신호를 더 안정적으로 비교할 수 있습니다. "
                    "다음 결과에서는 조명, 각도, 표정 차이를 함께 보면 개선 포인트가 더 분명해집니다."
                )
            return (
                "현재 사진만으로는 이 항목의 세부 판단을 자신 있게 제공하기 어렵습니다. "
                "정면에 가까운 밝은 사진에서 다시 촬영하면 얼굴 구조와 표정 신호를 더 안정적으로 비교할 수 있습니다. "
                "다음 결과에서는 조명, 각도, 표정 차이를 함께 보면 개선 포인트가 더 분명해집니다."
            )
        if value_part:
            return (
                f"{value_part} is the visible read, but this photo does not give enough context for a strong personalized detail. "
                "Use a centered, well-lit retake with less tilt so the face structure and expression can be compared more reliably. "
                "The next scan should make the practical improvement point clearer."
            )
        return (
            "This photo does not give enough context for a strong personalized detail on this item. "
            "Use a centered, well-lit retake with less tilt so the face structure and expression can be compared more reliably. "
            "The next scan should make the practical improvement point clearer."
        )

    @staticmethod
    def _fallback_growth_body(locale: str) -> str:
        if locale == "ko":
            return "밝은 정면 사진으로 다시 촬영한 뒤 다음 스캔과 비교하면 개선 방향을 더 정확히 확인할 수 있습니다."
        return "Use a centered, well-lit photo and compare future scans to confirm the improvement."

    @staticmethod
    def _fallback_coach_assessment(locale: str) -> str:
        if locale == "ko":
            return "평가: 현재 사진만으로는 이 요소를 과하게 단정하지 않는 편이 안전합니다."
        return "Assessment: This photo does not give enough context for a strong personalized read."

    @staticmethod
    def _fallback_coach_action(locale: str) -> str:
        if locale == "ko":
            return "플랜: 균일한 조명과 정면에 가까운 각도로 다시 촬영한 뒤 결과를 비교하세요."
        return "Plan: Retake with even light and a near-front angle before making a routine change."
