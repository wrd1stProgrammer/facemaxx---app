from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import FacemaxxBaseModel


ScanSource = Literal["upload", "camera"]
RunStatus = Literal["queued", "processing", "completed", "failed"]
AnalysisModeID = Literal[
    "proportions",
    "aesthetics",
    "glow-up-coach",
    "look-archetype",
    "best-photo-selector",
    "best-angle-finder",
    "dating-profile-score",
    "instagram-profile-score",
]

MULTI_PHOTO_MINIMUMS: dict[str, int] = {
    "best-photo-selector": 3,
    "best-angle-finder": 3,
    "dating-profile-score": 2,
    "instagram-profile-score": 2,
}
MAX_ANALYSIS_PHOTO_IDS = 6


class AnalysisModeOut(FacemaxxBaseModel):
    id: str
    title_key: str
    icon_name: str
    badge_key: str
    badge_type: str
    badge_color: str
    is_highlighted: bool
    sort_order: int
    is_enabled: bool


class CreatePhotoRequest(FacemaxxBaseModel):
    storage_path: str = Field(min_length=1)
    storage_bucket: Optional[str] = None
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    original_filename: Optional[str] = None
    sha256: Optional[str] = None


class PhotoOut(FacemaxxBaseModel):
    id: UUID
    storage_bucket: str
    storage_path: str
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: Optional[str] = None


class CreateAnalysisRunRequest(FacemaxxBaseModel):
    mode_id: AnalysisModeID
    photo_id: Optional[UUID] = None
    photo_ids: Optional[list[UUID]] = None
    face_scan_capture_id: Optional[UUID] = None
    source: ScanSource = "upload"
    onboarding_context: Optional[dict[str, Any]] = None
    locale: Literal[
        "en",
        "ko",
        "ja",
        "de",
        "es-419",
        "zh-Hant",
        "pt-BR",
        "fr",
        "it",
        "id",
        "tr",
        "ar",
    ] = "en"

    @model_validator(mode="after")
    def normalize_photo_ids(self) -> "CreateAnalysisRunRequest":
        deduped: list[UUID] = []
        for photo_id in self.photo_ids or []:
            if photo_id not in deduped:
                deduped.append(photo_id)

        if self.photo_id is None and deduped:
            self.photo_id = deduped[0]
        elif self.photo_id is not None and self.photo_id not in deduped:
            deduped.insert(0, self.photo_id)

        if len(deduped) > MAX_ANALYSIS_PHOTO_IDS:
            raise ValueError(f"photo_ids supports up to {MAX_ANALYSIS_PHOTO_IDS} photos")

        minimum_photo_count = MULTI_PHOTO_MINIMUMS.get(self.mode_id)
        if minimum_photo_count is not None and len(deduped) < minimum_photo_count:
            raise ValueError(f"{self.mode_id} requires at least {minimum_photo_count} photos")

        self.photo_ids = deduped
        return self


FaceCaptureBackend = Literal["arkit_true_depth", "vision_landmarks", "manual_upload"]


class FaceGeometryPayload(FacemaxxBaseModel):
    provider: FaceCaptureBackend = "arkit_true_depth"
    coordinate_space: str = "arkit_local"
    vertices: list[list[float]] = Field(default_factory=list)
    triangle_indices: list[int] = Field(default_factory=list)
    blend_shapes: dict[str, float] = Field(default_factory=dict)
    face_transform: Optional[list[float]] = None
    camera_transform: Optional[list[float]] = None
    camera_intrinsics: Optional[list[float]] = None
    landmarks_2d: Optional[dict[str, list[list[float]]]] = None
    quality: dict[str, Any] = Field(default_factory=dict)
    raw_payload: Optional[dict[str, Any]] = None


class CreateFaceScanCaptureRequest(FacemaxxBaseModel):
    photo_id: Optional[UUID] = None
    source: ScanSource = "camera"
    capture_backend: FaceCaptureBackend = "arkit_true_depth"
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    is_front_camera: bool = True
    is_mirrored: bool = True
    tracking_state: Optional[str] = None
    captured_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    geometry: FaceGeometryPayload


class FaceMetricMeasurement(FacemaxxBaseModel):
    metric_group: str
    metric_id: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    display_value: Optional[str] = None
    interpretation_key: Optional[str] = None
    interpretation_label_en: Optional[str] = None
    interpretation_label_ko: Optional[str] = None
    confidence: Optional[float] = None
    source: str = "geometry"
    metadata: dict[str, Any] = Field(default_factory=dict)


