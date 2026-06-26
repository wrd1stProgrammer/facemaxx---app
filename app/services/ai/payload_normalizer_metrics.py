from __future__ import annotations

from app.services.ai.prompt import TITLE_KEYS


class FaceAnalysisPayloadMetricsMixin:
    def _normalize_ring(self, item: dict, mode_id: str, index: int) -> dict:
        metric_id = self._slug(item.get("metric_id") or item.get("id") or item.get("title") or f"ring-{index + 1}")
        score = self._float(item.get("score"), 0.0)
        if score > 10:
            score = score / 100
        elif score > 1:
            score = score / 10
        score = min(max(score, 0), 1)
        return {
            "metric_id": metric_id,
            "title_key": self._ring_title_key(item, mode_id, metric_id),
            "score": score,
            "display_value": self._score_display_value(item.get("display_value"), score),
            "tint": item.get("tint") or self._score_tint(score),
            "sort_order": self._int(item.get("sort_order"), (index + 1) * 10),
        }

    @staticmethod
    def _ring_title_key(item: dict, mode_id: str, metric_id: str) -> str:
        known_keys = set(TITLE_KEYS["rings"].values())
        proposed_key = str(item.get("title_key") or "").strip()
        if proposed_key in known_keys:
            return proposed_key

        return TITLE_KEYS["rings"].get(metric_id, "analysis.results.ring.harmony")

    def _normalize_metric(self, item: dict, mode_id: str, index: int, locale: str) -> dict:
        section = str(item.get("section") or self._default_metric_section(mode_id))
        metric_id = self._slug(item.get("metric_id") or item.get("id") or item.get("title") or f"metric-{index + 1}")
        title_group = self._metric_title_group(mode_id)
        title_key = self._metric_title_key(item, title_group, metric_id)
        value_text = self._optional_string(item.get("value_text") or item.get("display_value") or item.get("value"))
        status_text = self._optional_string(item.get("status_text") or item.get("interpretation"))
        detail_text = self._optional_string(item.get("detail_text") or item.get("description") or item.get("body_text"))
        if not detail_text:
            detail_text = self._fallback_metric_detail(metric_id, value_text, status_text, locale)
        numeric_value = self._optional_float(item.get("numeric_value"))
        is_score_metric = self._is_score_metric(mode_id, section, item)
        if is_score_metric:
            value_text = self._normalize_score_value_text(value_text)
            if numeric_value is not None and 0 < numeric_value <= 1:
                numeric_value = round(numeric_value * 10, 2)
        return {
            "section": section,
            "metric_id": metric_id,
            "title_key": title_key,
            "value_text": value_text,
            "numeric_value": numeric_value,
            "unit": self._optional_string(item.get("unit")),
            "status_text": status_text,
            "detail_text": detail_text,
            "icon_name": self._safe_icon_name(item.get("icon_name"), metric_id),
            "value_tint": item.get("value_tint") or self._metric_tint(numeric_value if is_score_metric else None),
            "sort_order": self._int(item.get("sort_order"), (index + 1) * 10),
        }

    def _metric_title_key(self, item: dict, title_group: str, metric_id: str) -> str:
        known_key = TITLE_KEYS[title_group].get(metric_id)
        if known_key:
            return known_key

        proposed_key = self._optional_string(item.get("title_key"))
        allowed_keys = {
            title_key
            for group in TITLE_KEYS.values()
            for title_key in group.values()
        }
        if proposed_key in allowed_keys:
            return proposed_key

        return "analysis.results.metric.symmetry"

    def _normalize_growth_opportunity(self, item: dict, index: int, locale: str) -> dict:
        item_id = self._slug(item.get("item_id") or item.get("id") or item.get("title") or f"opportunity-{index + 1}")
        return {
            "item_id": item_id,
            "title_key": self._optional_string(item.get("title_key")),
            "body_key": self._optional_string(item.get("body_key")),
            "body_text": self._optional_string(item.get("body_text") or item.get("description")) or self._fallback_growth_body(locale),
            "category": str(item.get("category") or item_id),
            "sort_order": self._int(item.get("sort_order"), (index + 1) * 10),
        }

    def _normalize_photo_ranking(self, item: dict, index: int, photo_count: int) -> dict:
        candidate_index = self._int(
            item.get("candidate_index") or item.get("candidate") or item.get("photo_index"),
            index + 1,
        )
        if photo_count > 0:
            candidate_index = min(max(candidate_index, 1), photo_count)

        rank = self._int(item.get("rank"), index + 1)
        if photo_count > 0:
            rank = min(max(rank, 1), photo_count)

        score = self._optional_float(item.get("score") or item.get("numeric_value"))
        if score is not None:
            if 0 < score <= 1:
                score = score * 10
            elif score > 10:
                score = score / 10
            score = round(min(max(score, 0), 10), 2)

        return {
            "candidate_index": candidate_index,
            "rank": rank,
            "score": score,
            "verdict": self._optional_string(item.get("verdict") or item.get("status_text") or item.get("value_text")),
            "reason_text": self._optional_string(item.get("reason_text") or item.get("reason") or item.get("detail_text")),
            "description_text": self._optional_string(item.get("description_text") or item.get("photo_description") or item.get("description")),
            "best_use_text": self._optional_string(item.get("best_use_text") or item.get("best_use") or item.get("use_case")),
            "fun_label_text": self._optional_string(item.get("fun_label_text") or item.get("fun_label") or item.get("vibe_label")),
            "strengths": self._string_list(item.get("strengths") or item.get("strong_points")),
            "weakness_text": self._optional_string(item.get("weakness_text") or item.get("weakness") or item.get("risk_text")),
            "fix_text": self._optional_string(item.get("fix_text") or item.get("quick_fix") or item.get("retake_tip")),
            "caption_idea_text": self._optional_string(item.get("caption_idea_text") or item.get("caption_idea") or item.get("prompt_text")),
            "vibe_tags": self._string_list(item.get("vibe_tags") or item.get("tags")),
        }

    def _calibrate_photo_optimization_payload(self, data: dict) -> None:
        rankings = [
            item
            for item in self._as_list(data.get("photo_rankings"))
            if isinstance(item, dict) and item.get("score") is not None
        ]
        if len(rankings) < 2:
            return

        score_values = [
            self._float(item.get("score"), 0.0)
            for item in rankings
        ]
        score_spread = max(score_values) - min(score_values)
        all_high = min(score_values) >= 8.3
        too_flat = score_spread < 0.45
        if not all_high and not too_flat:
            return

        ordered_rankings = sorted(
            rankings,
            key=lambda item: (
                self._int(item.get("rank"), 999),
                self._int(item.get("candidate_index"), 999),
            ),
        )
        top_score = self._float(ordered_rankings[0].get("score"), max(score_values))
        top_score = min(max(top_score, 7.2), 8.8 if all_high else 9.2)
        gap = 0.55 if all_high else 0.38
        for offset, item in enumerate(ordered_rankings):
            adjusted_score = top_score - (gap * offset) - (0.10 * max(offset - 1, 0))
            item["score"] = round(min(max(adjusted_score, 5.2), 10.0), 1)

        if data.get("overall_score") is not None:
            average_score = sum(item["score"] for item in ordered_rankings) / len(ordered_rankings)
            ceiling = min(ordered_rankings[0]["score"], average_score + 0.65)
            data["overall_score"] = round(min(self._score(data.get("overall_score")) or ceiling, ceiling), 1)
            data["overall_progress"] = round(data["overall_score"] / 10, 4)

        if data.get("potential_score") is not None and data.get("overall_score") is not None:
            potential_score = self._score(data.get("potential_score"))
            if potential_score is not None:
                ceiling = min(10.0, data["overall_score"] + 0.9)
                floor = min(10.0, data["overall_score"] + 0.4)
                data["potential_score"] = round(min(max(potential_score, floor), ceiling), 1)
                data["potential_progress"] = round(data["potential_score"] / 10, 4)
