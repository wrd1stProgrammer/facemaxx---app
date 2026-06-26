from __future__ import annotations

import base64
from typing import TypeAlias

from app.core.config import Settings
from app.schemas.analysis import AnalysisResultPayload
from app.services.ai.base import ProviderAnalysisRequest
from app.services.ai.payload_normalizer import FaceAnalysisPayloadNormalizer
from app.services.ai.prompt import build_face_analysis_prompt

JsonValue: TypeAlias = str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]


class OpenAIFaceAnalysisProvider:
    name = "openai"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.openai_model

    async def analyze(self, request: ProviderAnalysisRequest) -> AnalysisResultPayload:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        prompt = build_face_analysis_prompt(
            request.mode_id,
            request.locale,
            face_metrics=request.face_metrics,
            photo_count=len(request.photos or []) or (1 if request.photo_id else 0),
            onboarding_context=request.onboarding_context,
        )
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
    return {
        "format": {
            "type": "json_schema",
            "name": "AnalysisResultPayload",
            "schema": AnalysisResultPayload.model_json_schema(),
            "strict": False,
        }
    }
