from __future__ import annotations

import asyncio
import os

from app.core.config import Settings
from app.schemas.analysis import AnalysisResultPayload
from app.services.ai.base import ProviderAnalysisRequest
from app.services.ai.payload_normalizer import FaceAnalysisPayloadNormalizer
from app.services.ai.prompt import build_face_analysis_prompt


class GeminiFaceAnalysisProvider(FaceAnalysisPayloadNormalizer):
    name = "gemini"
    transient_status_codes = {429, 500, 502, 503, 504}

    def __init__(self, settings: Settings):
        super().__init__(provider_name=self.name, model_name=settings.gemini_model)
        self.settings = settings

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
        if request.mode_id == "proportions":
            data = await self._repair_proportions_payload_if_needed(
                client=client,
                image_parts=image_parts,
                request=request,
                config=config,
                data=data,
            )
        data = self._normalize_payload(data, request, model_name=used_model_name)
        return AnalysisResultPayload.model_validate(data)

    async def _repair_proportions_payload_if_needed(
        self,
        client,
        image_parts: list[object],
        request: ProviderAnalysisRequest,
        config,
        data: dict,
    ) -> dict:
        missing_ids = self._proportions_missing_metric_ids(data)
        placeholder_count = self._proportions_placeholder_metric_count(data)
        if not missing_ids and placeholder_count == 0:
            return data

        repair_prompt = build_face_analysis_prompt(
            request.mode_id,
            request.locale,
            face_metrics=request.face_metrics,
            photo_count=len(image_parts),
            onboarding_context=request.onboarding_context,
        )
        repair_prompt += (
            "\n\nCRITICAL REPAIR PASS:\n"
            f"- The previous proportions response omitted these required metric_id values: {', '.join(missing_ids)}.\n"
            f"- It also contained {placeholder_count} generic placeholder metric value(s).\n"
            "- Return one complete JSON object for the same photo, including every required proportions metric_id.\n"
            "- Do not output generic placeholder values such as \"Photo estimate\", \"a balanced overall outline\", "
            "\"eyes that anchor\", or other metric-definition text as value_text.\n"
            "- value_text must be a compact actual read from the user's photo, for example "
            "\"Oval · soft outline\", \"Slight negative · calmer eye line\", or \"1.58 · broader frame\".\n"
            "- detail_text must explain the visible read for this user's face/photo, not what the metric means.\n"
        )

        repair_contents: list[object] = [repair_prompt]
        for index, image_part in enumerate(image_parts, start=1):
            if len(image_parts) > 1:
                repair_contents.append(f"Photo candidate {index}:")
            repair_contents.append(image_part)

        try:
            repair_response, _ = await self._generate_content_with_fallback(
                client=client,
                contents=repair_contents,
                config=config,
            )
            repaired_data = self._parse_json(repair_response.text or "{}")
        except Exception as exc:
            print("Facemaxx Gemini proportions repair failed:", repr(exc))
            return data

        repaired_missing_count = len(self._proportions_missing_metric_ids(repaired_data))
        repaired_placeholder_count = self._proportions_placeholder_metric_count(repaired_data)
        if (
            repaired_missing_count < len(missing_ids)
            or repaired_placeholder_count < placeholder_count
        ):
            return repaired_data
        return data

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
