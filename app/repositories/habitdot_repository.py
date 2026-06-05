from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.api.deps import RequestIdentity
from app.db.supabase import get_supabase_service_client
from app.schemas.habitdot import (
    HabitdotBugReportRequest,
    HabitdotFeedbackRequest,
    HabitdotOnboardingRequest,
    HabitdotPaywallViewRequest,
    HabitdotPersistedResponse,
)


class HabitdotRepository:
    def save_onboarding(
        self,
        identity: RequestIdentity,
        request: HabitdotOnboardingRequest,
        inferred_country_code: str | None = None,
    ) -> HabitdotPersistedResponse:
        supabase = get_supabase_service_client()
        if supabase is None:
            return HabitdotPersistedResponse(persisted=False)

        completed_at = request.completed_at or datetime.now(UTC)
        payload = {
            "user_id": identity.user_id,
            "client_install_id": identity.client_install_id,
            "locale": request.locale,
            "country_code": self._normalized_country(request.country_code),
            "inferred_country_code": self._normalized_country(inferred_country_code),
            "time_zone": request.time_zone,
            "app_version": request.app_version,
            "build_number": request.build_number,
            "platform": request.platform,
            "source": request.source,
            "selected_first_habit": request.selected_first_habit,
            "selected_theme": request.selected_theme,
            "common_reminder_hour": request.common_reminder_hour,
            "common_reminder_minute": request.common_reminder_minute,
            "survey": request.survey,
            "raw_payload": request.model_dump(mode="json"),
            "completed_at": completed_at.isoformat(),
        }

        return self._insert("habitdot_onboarding_responses", payload)

    def save_feedback(
        self,
        identity: RequestIdentity,
        request: HabitdotFeedbackRequest,
        inferred_country_code: str | None = None,
    ) -> HabitdotPersistedResponse:
        payload = {
            "user_id": identity.user_id,
            "client_install_id": identity.client_install_id,
            "kind": request.kind,
            "subject": request.subject,
            "message": request.message,
            "contact_email": request.contact_email,
            "locale": request.locale,
            "country_code": self._normalized_country(request.country_code),
            "inferred_country_code": self._normalized_country(inferred_country_code),
            "time_zone": request.time_zone,
            "app_version": request.app_version,
            "build_number": request.build_number,
            "platform": request.platform,
            "metadata": request.metadata,
        }
        return self._insert("habitdot_feedback", payload)

    def save_bug_report(
        self,
        identity: RequestIdentity,
        request: HabitdotBugReportRequest,
        inferred_country_code: str | None = None,
    ) -> HabitdotPersistedResponse:
        payload = {
            "user_id": identity.user_id,
            "client_install_id": identity.client_install_id,
            "subject": request.subject,
            "message": request.message,
            "contact_email": request.contact_email,
            "locale": request.locale,
            "country_code": self._normalized_country(request.country_code),
            "inferred_country_code": self._normalized_country(inferred_country_code),
            "time_zone": request.time_zone,
            "app_version": request.app_version,
            "build_number": request.build_number,
            "platform": request.platform,
            "metadata": request.metadata,
        }
        return self._insert("habitdot_bug_reports", payload)

    def record_paywall_view(
        self,
        identity: RequestIdentity,
        request: HabitdotPaywallViewRequest,
        inferred_country_code: str | None = None,
    ) -> HabitdotPersistedResponse:
        supabase = get_supabase_service_client()
        if supabase is None or identity.client_install_id is None:
            return HabitdotPersistedResponse(persisted=False)

        params = {
            "p_client_install_id": identity.client_install_id,
            "p_locale": request.locale,
            "p_country_code": self._normalized_country(request.country_code),
            "p_inferred_country_code": self._normalized_country(inferred_country_code),
            "p_time_zone": request.time_zone,
            "p_app_version": request.app_version,
            "p_build_number": request.build_number,
            "p_platform": request.platform,
        }

        try:
            response = supabase.rpc("increment_habitdot_paywall_view", params).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="habitdot_install_metrics table is not installed. Run the Supabase migration.",
            ) from exc

        return HabitdotPersistedResponse(persisted=True, count=self._paywall_count(response.data))

    @staticmethod
    def _insert(table: str, payload: dict) -> HabitdotPersistedResponse:
        supabase = get_supabase_service_client()
        if supabase is None:
            return HabitdotPersistedResponse(persisted=False)

        try:
            response = supabase.table(table).insert(payload).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{table} table is not installed. Run the Supabase migration.",
            ) from exc

        rows = response.data or []
        row_id = str(rows[0].get("id")) if rows and rows[0].get("id") else None
        return HabitdotPersistedResponse(persisted=True, id=row_id)

    @staticmethod
    def _paywall_count(value) -> int | None:
        if isinstance(value, int):
            return value

        if not isinstance(value, list) or not value:
            return None

        first = value[0]
        if isinstance(first, int):
            return first

        if not isinstance(first, dict):
            return None

        for key in ("increment_habitdot_paywall_view", "count"):
            raw_count = first.get(key)
            if isinstance(raw_count, int):
                return raw_count

        return None

    @staticmethod
    def _normalized_country(value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip().upper()
        return value[:8] if value else None
