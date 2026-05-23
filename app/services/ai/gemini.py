from __future__ import annotations

import asyncio
import json
import math
import os
import re

from app.core.config import Settings
from app.schemas.analysis import AnalysisResultPayload
from app.services.ai.base import ProviderAnalysisRequest
from app.services.ai.prompt import TITLE_KEYS, build_face_analysis_prompt


class GeminiFaceAnalysisProvider:
    name = "gemini"
    transient_status_codes = {429, 500, 502, 503, 504}

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.gemini_model

    async def analyze(self, request: ProviderAnalysisRequest) -> AnalysisResultPayload:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        from google import genai
        from google.genai import types

        previous_google_api_key = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            client = genai.Client(api_key=self.settings.gemini_api_key)
        finally:
            if previous_google_api_key is not None:
                os.environ["GOOGLE_API_KEY"] = previous_google_api_key
        image_parts = await self._image_parts(request)
        prompt = build_face_analysis_prompt(
            request.mode_id,
            request.locale,
            face_metrics=request.face_metrics,
            photo_count=len(image_parts),
            onboarding_context=request.onboarding_context,
        )
        contents: list[object] = [prompt]

        for index, image_part in enumerate(image_parts, start=1):
            if len(image_parts) > 1:
                contents.append(f"Photo candidate {index}:")
            contents.append(image_part)

        config = types.GenerateContentConfig(
            temperature=0.35,
            response_mime_type="application/json",
        )
        response, used_model_name = await self._generate_content_with_fallback(
            client=client,
            contents=contents,
            config=config,
        )
        data = self._parse_json(response.text or "{}")
        data = self._normalize_payload(data, request, model_name=used_model_name)
        return AnalysisResultPayload.model_validate(data)

    async def _generate_content_with_fallback(self, client, contents: list[object], config):
        attempts_per_model = max(1, self.settings.gemini_retry_attempts)
        model_candidates = self.settings.gemini_model_candidates or [self.model_name]
        last_exc: Exception | None = None

        for model_index, model_name in enumerate(model_candidates):
            for attempt_index in range(attempts_per_model):
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    if model_name != self.model_name:
                        print(
                            "Facemaxx Gemini fallback succeeded:",
                            "primary=",
                            self.model_name,
                            "used=",
                            model_name,
                        )
                    return response, model_name
                except Exception as exc:
                    last_exc = exc
                    is_transient = self._is_transient_model_error(exc)
                    has_more_attempts = attempt_index < attempts_per_model - 1
                    has_fallback_model = model_index < len(model_candidates) - 1
                    if not is_transient or (not has_more_attempts and not has_fallback_model):
                        raise

                    next_model = (
                        model_candidates[model_index + 1]
                        if not has_more_attempts and has_fallback_model
                        else model_name
                    )
                    delay = self._retry_delay_seconds(attempt_index, model_index)
                    print(
                        "Facemaxx Gemini transient failure; retrying:",
                        "model=",
                        model_name,
                        "next_model=",
                        next_model,
                        "attempt=",
                        attempt_index + 1,
                        "status=",
                        self._exception_status_code(exc),
                        "delay=",
                        delay,
                    )
                    await asyncio.sleep(delay)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No Gemini model candidates configured")

    async def _image_parts(self, request: ProviderAnalysisRequest) -> list:
        if request.photos:
            parts = []
            for photo in request.photos:
                image_part = await self._image_part(
                    photo_url=photo.photo_url,
                    photo_bytes=photo.photo_bytes,
                    photo_mime_type=photo.photo_mime_type,
                )
                if image_part is not None:
                    parts.append(image_part)
            return parts

        image_part = await self._image_part(
            photo_url=request.photo_url,
            photo_bytes=request.photo_bytes,
            photo_mime_type=request.photo_mime_type,
        )
        return [image_part] if image_part is not None else []

    async def _image_part(
        self,
        photo_url: str | None,
        photo_bytes: bytes | None,
        photo_mime_type: str | None,
    ):
        from google.genai import types

        if photo_bytes:
            return types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo_mime_type or "image/jpeg",
            )

        if not photo_url:
            return None

        import httpx

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(photo_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
            return types.Part.from_bytes(data=response.content, mime_type=content_type)

    @staticmethod
    def _parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def _normalize_payload(
        self,
        data: dict,
        request: ProviderAnalysisRequest,
        model_name: str | None = None,
    ) -> dict:
        data = data if isinstance(data, dict) else {}
        data["provider"] = self.name
        data["model_name"] = model_name or self.model_name
        data["mode_id"] = request.mode_id
        data["overall_score"] = self._score(data.get("overall_score"))
        data["overall_progress"] = self._progress(data.get("overall_progress"))
        data["potential_score"] = self._score(data.get("potential_score"))
        data["potential_progress"] = self._progress(data.get("potential_progress"))

        data["rings"] = [
            self._normalize_ring(item, request.mode_id, index)
            for index, item in enumerate(self._as_list(data.get("rings")))
            if isinstance(item, dict)
        ]
        data["metrics"] = [
            self._normalize_metric(item, request.mode_id, index, request.locale)
            for index, item in enumerate(self._as_list(data.get("metrics")))
            if isinstance(item, dict)
        ]
        data["growth_opportunities"] = [
            self._normalize_growth_opportunity(item, index, request.locale)
            for index, item in enumerate(self._as_list(data.get("growth_opportunities")))
            if isinstance(item, dict)
        ]
        data["photo_rankings"] = [
            self._normalize_photo_ranking(item, index, len(request.photos or []))
            for index, item in enumerate(self._as_list(data.get("photo_rankings")))
            if isinstance(item, dict)
        ]
        data["coach_items"] = [
            self._normalize_coach_item(item, index, request.locale)
            for index, item in enumerate(self._as_list(data.get("coach_items")))
            if isinstance(item, dict)
        ]

        archetype = data.get("look_archetype")
        data["look_archetype"] = (
            self._normalize_look_archetype(archetype)
            if isinstance(archetype, dict)
            else None
        )
        return data

    @classmethod
    def _is_transient_model_error(cls, exc: Exception) -> bool:
        status_code = cls._exception_status_code(exc)
        if status_code in cls.transient_status_codes:
            return True

        text = str(exc).lower()
        transient_markers = (
            "unavailable",
            "high demand",
            "temporarily",
            "resource_exhausted",
            "deadline",
            "timeout",
            "rate limit",
        )
        return any(marker in text for marker in transient_markers)

    @staticmethod
    def _exception_status_code(exc: Exception) -> int | None:
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        try:
            return int(status_code) if status_code is not None else None
        except (TypeError, ValueError):
            return None

    def _retry_delay_seconds(self, attempt_index: int, model_index: int) -> float:
        base_delay = max(0.1, self.settings.gemini_retry_base_delay_seconds)
        return round(base_delay * (2 ** attempt_index) + (0.25 * model_index), 2)

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
            "tint": item.get("tint") or "#7EF0A1",
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
        if self._is_score_metric(mode_id, section, item):
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
            "value_tint": item.get("value_tint") or "#34D15C",
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
        if score is not None and score > 10:
            score = score / 10

        return {
            "candidate_index": candidate_index,
            "rank": rank,
            "score": score,
            "verdict": self._optional_string(item.get("verdict") or item.get("status_text") or item.get("value_text")),
            "reason_text": self._optional_string(item.get("reason_text") or item.get("reason") or item.get("detail_text")),
        }

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

    @staticmethod
    def _as_list(value: object) -> list:
        return value if isinstance(value, list) else []

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

    @staticmethod
    def _default_metric_section(mode_id: str) -> str:
        if mode_id == "proportions":
            return "proportions"
        if mode_id == "aesthetics":
            return "detailed_metrics"
        if mode_id == "best-photo-selector":
            return "photo_selection"
        if mode_id == "best-angle-finder":
            return "angle_breakdown"
        if mode_id == "dating-profile-score":
            return "dating_profile"
        if mode_id == "instagram-profile-score":
            return "instagram_profile"
        return "facial_analysis"

    @staticmethod
    def _default_icon(metric_id: str) -> str:
        if "eye" in metric_id:
            return "eye.fill"
        if "skin" in metric_id:
            return "drop.fill"
        if "jaw" in metric_id:
            return "triangle.fill"
        if "hair" in metric_id:
            return "comb.fill"
        if "symmetry" in metric_id:
            return "circle.lefthalf.filled"
        if "lip" in metric_id or "mouth" in metric_id:
            return "mouth.fill"
        if "confidence" in metric_id:
            return "heart.fill"
        if "photo" in metric_id or "composition" in metric_id or "crop" in metric_id:
            return "camera.fill"
        if "angle" in metric_id:
            return "viewfinder"
        if "lighting" in metric_id:
            return "sun.max.fill"
        if "background" in metric_id:
            return "rectangle.dashed"
        if "trust" in metric_id or "readiness" in metric_id:
            return "checkmark.seal.fill"
        if "instagram" in metric_id or "feed" in metric_id:
            return "square.grid.3x3.fill"
        return "face.smiling"

    @classmethod
    def _safe_icon_name(cls, value: object, metric_id: str) -> str:
        icon_name = cls._optional_string(value)
        aliases = {
            "bolt.heart.fill": "bolt.fill",
            "camera.viewfinder": "viewfinder",
            "checkmark.shield.fill": "checkmark.seal.fill",
            "circle.grid.cross.fill": "circle.grid.3x3.fill",
            "quote.bubble.fill": "text.bubble.fill",
            "shield.checkmark.fill": "checkmark.seal.fill",
        }
        if icon_name in aliases:
            return aliases[icon_name]
        safe_icons = {
            "arrow.left.and.right.circle",
            "arrow.turn.up.left",
            "arrow.turn.up.right",
            "bolt.fill",
            "bubble.left.and.bubble.right.fill",
            "calendar",
            "camera.fill",
            "checkmark.seal.fill",
            "circle.grid.3x3.fill",
            "circle.lefthalf.filled",
            "comb.fill",
            "crop",
            "drop.fill",
            "exclamationmark.triangle.fill",
            "eye.circle.fill",
            "eye.fill",
            "eyeglasses",
            "face.smiling",
            "heart.fill",
            "mouth.fill",
            "mustache.fill",
            "person.crop.square.fill",
            "rectangle.dashed",
            "rectangle.fill",
            "rectangle.portrait",
            "rectangle.stack.fill",
            "slider.horizontal.3",
            "sparkles",
            "square.grid.3x3.fill",
            "star.fill",
            "sun.max.fill",
            "text.bubble.fill",
            "triangle.fill",
            "viewfinder",
            "wand.and.stars",
            "xmark.circle.fill",
            "xmark.octagon.fill",
        }
        if icon_name in safe_icons:
            return icon_name
        return cls._default_icon(metric_id)

    @staticmethod
    def _fallback_metric_detail(metric_id: str, value_text: str | None, status_text: str | None, locale: str) -> str:
        value_part = value_text or status_text or "this result"
        if locale == "ko":
            return (
                f"{value_part}는 현재 얼굴 스캔과 사진 맥락을 바탕으로 해석한 결과입니다. "
                f"{metric_id.replace('-', ' ')} 판독은 이 요소가 전체 인상에 어떤 영향을 주는지 설명합니다. "
                "정면에 가까운 밝은 사진으로 다시 비교하면 변화가 더 안정적으로 보입니다."
            )
        return (
            f"{value_part} is interpreted from the current face scan and photo. "
            f"The {metric_id.replace('-', ' ')} reading helps explain how this feature affects the overall impression. "
            "Use a centered, well-lit retake to compare changes more reliably."
        )

    @staticmethod
    def _fallback_growth_body(locale: str) -> str:
        if locale == "ko":
            return "밝은 정면 사진으로 다시 촬영한 뒤 다음 스캔과 비교하면 개선 방향을 더 정확히 확인할 수 있습니다."
        return "Use a centered, well-lit photo and compare future scans to confirm the improvement."

    @staticmethod
    def _fallback_coach_assessment(locale: str) -> str:
        if locale == "ko":
            return "평가: 현재 얼굴 스캔에서 이 요소는 비교적 명확하게 읽힙니다."
        return "Assessment: This feature reads clearly from the current face scan."

    @staticmethod
    def _fallback_coach_action(locale: str) -> str:
        if locale == "ko":
            return "플랜: 균일한 조명에서 다시 촬영하고 다음 스캔과 비교한 뒤 루틴을 조정하세요."
        return "Plan: Retake in even light and compare future scans before changing your routine."
