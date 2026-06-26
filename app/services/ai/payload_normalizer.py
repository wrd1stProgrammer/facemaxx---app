from __future__ import annotations

import json
import re

from app.services.ai.base import ProviderAnalysisRequest
from app.services.ai.payload_normalizer_data import FaceAnalysisPayloadDataMixin
from app.services.ai.payload_normalizer_fallbacks import FaceAnalysisPayloadFallbackMixin
from app.services.ai.payload_normalizer_icons import FaceAnalysisPayloadIconMixin
from app.services.ai.payload_normalizer_look import FaceAnalysisPayloadLookMixin
from app.services.ai.payload_normalizer_metrics import FaceAnalysisPayloadMetricsMixin
from app.services.ai.payload_normalizer_proportions import FaceAnalysisPayloadProportionsMixin
from app.services.ai.payload_normalizer_values import FaceAnalysisPayloadValueMixin


class FaceAnalysisPayloadNormalizer(
    FaceAnalysisPayloadDataMixin,
    FaceAnalysisPayloadProportionsMixin,
    FaceAnalysisPayloadMetricsMixin,
    FaceAnalysisPayloadLookMixin,
    FaceAnalysisPayloadValueMixin,
    FaceAnalysisPayloadIconMixin,
    FaceAnalysisPayloadFallbackMixin,
):
    def __init__(self, provider_name: str, model_name: str | None) -> None:
        self.name = provider_name
        self.model_name = model_name

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
        if request.mode_id == "proportions":
            self._ensure_proportions_metrics(data, request)
            self._sanitize_proportions_template_metrics(data, request)
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
        if request.mode_id in self.photo_optimization_mode_ids:
            self._calibrate_photo_optimization_payload(data)
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
