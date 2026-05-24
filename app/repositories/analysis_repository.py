from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.db.supabase import get_supabase_service_client
from app.models.constants import ANALYSIS_METRIC_TEMPLATES, ANALYSIS_MODES
from app.schemas.analysis import (
    AnalysisResultPayload,
    AnalysisRunResponse,
    AnalysisRunSummaryResponse,
    LookArchetypeResult,
)


class AnalysisRepository:
    def list_modes(self) -> list[dict]:
        supabase = get_supabase_service_client()
        if supabase is None:
            return ANALYSIS_MODES

        response = (
            supabase.table("analysis_modes")
            .select("*")
            .eq("is_enabled", True)
            .order("sort_order")
            .execute()
        )
        return response.data or ANALYSIS_MODES

    def create_run(
        self,
        user_id: str | None,
        client_install_id: str | None,
        mode_id: str,
        photo_id: UUID | None,
        photo_ids: list[UUID] | None,
        source: str,
        face_scan_capture_id: UUID | None = None,
        onboarding_context: dict[str, Any] | None = None,
        is_free_trial_result: bool = False,
    ) -> UUID:
        settings = get_settings()
        run_id = uuid4()
        payload = {
            "id": str(run_id),
            "user_id": user_id,
            "client_install_id": client_install_id or settings.demo_user_id,
            "mode_id": mode_id,
            "photo_id": str(photo_id) if photo_id else None,
            "photo_ids": [str(photo_id) for photo_id in (photo_ids or [])],
            "face_scan_capture_id": str(face_scan_capture_id) if face_scan_capture_id else None,
            "source": source,
            "status": "processing",
            "onboarding_context": self._safe_json(onboarding_context or {}),
            "is_free_trial_result": is_free_trial_result,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        supabase = get_supabase_service_client()
        if supabase is None:
            return run_id

        try:
            self._ensure_analysis_modes(supabase)
            self._ensure_analysis_metric_templates(supabase)
            try:
                supabase.table("analysis_runs").insert(payload).execute()
            except Exception as exc:
                message = str(exc)
                if "onboarding_context" not in message and "photo_ids" not in message and "is_free_trial_result" not in message:
                    raise
                legacy_payload = dict(payload)
                if "onboarding_context" in message:
                    legacy_payload.pop("onboarding_context", None)
                if "photo_ids" in message:
                    legacy_payload.pop("photo_ids", None)
                if "is_free_trial_result" in message:
                    legacy_payload.pop("is_free_trial_result", None)
                try:
                    supabase.table("analysis_runs").insert(legacy_payload).execute()
                except Exception as retry_exc:
                    retry_message = str(retry_exc)
                    if (
                        "onboarding_context" not in retry_message
                        and "photo_ids" not in retry_message
                        and "is_free_trial_result" not in retry_message
                    ):
                        raise
                    legacy_payload = dict(payload)
                    legacy_payload.pop("onboarding_context", None)
                    legacy_payload.pop("photo_ids", None)
                    legacy_payload.pop("is_free_trial_result", None)
                    supabase.table("analysis_runs").insert(legacy_payload).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create analysis run",
            ) from exc

        return run_id

    def complete_run(
        self,
        run_id: UUID,
        result: AnalysisResultPayload,
        photo_ids: list[UUID] | None = None,
    ) -> None:
        supabase = get_supabase_service_client()
        if supabase is None:
            return

        look_archetype_id = None
        if result.look_archetype is not None:
            look_archetype_id = self._ensure_look_archetype(supabase, result.look_archetype)

        run_update = {
            "status": "completed",
            "model_provider": result.provider,
            "model_name": result.model_name,
            "overall_score": self._safe_score(result.overall_score),
            "overall_progress": self._safe_progress(result.overall_progress),
            "potential_score": self._safe_score(result.potential_score),
            "potential_progress": self._safe_progress(result.potential_progress),
            "summary_key": result.summary_key,
            "summary_text": result.summary_text,
            "look_archetype_id": look_archetype_id,
            "raw_provider_response": self._safe_json(result.model_dump(mode="json")),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        supabase.table("analysis_runs").update(run_update).eq("id", str(run_id)).execute()

        if result.rings:
            supabase.table("analysis_score_rings").insert([
                {**self._safe_ring(ring.model_dump()), "run_id": str(run_id)} for ring in result.rings
            ]).execute()

        if result.metrics:
            supabase.table("analysis_metrics").insert([
                {**self._safe_metric(metric.model_dump()), "run_id": str(run_id), "mode_id": result.mode_id}
                for metric in result.metrics
            ]).execute()

        if result.growth_opportunities:
            supabase.table("growth_opportunities").insert([
                {**item.model_dump(), "run_id": str(run_id)}
                for item in result.growth_opportunities
            ]).execute()

        if result.photo_rankings:
            self._insert_photo_rankings(supabase, run_id, result, photo_ids or [])

        if result.coach_items:
            supabase.table("glow_up_coach_items").insert([
                {**item.model_dump(), "run_id": str(run_id)}
                for item in result.coach_items
            ]).execute()

    def _insert_photo_rankings(
        self,
        supabase,
        run_id: UUID,
        result: AnalysisResultPayload,
        photo_ids: list[UUID],
    ) -> None:
        rows = []
        for index, ranking in enumerate(result.photo_rankings):
            candidate_photo_id = (
                str(photo_ids[ranking.candidate_index - 1])
                if 0 <= ranking.candidate_index - 1 < len(photo_ids)
                else None
            )
            rows.append({
                "run_id": str(run_id),
                "photo_id": candidate_photo_id,
                "candidate_index": ranking.candidate_index,
                "rank": ranking.rank,
                "score": self._safe_score(ranking.score),
                "verdict": ranking.verdict,
                "reason_text": ranking.reason_text,
                "description_text": ranking.description_text,
                "best_use_text": ranking.best_use_text,
                "fun_label_text": ranking.fun_label_text,
                "strengths": ranking.strengths,
                "weakness_text": ranking.weakness_text,
                "fix_text": ranking.fix_text,
                "caption_idea_text": ranking.caption_idea_text,
                "vibe_tags": ranking.vibe_tags,
                "metadata": self._safe_json(ranking.model_dump(mode="json")),
                "sort_order": ranking.rank * 10 if ranking.rank else (index + 1) * 10,
            })

        if not rows:
            return

        try:
            supabase.table("analysis_photo_rankings").insert(rows).execute()
        except Exception as exc:
            message = str(exc)
            if "analysis_photo_rankings" not in message:
                raise
            print("Analysis photo rankings table is not available; skipping relational ranking insert.")

    def _ensure_look_archetype(self, supabase, archetype: LookArchetypeResult) -> str:
        payload = {
            "id": archetype.archetype_id,
            "type_name": archetype.type_name,
            "title_key": archetype.title_key,
            "subtitle_key": archetype.subtitle_key,
            "body_key": archetype.body_key,
            "share_badge_key": archetype.share_badge_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        supabase.table("look_archetypes").upsert(payload).execute()
        return archetype.archetype_id

    def _ensure_analysis_modes(self, supabase) -> None:
        try:
            supabase.table("analysis_modes").upsert(ANALYSIS_MODES, on_conflict="id").execute()
        except TypeError:
            supabase.table("analysis_modes").upsert(ANALYSIS_MODES).execute()

    def _ensure_analysis_metric_templates(self, supabase) -> None:
        try:
            supabase.table("analysis_metric_templates").upsert(
                ANALYSIS_METRIC_TEMPLATES,
                on_conflict="mode_id,section,metric_id",
            ).execute()
        except TypeError:
            supabase.table("analysis_metric_templates").upsert(ANALYSIS_METRIC_TEMPLATES).execute()
        except Exception as exc:
            if "analysis_metric_templates" not in str(exc):
                raise

    def fail_run(self, run_id: UUID, message: str) -> None:
        supabase = get_supabase_service_client()
        if supabase is None:
            return

        supabase.table("analysis_runs").update({
            "status": "failed",
            "error_message": message,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", str(run_id)).execute()

    def get_run(
        self,
        run_id: UUID,
        user_id: str | None,
        client_install_id: str | None,
    ) -> AnalysisRunResponse:
        supabase = get_supabase_service_client()
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run lookup requires Supabase configuration",
            )

        query = supabase.table("analysis_runs").select("*").eq("id", str(run_id))
        if user_id:
            query = query.eq("user_id", user_id)
        elif client_install_id:
            query = query.eq("client_install_id", client_install_id)
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing request identity")

        response = query.single().execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")

        row = response.data
        result = None
        raw_provider_response = row.get("raw_provider_response")
        if raw_provider_response:
            try:
                result = AnalysisResultPayload.model_validate(raw_provider_response)
            except Exception as exc:
                print(f"Analysis run result hydration failed: {exc}")

        return AnalysisRunResponse(
            id=row["id"],
            status=row["status"],
            mode_id=row["mode_id"],
            is_free_trial_result=bool(row.get("is_free_trial_result")),
            photo_id=row.get("photo_id"),
            photo_ids=self._photo_ids_from_row(row),
            face_scan_capture_id=row.get("face_scan_capture_id"),
            created_at=row.get("created_at"),
            completed_at=row.get("completed_at"),
            result=result,
        )

    def list_runs(
        self,
        user_id: str | None,
        client_install_id: str | None,
        limit: int,
    ) -> list[AnalysisRunSummaryResponse]:
        supabase = get_supabase_service_client()
        if supabase is None:
            return []

        query = (
            supabase
            .table("analysis_runs")
            .select("id,status,mode_id,is_free_trial_result,photo_id,photo_ids,face_scan_capture_id,overall_score,summary_text,created_at,completed_at")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if user_id:
            query = query.eq("user_id", user_id)
        elif client_install_id:
            query = query.eq("client_install_id", client_install_id)
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing request identity")

        try:
            response = query.execute()
        except Exception as exc:
            message = str(exc)
            if "photo_ids" not in message and "is_free_trial_result" not in message:
                raise
            select_columns = "id,status,mode_id,photo_id,face_scan_capture_id,overall_score,summary_text,created_at,completed_at"
            if "photo_ids" not in message:
                select_columns = "id,status,mode_id,photo_ids,face_scan_capture_id,overall_score,summary_text,created_at,completed_at"
            query = (
                supabase
                .table("analysis_runs")
                .select(select_columns)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if user_id:
                query = query.eq("user_id", user_id)
            elif client_install_id:
                query = query.eq("client_install_id", client_install_id)
            response = query.execute()

        return [
            AnalysisRunSummaryResponse.model_validate({
                **row,
                "photo_ids": self._photo_ids_from_row(row),
            })
            for row in (response.data or [])
        ]

    @staticmethod
    def _photo_ids_from_row(row: dict[str, Any]) -> list[str]:
        raw_photo_ids = row.get("photo_ids") or []
        if isinstance(raw_photo_ids, list):
            photo_ids = [str(photo_id) for photo_id in raw_photo_ids if photo_id]
        else:
            photo_ids = []
        primary_photo_id = row.get("photo_id")
        if primary_photo_id and str(primary_photo_id) not in photo_ids:
            photo_ids.insert(0, str(primary_photo_id))
        return photo_ids

    def _safe_ring(self, row: dict[str, Any]) -> dict[str, Any]:
        row["score"] = self._safe_progress(row.get("score")) or 0.0
        return self._safe_json(row)

    def _safe_metric(self, row: dict[str, Any]) -> dict[str, Any]:
        row["numeric_value"] = self._safe_number(row.get("numeric_value"))
        return self._safe_json(row)

    @classmethod
    def _safe_score(cls, value: Any) -> float | None:
        number = cls._safe_number(value)
        if number is None:
            return None
        if 0 <= number <= 1:
            return round(number * 10, 2)
        if 10 < number <= 100:
            return round(number / 10, 2)
        return round(min(max(number, 0.0), 10.0), 2)

    @classmethod
    def _safe_progress(cls, value: Any) -> float | None:
        number = cls._safe_number(value)
        if number is None:
            return None
        if number > 10:
            number = number / 100
        elif number > 1:
            number = number / 10
        return round(min(max(number, 0.0), 1.0), 4)

    @staticmethod
    def _safe_number(value: Any) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _safe_json(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: cls._safe_json(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._safe_json(item) for item in value]
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        return value
