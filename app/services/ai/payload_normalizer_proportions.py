from __future__ import annotations

import re

from app.services.ai.base import ProviderAnalysisRequest


class FaceAnalysisPayloadProportionsMixin:
    def _proportions_missing_metric_ids(self, data: dict) -> list[str]:
        required_ids = [str(spec["metric_id"]) for spec in self.proportions_required_metrics]
        metrics = self._as_list((data or {}).get("metrics")) if isinstance(data, dict) else []
        existing_ids = {
            self._slug(item.get("metric_id") or item.get("id") or item.get("title"))
            for item in metrics
            if isinstance(item, dict)
        }
        return [metric_id for metric_id in required_ids if metric_id not in existing_ids]

    def _proportions_placeholder_metric_count(self, data: dict) -> int:
        metrics = self._as_list((data or {}).get("metrics")) if isinstance(data, dict) else []
        count = 0
        for item in metrics:
            if not isinstance(item, dict):
                continue
            if self._has_proportions_placeholder_text(item):
                count += 1
        return count

    def _ensure_proportions_metrics(self, data: dict, request: ProviderAnalysisRequest) -> None:
        metrics = [
            item
            for item in self._as_list(data.get("metrics"))
            if isinstance(item, dict)
        ]
        existing_ids = {
            self._slug(item.get("metric_id"))
            for item in metrics
        }
        measured_by_id = self._face_metric_lookup(request.face_metrics or [])

        for spec in self.proportions_required_metrics:
            metric_id = spec["metric_id"]
            if metric_id in existing_ids:
                continue
            measured = measured_by_id.get(metric_id)
            if measured is None:
                continue
            metrics.append(self._fallback_proportions_metric(spec, measured, request.locale))

        metrics.sort(key=lambda item: self._int(item.get("sort_order"), 999))
        data["metrics"] = metrics

    def _sanitize_proportions_template_metrics(
        self,
        data: dict,
        request: ProviderAnalysisRequest,
    ) -> None:
        metrics = [
            item
            for item in self._as_list(data.get("metrics"))
            if isinstance(item, dict)
        ]
        measured_by_id = self._face_metric_lookup(request.face_metrics or [])
        for item in metrics:
            if not self._has_proportions_placeholder_text(item):
                continue
            spec = self._proportions_metric_spec(self._slug(item.get("metric_id")))
            if spec is None:
                value_text = self._estimated_unknown_value_text(request.locale)
                item["value_text"] = value_text
                item["detail_text"] = self._fallback_metric_detail(
                    self._slug(item.get("metric_id")),
                    value_text,
                    None,
                    request.locale,
                )
                item["value_tint"] = "#A7A7B2"
                continue
            measured = measured_by_id.get(str(spec["metric_id"]))
            value_text = self._measured_value_text(measured, request.locale)
            has_value = bool(value_text)
            if not value_text:
                value_text = self._estimated_value_text(spec, request.locale)
            item["value_text"] = value_text
            item["numeric_value"] = self._optional_float((measured or {}).get("numeric_value"))
            item["unit"] = self._optional_string((measured or {}).get("unit"))
            item["status_text"] = self._optional_string(
                (measured or {}).get(
                    "interpretation_label_ko" if request.locale == "ko" else "interpretation_label_en"
                )
            )
            item["detail_text"] = self._proportions_detail_text(
                spec,
                value_text,
                has_value,
                request.locale,
            )
            item["value_tint"] = "#34D15C" if has_value else "#A7A7B2"

    @classmethod
    def _has_proportions_placeholder_text(cls, item: dict) -> bool:
        value_text = str(item.get("value_text") or item.get("display_value") or "").lower()
        detail_text = str(item.get("detail_text") or item.get("description") or "").lower()
        return any(
            marker in value_text or marker in detail_text
            for marker in cls.proportions_placeholder_markers
        )

    def _proportions_metric_spec(self, metric_id: str) -> dict[str, object] | None:
        for spec in self.proportions_required_metrics:
            if spec["metric_id"] == metric_id:
                return spec
        return None

    def _fallback_proportions_metric(
        self,
        spec: dict[str, object],
        measured: dict[str, object] | None,
        locale: str,
    ) -> dict:
        metric_id = str(spec["metric_id"])
        value_text = self._measured_value_text(measured, locale)
        has_value = bool(value_text)
        if not value_text:
            value_text = self._estimated_value_text(spec, locale)

        return {
            "section": spec["section"],
            "metric_id": metric_id,
            "title_key": spec["title_key"],
            "value_text": value_text,
            "numeric_value": self._optional_float((measured or {}).get("numeric_value")),
            "unit": self._optional_string((measured or {}).get("unit")),
            "status_text": self._optional_string((measured or {}).get("interpretation_label_ko" if locale == "ko" else "interpretation_label_en")),
            "detail_text": self._proportions_detail_text(spec, value_text, has_value, locale),
            "icon_name": spec["icon_name"],
            "value_tint": "#34D15C" if has_value else "#A7A7B2",
            "sort_order": spec["sort_order"],
        }

    def _proportions_detail_text(
        self,
        spec: dict[str, object],
        value_text: str,
        has_measured_value: bool,
        locale: str,
    ) -> str:
        if locale == "ko":
            label = str(spec["ko_label"])
            read = str(spec["ko_read"])
            effect = str(spec["ko_effect"])
            if has_measured_value:
                return (
                    f"{label}: 현재 결과는 {value_text}입니다. "
                    f"이 값은 사용자 얼굴에서 {read}에 가까운 신호입니다. 실제 인상은 {effect} 쪽으로 보입니다. "
                    "정면에 가까운 각도와 부드러운 조명에서 다시 촬영하면 이 비율의 장점이 더 선명하게 드러납니다."
                )
            return (
                f"{label}: 현재 사진만으로는 이 항목을 자신 있게 읽기 어렵습니다. "
                "사용자 얼굴의 실제 균형을 더 정확히 보려면 정면에 가까운 각도, 균일한 조명, 덜 기울어진 구도가 필요합니다. "
                "다음 촬영에서는 얼굴이 프레임 중앙에 오도록 맞추면 이 지표의 판단 신뢰도가 올라갑니다."
            )

        label = str(spec["en_label"])
        read = str(spec["en_read"])
        effect = str(spec["en_effect"])
        if has_measured_value:
            return (
                f"Your {label} reads as {value_text} in this result. "
                f"For your face, this points to {read}, creating {effect}. "
                "A near-front camera angle with softer light would make this proportion read even more clearly."
            )
        return (
            f"Your {label} needs a clearer photo before I can give a confident read. "
            "The current image does not provide enough stable visual context for this metric. "
            "Use a front-facing retake with even light and less tilt so this part of your face can be judged more accurately."
        )

    def _estimated_value_text(self, spec: dict[str, object], locale: str) -> str:
        if locale == "ko":
            return "저신뢰 · 재촬영 권장"
        return "Low confidence · retake recommended"

    @staticmethod
    def _estimated_unknown_value_text(locale: str) -> str:
        if locale == "ko":
            return "저신뢰 · 확인 필요"
        return "Low confidence · needs review"

    def _measured_value_text(self, measured: dict[str, object] | None, locale: str) -> str | None:
        if not measured:
            return None
        display_value = self._optional_string(measured.get("display_value"))
        if locale == "ko" and display_value and re.search(r"[가-힣]", display_value):
            return display_value
        if locale != "ko" and display_value:
            return display_value

        numeric_value = self._optional_float(measured.get("numeric_value"))
        if locale == "ko" and numeric_value is not None:
            label_ko = self._optional_string(measured.get("interpretation_label_ko"))
            if label_ko:
                return f"{self._format_metric_value(numeric_value, measured.get('unit'))} · {label_ko}"
            return self._format_metric_value(numeric_value, measured.get("unit"))
        if display_value:
            return display_value

        if numeric_value is None:
            return None
        label = (
            self._optional_string(measured.get("interpretation_label_en"))
            or self._optional_string(measured.get("interpretation_label_ko"))
        )
        if label:
            return f"{numeric_value:.2f} · {label}"
        return f"{numeric_value:.2f}"

    def _format_metric_value(self, numeric_value: float, unit: object) -> str:
        unit_text = self._optional_string(unit)
        value_text = f"{numeric_value:.2f}".rstrip("0").rstrip(".")
        if unit_text in {"degree", "degrees", "deg"}:
            return f"{value_text}°"
        if unit_text in {"percent", "%"}:
            return f"{value_text}%"
        return value_text

    def _face_metric_lookup(self, face_metrics: list[dict[str, object]]) -> dict[str, dict[str, object]]:
        lookup: dict[str, dict[str, object]] = {}
        aliases = {
            "face-width-height-ratio": "face-width-height-ratio",
            "face-depth-width-ratio": "face-depth-width-ratio",
            "structure-symmetry-score": "symmetry",
            "eye-spacing-ratio": "eye-spacing-ratio",
            "canthal-tilt": "canthal-tilt",
            "face-contour-width-height-ratio": "face-contour-width-height-ratio",
        }
        for item in face_metrics:
            if not isinstance(item, dict):
                continue
            metric_id = self._slug(item.get("metric_id"))
            lookup[metric_id] = item
            alias = aliases.get(metric_id)
            if alias:
                lookup[alias] = item
        return lookup
