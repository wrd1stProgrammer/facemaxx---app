from __future__ import annotations

from app.services.ai.prompt import TITLE_KEYS


class FaceAnalysisPayloadLookMixin:
    def _normalize_coach_item(self, item: dict, index: int, locale: str) -> dict:
        item_id = self._slug(item.get("item_id") or item.get("id") or item.get("title") or f"coach-{index + 1}")
        proposed_title_key = self._optional_string(item.get("title_key"))
        item_id = self._coach_item_id(item_id, proposed_title_key)
        section = str(item.get("section") or "facial_analysis")
        if section not in {"facial_analysis", "needs_work", "strengths"}:
            section = "facial_analysis"
        return {
            "section": section,
            "item_id": item_id,
            "title_key": self._coach_title_key(item_id, proposed_title_key),
            "assessment_text": self._optional_string(item.get("assessment_text") or item.get("assessment")) or self._fallback_coach_assessment(locale),
            "action_text": self._optional_string(item.get("action_text") or item.get("action") or item.get("plan_text")) or self._fallback_coach_action(locale),
            "icon_name": item.get("icon_name") or self._default_icon(item_id),
            "is_default_expanded": bool(item.get("is_default_expanded", False)),
            "sort_order": self._int(item.get("sort_order"), (index + 1) * 10),
        }

    def _coach_item_id(self, item_id: str, proposed_title_key: str | None) -> str:
        if item_id in TITLE_KEYS["coach"]:
            return item_id

        if proposed_title_key:
            for known_id, known_title_key in TITLE_KEYS["coach"].items():
                if proposed_title_key == known_title_key:
                    return known_id

        return item_id

    def _coach_title_key(self, item_id: str, proposed_title_key: str | None) -> str:
        known_key = TITLE_KEYS["coach"].get(item_id)
        if known_key:
            return known_key

        allowed_keys = set(TITLE_KEYS["coach"].values())
        if proposed_title_key in allowed_keys:
            return proposed_title_key

        return "analysis.glowUpCoach.item.glow"

    def _normalize_look_archetype(self, item: dict) -> dict:
        archetype_id = self._slug(item.get("archetype_id") or item.get("type_name") or "clean-cut-heartthrob")
        traits = [
            self._normalize_trait(trait, index)
            for index, trait in enumerate(self._as_list(item.get("traits")))
            if isinstance(trait, dict)
        ]
        sections = [
            self._normalize_archetype_section(section, index)
            for index, section in enumerate(self._as_list(item.get("sections")))
            if isinstance(section, dict)
        ]
        return {
            "archetype_id": archetype_id,
            "title_key": item.get("title_key") or "analysis.lookArchetype.title",
            "type_name": str(item.get("type_name") or "Clean-cut Heartthrob"),
            "secondary_type_name": self._optional_string(item.get("secondary_type_name") or item.get("secondary_type")),
            "subtitle_key": self._optional_string(item.get("subtitle_key")),
            "subtitle_text": self._optional_string(item.get("subtitle_text")),
            "body_key": self._optional_string(item.get("body_key")),
            "body_text": self._optional_string(item.get("body_text")),
            "share_badge_key": item.get("share_badge_key") or "analysis.lookArchetype.shareReady",
            "traits": traits,
            "sections": sections,
        }

    def _normalize_trait(self, item: dict, index: int) -> dict:
        trait_id = self._slug(item.get("trait_id") or item.get("title") or f"trait-{index + 1}")
        return {
            "trait_id": trait_id,
            "title_key": item.get("title_key") or f"analysis.lookArchetype.trait.{trait_id}",
            "title_text": self._optional_string(item.get("title_text") or item.get("title")),
            "tint": item.get("tint") or "#34D15C",
            "sort_order": self._int(item.get("sort_order"), (index + 1) * 10),
        }

    def _normalize_archetype_section(self, item: dict, index: int) -> dict:
        section_id = self._slug(item.get("section_id") or item.get("title") or f"section-{index + 1}")
        bullets = [
            self._normalize_archetype_bullet(bullet, bullet_index)
            for bullet_index, bullet in enumerate(self._as_list(item.get("bullets")))
            if isinstance(bullet, dict)
        ]
        return {
            "section_id": section_id,
            "title_key": item.get("title_key") or f"analysis.lookArchetype.{section_id}",
            "title_text": self._optional_string(item.get("title_text") or item.get("title")),
            "icon_name": item.get("icon_name") or "checkmark.seal.fill",
            "tint": item.get("tint") or "#34D15C",
            "is_default_expanded": bool(item.get("is_default_expanded", index == 0)),
            "sort_order": self._int(item.get("sort_order"), (index + 1) * 10),
            "bullets": bullets,
        }

    def _normalize_archetype_bullet(self, item: dict, index: int) -> dict:
        bullet_id = self._slug(item.get("bullet_id") or item.get("title") or f"bullet-{index + 1}")
        return {
            "bullet_id": bullet_id,
            "title_key": item.get("title_key") or f"analysis.lookArchetype.bullet.{bullet_id}",
            "title_text": self._optional_string(item.get("title_text") or item.get("title")) or "A clear supporting feature from this scan.",
            "icon_name": item.get("icon_name") or "checkmark.circle.fill",
            "sort_order": self._int(item.get("sort_order"), (index + 1) * 10),
        }
