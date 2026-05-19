from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status

from app.db.supabase import get_supabase_service_client
from app.schemas.onboarding import OnboardingPreferencesRequest, OnboardingPreferencesResponse


GOAL_LABELS = {
    "symmetry": "facial symmetry and balance",
    "jawline": "jawline and lower-face definition",
    "skin": "skin clarity and glow",
    "proportions": "facial proportions and structure",
    "progress": "glow-up progress tracking",
    "photos": "best photo and angle selection",
    "profile": "dating and social profile performance",
}

AGE_CONTEXT = {
    "18-24": "youthful social/profile presentation; keep recommendations light, current, and photo-first",
    "25-34": "polished profile presentation; emphasize confidence, grooming, lighting, and repeatable photo setup",
    "35-44": "refined presentation; emphasize structure, clean lighting, skin texture handling, and style consistency",
    "45+": "natural polished presentation; emphasize flattering light, clean framing, and texture-friendly detail",
}

GENDER_CONTEXT = {
    "male": "self-selected male; keep styling and grooming suggestions masculine-coded only when visibly relevant",
    "female": "self-selected female; keep styling and framing suggestions feminine-coded only when visibly relevant",
    "other": "self-selected other; keep styling guidance neutral and avoid gendered assumptions",
}


class OnboardingRepository:
    def save_preferences(
        self,
        user_id: str | None,
        request: OnboardingPreferencesRequest,
    ) -> OnboardingPreferencesResponse:
        if not user_id:
            return self._response_from_request(request, persisted=False)

        supabase = get_supabase_service_client()
        if supabase is None:
            return self._response_from_request(request, persisted=False)

        age_range_id = request.age_range_id or self._age_range_id(request.age)
        payload = {
            "user_id": user_id,
            "selected_goal_ids": request.selected_goal_ids,
            "gender_id": request.gender_id,
            "age": request.age,
            "age_range_id": age_range_id,
            "completed_at": request.completed_at.isoformat(),
            "metadata": request.metadata,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self._ensure_profile(supabase, user_id)
            response = supabase.table("user_onboarding_preferences").upsert(
                payload,
                on_conflict="user_id",
            ).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Onboarding preferences table is not installed. Run the Supabase migration.",
            ) from exc

        rows = response.data or []
        return self._response_from_row(rows[0] if rows else payload, persisted=True)

    def get_preferences(self, user_id: str | None) -> OnboardingPreferencesResponse:
        if not user_id:
            return OnboardingPreferencesResponse(persisted=False)

        supabase = get_supabase_service_client()
        if supabase is None:
            return OnboardingPreferencesResponse(persisted=False)

        try:
            response = (
                supabase.table("user_onboarding_preferences")
                .select("selected_goal_ids,gender_id,age,age_range_id,completed_at,metadata")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Onboarding preferences table is not installed. Run the Supabase migration.",
            ) from exc

        rows = response.data or []
        if not rows:
            return OnboardingPreferencesResponse(persisted=False)

        return self._response_from_row(rows[0], persisted=True)

    def context_for_user(self, user_id: str | None) -> dict[str, Any]:
        if not user_id:
            return {}

        supabase = get_supabase_service_client()
        if supabase is None:
            return {}

        try:
            response = (
                supabase.table("user_onboarding_preferences")
                .select("selected_goal_ids,gender_id,age,age_range_id,completed_at")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            print(f"Onboarding context skipped: {exc}")
            return {}

        rows = response.data or []
        return self.normalized_context(rows[0] if rows else None)

    def normalized_context(self, raw_context: dict[str, Any] | None) -> dict[str, Any]:
        if not raw_context:
            return {}

        selected_goal_ids = [
            goal_id
            for goal_id in raw_context.get("selected_goal_ids", [])
            if goal_id in GOAL_LABELS
        ]
        gender_id = raw_context.get("gender_id")
        age = raw_context.get("age")
        age_range_id = raw_context.get("age_range_id") or self._age_range_id(age)

        context: dict[str, Any] = {
            "selected_goal_ids": selected_goal_ids,
            "selected_goal_labels": [GOAL_LABELS[goal_id] for goal_id in selected_goal_ids],
        }
        if gender_id in GENDER_CONTEXT:
            context["gender_id"] = gender_id
            context["gender_context"] = GENDER_CONTEXT[gender_id]
        if isinstance(age, int):
            context["age"] = age
        if age_range_id in AGE_CONTEXT:
            context["age_range_id"] = age_range_id
            context["age_context"] = AGE_CONTEXT[age_range_id]
        if raw_context.get("completed_at"):
            context["completed_at"] = raw_context["completed_at"]

        return context

    @staticmethod
    def _ensure_profile(supabase, user_id: str) -> None:
        supabase.table("profiles").upsert({"id": user_id}, on_conflict="id").execute()

    @staticmethod
    def _response_from_request(
        request: OnboardingPreferencesRequest,
        persisted: bool,
    ) -> OnboardingPreferencesResponse:
        return OnboardingPreferencesResponse(
            selected_goal_ids=request.selected_goal_ids,
            gender_id=request.gender_id,
            age=request.age,
            age_range_id=request.age_range_id or OnboardingRepository._age_range_id(request.age),
            completed_at=request.completed_at,
            metadata=request.metadata,
            persisted=persisted,
        )

    @staticmethod
    def _response_from_row(row: dict[str, Any], persisted: bool) -> OnboardingPreferencesResponse:
        return OnboardingPreferencesResponse(
            selected_goal_ids=row.get("selected_goal_ids") or [],
            gender_id=row.get("gender_id"),
            age=row.get("age"),
            age_range_id=row.get("age_range_id") or OnboardingRepository._age_range_id(row.get("age")),
            completed_at=row.get("completed_at"),
            metadata=row.get("metadata") or {},
            persisted=persisted,
        )

    @staticmethod
    def _age_range_id(age: Optional[int]) -> Optional[str]:
        if age is None:
            return None
        if age < 25:
            return "18-24"
        if age < 35:
            return "25-34"
        if age < 45:
            return "35-44"
        return "45+"