class FaceScanCaptureResponse(FacemaxxBaseModel):
    id: UUID
    photo_id: Optional[UUID] = None
    geometry_saved: bool
    metrics: list[FaceMetricMeasurement] = Field(default_factory=list)


class ScoreRing(FacemaxxBaseModel):
    metric_id: str
    title_key: str
    score: float
    display_value: str
    tint: str
    sort_order: int


class AnalysisMetric(FacemaxxBaseModel):
    section: str
    metric_id: str
    title_key: str
    value_text: Optional[str] = None
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    status_text: Optional[str] = None
    detail_key: Optional[str] = None
    detail_text: Optional[str] = None
    icon_name: str
    value_tint: Optional[str] = None
    sort_order: int


class GrowthOpportunity(FacemaxxBaseModel):
    item_id: str
    title_key: Optional[str] = None
    body_key: Optional[str] = None
    body_text: Optional[str] = None
    category: str
    sort_order: int


class PhotoCandidateRanking(FacemaxxBaseModel):
    candidate_index: int = Field(ge=1)
    rank: int = Field(ge=1)
    score: Optional[float] = None
    verdict: Optional[str] = None
    reason_text: Optional[str] = None


class GlowUpCoachItem(FacemaxxBaseModel):
    section: str
    item_id: str
    title_key: str
    assessment_key: Optional[str] = None
    assessment_text: Optional[str] = None
    action_key: Optional[str] = None
    action_text: Optional[str] = None
    icon_name: str
    is_default_expanded: bool = False
    sort_order: int


class LookArchetypeTrait(FacemaxxBaseModel):
    trait_id: str
    title_key: str
    title_text: Optional[str] = None
    tint: str
    sort_order: int


class LookArchetypeBullet(FacemaxxBaseModel):
    bullet_id: str
    title_key: str
    title_text: Optional[str] = None
    icon_name: str
    sort_order: int


class LookArchetypeSection(FacemaxxBaseModel):
    section_id: str
    title_key: str
    title_text: Optional[str] = None
    icon_name: str
    tint: str
    is_default_expanded: bool
    sort_order: int
    bullets: list[LookArchetypeBullet] = Field(default_factory=list)


class LookArchetypeResult(FacemaxxBaseModel):
    archetype_id: str
    title_key: str
    type_name: str
    secondary_type_name: Optional[str] = None
    subtitle_key: Optional[str] = None
    subtitle_text: Optional[str] = None
    body_key: Optional[str] = None
    body_text: Optional[str] = None
    share_badge_key: Optional[str] = None
    traits: list[LookArchetypeTrait] = Field(default_factory=list)
    sections: list[LookArchetypeSection] = Field(default_factory=list)


class AnalysisResultPayload(FacemaxxBaseModel):
    mode_id: str
    provider: str
    model_name: Optional[str] = None
    overall_score: Optional[float] = None
    overall_progress: Optional[float] = None
    potential_score: Optional[float] = None
    potential_progress: Optional[float] = None
    summary_key: Optional[str] = None
    summary_text: Optional[str] = None
    rings: list[ScoreRing] = Field(default_factory=list)
    metrics: list[AnalysisMetric] = Field(default_factory=list)
    growth_opportunities: list[GrowthOpportunity] = Field(default_factory=list)
    photo_rankings: list[PhotoCandidateRanking] = Field(default_factory=list)
    coach_items: list[GlowUpCoachItem] = Field(default_factory=list)
    look_archetype: Optional[LookArchetypeResult] = None


class AnalysisRunResponse(FacemaxxBaseModel):
    id: UUID
    status: RunStatus
    mode_id: str
    is_free_trial_result: bool = False
    photo_id: Optional[UUID] = None
    photo_ids: list[UUID] = Field(default_factory=list)
    face_scan_capture_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[AnalysisResultPayload] = None


class AnalysisRunSummaryResponse(FacemaxxBaseModel):
    id: UUID
    status: RunStatus
    mode_id: str
    is_free_trial_result: bool = False
    photo_id: Optional[UUID] = None
    photo_ids: list[UUID] = Field(default_factory=list)
    face_scan_capture_id: Optional[UUID] = None
    overall_score: Optional[float] = None
    summary_text: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
