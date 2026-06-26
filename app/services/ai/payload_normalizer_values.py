from __future__ import annotations

import math
import re


class FaceAnalysisPayloadValueMixin:
    @staticmethod
    def _as_list(value: object) -> list:
        return value if isinstance(value, list) else []

    @classmethod
    def _string_list(cls, value: object) -> list[str]:
        if isinstance(value, list):
            return [
                text
                for item in value
                if (text := cls._optional_string(item))
            ][:5]
        text = cls._optional_string(value)
        if not text:
            return []
        return [
            item.strip()
            for item in re.split(r"[,/|]", text)
            if item.strip()
        ][:5]

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _float(value: object, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    @classmethod
    def _optional_float(cls, value: object) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _score_tint(score: float) -> str:
        return "#FFB020" if score < 0.75 else "#7EF0A1"

    @staticmethod
    def _metric_tint(value: float | None) -> str:
        return "#FFB020" if value is not None and value < 7.5 else "#34D15C"

    @classmethod
    def _score(cls, value: object) -> float | None:
        number = cls._optional_float(value)
        if number is None:
            return None
        if 0 <= number <= 1:
            return round(number * 10, 2)
        if 10 < number <= 100:
            return round(number / 10, 2)
        return round(min(max(number, 0), 10), 2)

    @classmethod
    def _score_display_value(cls, raw_value: object, normalized_score: float) -> str:
        number = cls._optional_float(raw_value)
        if number is not None:
            return cls._score_text(cls._visible_score(number))

        text = cls._optional_string(raw_value)
        if text:
            return text
        return cls._score_text(normalized_score * 10)

    @classmethod
    def _normalize_score_value_text(cls, value_text: str | None) -> str | None:
        if not value_text:
            return value_text

        match = re.match(r"^\s*([0-9]+(?:[\.,][0-9]+)?)(.*)$", value_text)
        if not match:
            return value_text

        suffix = match.group(2)
        if suffix and not (
            suffix[0].isspace()
            or suffix.startswith("·")
            or suffix.startswith("/")
            or suffix.startswith("점")
        ):
            return value_text

        try:
            number = float(match.group(1).replace(",", "."))
        except ValueError:
            return value_text

        if not 0 < number <= 1:
            if 10 < number <= 100:
                return f"{cls._score_text(number / 10)}{suffix}"
            return value_text
        return f"{cls._score_text(number * 10)}{suffix}"

    @staticmethod
    def _visible_score(score: float) -> float:
        if 0 <= score <= 1:
            return score * 10
        if 10 < score <= 100:
            return score / 10
        return score

    @staticmethod
    def _score_text(score: float) -> str:
        return f"{min(max(score, 0), 10):.1f}"

    @classmethod
    def _is_score_metric(cls, mode_id: str, section: str, item: dict) -> bool:
        unit = cls._optional_string(item.get("unit"))
        if unit and unit.lower() in {"score", "점수"}:
            return True

        score_sections = {
            "photo_selection",
            "improvement_plan",
            "angle_breakdown",
            "capture_plan",
            "dating_profile",
            "profile_plan",
            "instagram_profile",
            "content_plan",
        }
        return mode_id in {
            "best-photo-selector",
            "best-angle-finder",
            "dating-profile-score",
            "instagram-profile-score",
        } and section in score_sections

    @classmethod
    def _progress(cls, value: object) -> float | None:
        number = cls._optional_float(value)
        if number is None:
            return None
        if number > 10:
            number = number / 100
        elif number > 1:
            number = number / 10
        return round(min(max(number, 0), 1), 4)

    @staticmethod
    def _int(value: object, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _slug(value: object) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[^a-z0-9가-힣]+", "-", text).strip("-")
        return text or "item"

    @staticmethod
    def _metric_title_group(mode_id: str) -> str:
        if mode_id == "proportions":
            return "proportions"
        if mode_id in {
            "best-photo-selector",
            "best-angle-finder",
            "dating-profile-score",
            "instagram-profile-score",
        }:
            return "photo_optimization"
        return "aesthetics"
