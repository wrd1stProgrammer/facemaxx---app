from __future__ import annotations

import base64
from typing import TypeAlias
from functools import lru_cache

from app.core.config import Settings
from app.schemas.analysis import AnalysisResultPayload
from app.services.ai.base import ProviderAnalysisRequest
from app.services.ai.payload_normalizer import FaceAnalysisPayloadNormalizer
from app.services.ai.prompt import ANALYSIS_JSON_CONTRACT, build_face_analysis_prompt

JsonValue: TypeAlias = str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]


@lru_cache(maxsize=1)
def _shared_client():
    from openai import AsyncOpenAI
    from app.core.config import get_settings

    return AsyncOpenAI(api_key=get_settings().openai_api_key)


async def close_face_analysis_client() -> None:
    if _shared_client.cache_info().currsize:
        client = _shared_client()
        _shared_client.cache_clear()
        await client.close()


class OpenAIFaceAnalysisProvider:
    name = "openai"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.openai_model

    async def analyze(self, request: ProviderAnalysisRequest) -> AnalysisResultPayload:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        client = _shared_client()
        prompt = build_face_analysis_prompt(
            request.mode_id,
            request.locale,
            face_metrics=request.face_metrics,
            photo_count=len(request.photos or []) or (1 if request.photo_id else 0),
            onboarding_context=request.onboarding_context,
        )
        # The response schema already describes the wire format. Preserve the
        # contract's content guidance while removing its duplicate JSON example.
        content_guidance = "For every photo_rankings" + ANALYSIS_JSON_CONTRACT.split("\nFor every photo_rankings", 1)[1]
        prompt = prompt.replace(ANALYSIS_JSON_CONTRACT, content_guidance)
        prompt += """
Transport instructions: return compact JSON matching the supplied response schema.
Preserve all requested analysis items, personalized observations and full explanation depth.
For rings, metrics and coach_items, omit title_key, icon_name and sort_order:
the server restores these from metric_id/item_id and array order. Use the exact known
metric_id/item_id values and keep the intended display order. Do not omit or shorten
detail_text, assessment_text, action_text or summary_text to save tokens.
Do not emit mode_id, provider or model_name; the server supplies them.
Other fields, including meaningful colors, scores and custom archetype titles, are unchanged.
"""
        content: list[dict[str, JsonValue]] = [{"type": "input_text", "text": prompt}]
        photos = request.photos or []
        if not photos and (request.photo_bytes or request.photo_url):
            from app.services.ai.base import ProviderPhotoInput

            photos = [
                ProviderPhotoInput(
                    photo_id=request.photo_id,
                    photo_url=request.photo_url,
                    photo_bytes=request.photo_bytes,
                    photo_mime_type=request.photo_mime_type,
                )
            ] if request.photo_id else []

        for index, photo in enumerate(photos, start=1):
            if len(photos) > 1:
                content.append({"type": "input_text", "text": f"Photo candidate {index}:"})
            image_url = self._image_url(photo.photo_url, photo.photo_bytes, photo.photo_mime_type)
            if image_url:
                content.append({"type": "input_image", "image_url": image_url})

        response = await client.responses.create(
            model=self.model_name,
            input=[{"role": "user", "content": content}],
            text=_response_text_format(),
            reasoning={"effort": "low"},
        )
        normalizer = FaceAnalysisPayloadNormalizer(provider_name=self.name, model_name=self.model_name)
        data = normalizer._parse_json(response.output_text or "{}")
        data = normalizer._normalize_payload(data, request)
        return AnalysisResultPayload.model_validate(data)

    @staticmethod
    def _image_url(photo_url: str | None, photo_bytes: bytes | None, photo_mime_type: str | None) -> str | None:
        if photo_bytes:
            encoded = base64.b64encode(photo_bytes).decode("ascii")
            return f"data:{photo_mime_type or 'image/jpeg'};base64,{encoded}"
        return photo_url


def _response_text_format() -> dict[str, JsonValue]:
    schema = AnalysisResultPayload.model_json_schema()
    def omit(node, fields):
        for field in fields:
            node.get("properties", {}).pop(field, None)
        if "required" in node:
            node["required"] = [field for field in node["required"] if field not in fields]
    omit(schema, {"mode_id", "provider", "model_name"})
    for name in ("ScoreRing", "AnalysisMetric", "GlowUpCoachItem"):
        omit(schema["$defs"][name], {"title_key", "icon_name", "sort_order"})
    return {
        "format": {
            "type": "json_schema",
            "name": "AnalysisResultPayload",
            "schema": schema,
            "strict": False,
        }
    }
