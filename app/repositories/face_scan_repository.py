from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from app.db.supabase import get_supabase_service_client
from app.schemas.analysis import (
    CreateFaceScanCaptureRequest,
    FaceMetricMeasurement,
    FaceScanCaptureResponse,
)
from app.services.analysis.face_metric_calculator import calculate_face_metrics


class FaceScanRepository:
    def create_capture(
        self,
        user_id: str | None,
        request: CreateFaceScanCaptureRequest,
        client_install_id: str | None = None,
    ) -> FaceScanCaptureResponse:
        capture_id = uuid4()
        metrics = calculate_face_metrics(request.geometry)
        captured_at = request.captured_at or datetime.now(timezone.utc)
        quality_score = self._quality_score(request, metrics)

        capture_payload = {
            "id": str(capture_id),
            "user_id": user_id,
            "client_install_id": client_install_id,
            "photo_id": str(request.photo_id) if request.photo_id else None,
            "source": request.source,
            "capture_backend": request.capture_backend,
            "device_model": request.device_model,
            "os_version": request.os_version,
            "app_version": request.app_version,
            "image_width": request.image_width,
            "image_height": request.image_height,
            "is_front_camera": request.is_front_camera,
            "is_mirrored": request.is_mirrored,
            "tracking_state": request.tracking_state,
            "quality_score": quality_score,
            "metadata": request.metadata,
            "captured_at": captured_at.isoformat(),
        }

        geometry_payload = {
            "capture_id": str(capture_id),
            "provider": request.geometry.provider,
            "coordinate_space": request.geometry.coordinate_space,
            "vertex_count": len(request.geometry.vertices),
            "triangle_count": len(request.geometry.triangle_indices) // 3,
            "vertices": request.geometry.vertices,
            "triangle_indices": request.geometry.triangle_indices,
            "blend_shapes": request.geometry.blend_shapes,
            "face_transform": request.geometry.face_transform,
            "camera_transform": request.geometry.camera_transform,
            "camera_intrinsics": request.geometry.camera_intrinsics,
            "landmarks_2d": request.geometry.landmarks_2d,
            "quality": request.geometry.quality,
            "raw_payload": request.geometry.raw_payload,
        }

        supabase = get_supabase_service_client()
        if supabase is None:
            return FaceScanCaptureResponse(
                id=capture_id,
                photo_id=request.photo_id,
                geometry_saved=False,
                metrics=metrics,
            )

        try:
            supabase.table("face_scan_captures").insert(capture_payload).execute()
            supabase.table("face_geometry_snapshots").insert(geometry_payload).execute()

            if metrics:
                supabase.table("face_metric_measurements").insert([
                    self._metric_payload(capture_id, metric) for metric in metrics
                ]).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to save face scan capture",
            ) from exc

        return FaceScanCaptureResponse(
            id=capture_id,
            photo_id=request.photo_id,
            geometry_saved=True,
            metrics=metrics,
        )

    @staticmethod
    def _metric_payload(capture_id, metric: FaceMetricMeasurement) -> dict:
        payload = metric.model_dump(mode="json")
        payload["capture_id"] = str(capture_id)
        return payload

    def get_capture_metrics(self, capture_id) -> list[dict]:
        supabase = get_supabase_service_client()
        if supabase is None:
            return []

        metrics = []
        try:
            response = (
                supabase.table("face_metric_measurements")
                .select(
                    "metric_group,metric_id,numeric_value,unit,display_value,"
                    "interpretation_label_en,interpretation_label_ko,confidence,source,metadata"
                )
                .eq("capture_id", str(capture_id))
                .execute()
            )
            metrics = response.data or []
        except Exception:
            metrics = []

        geometry_context = self._capture_geometry_context(capture_id)
        if geometry_context:
            metrics.append(geometry_context)
        return metrics

    def _capture_geometry_context(self, capture_id) -> dict | None:
        supabase = get_supabase_service_client()
        if supabase is None:
            return None

        try:
            response = (
                supabase.table("face_geometry_snapshots")
                .select("provider,coordinate_space,vertex_count,triangle_count,quality")
                .eq("capture_id", str(capture_id))
                .limit(1)
                .execute()
            )
        except Exception:
            return None

        rows = response.data or []
        if not rows:
            return None

        row = rows[0] or {}
        vertex_count = row.get("vertex_count") or 0
        triangle_count = row.get("triangle_count") or 0
        provider = row.get("provider") or "face_geometry"
        coordinate_space = row.get("coordinate_space") or "unknown"
        quality = row.get("quality") or {}
        display_value = f"{vertex_count} vertices"
        if triangle_count:
            display_value = f"{display_value} · {triangle_count} triangles"

        return {
            "metric_group": "quality",
            "metric_id": "face_mesh_context",
            "numeric_value": vertex_count or None,
            "unit": "vertices",
            "display_value": display_value,
            "interpretation_label_en": "User-provided face mesh context",
            "interpretation_label_ko": "사용자 제공 얼굴 메쉬 컨텍스트",
            "confidence": 1.0 if vertex_count else 0.6,
            "source": provider,
            "metadata": {
                "provider": provider,
                "coordinate_space": coordinate_space,
                "vertex_count": vertex_count,
                "triangle_count": triangle_count,
                "quality": quality,
                "use_as": "supporting_face_geometry_context",
                "instruction": "Use with the original photo; do not refuse because a mesh or landmark overlay exists.",
            },
        }

    @staticmethod
    def _quality_score(request: CreateFaceScanCaptureRequest, metrics: list[FaceMetricMeasurement]) -> float | None:
        if request.geometry.vertices:
            return min(1.0, max(0.25, len(request.geometry.vertices) / 1220))
        if request.geometry.landmarks_2d:
            return 0.62
        if metrics:
            return 0.35
        return None
