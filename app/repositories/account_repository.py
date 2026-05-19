from __future__ import annotations

from app.api.deps import RequestIdentity
from app.db.supabase import get_supabase_service_client


class AccountRepository:
    def delete_account_data(self, identity: RequestIdentity) -> None:
        supabase = get_supabase_service_client()
        if supabase is None:
            return

        if identity.user_id:
            self._delete_by_column(supabase, "analysis_runs", "user_id", identity.user_id)
            self._delete_by_column(supabase, "face_scan_captures", "user_id", identity.user_id)
            self._delete_by_column(supabase, "photos", "user_id", identity.user_id)
            self._delete_by_column(supabase, "user_onboarding_preferences", "user_id", identity.user_id)
            self._delete_by_column(supabase, "user_usage", "user_id", identity.user_id)
            self._delete_by_column(supabase, "profiles", "id", identity.user_id)
            self._delete_auth_user(supabase, identity.user_id)
            return

        if identity.client_install_id:
            self._delete_by_column(supabase, "analysis_runs", "client_install_id", identity.client_install_id)
            self._delete_by_column(supabase, "face_scan_captures", "client_install_id", identity.client_install_id)
            self._delete_by_column(supabase, "photos", "client_install_id", identity.client_install_id)

    @staticmethod
    def _delete_by_column(supabase, table: str, column: str, value: str) -> None:
        try:
            supabase.table(table).delete().eq(column, value).execute()
        except Exception as exc:
            print(f"Account cleanup skipped for {table}.{column}: {exc}")

    @staticmethod
    def _delete_auth_user(supabase, user_id: str) -> None:
        try:
            supabase.auth.admin.delete_user(user_id)
        except Exception as exc:
            print(f"Supabase auth user deletion skipped: {exc}")
