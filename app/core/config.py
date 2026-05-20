from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    app_env: str = "local"
    api_prefix: str = "/v1"
    cors_origins: str = ""

    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_storage_bucket: str = "face-photos"
    supabase_storage_required: bool = False

    image_storage_provider: Literal["auto", "local", "supabase", "cloudinary"] = "auto"
    cloudinary_cloud_name: Optional[str] = None
    cloudinary_api_key: Optional[str] = None
    cloudinary_api_secret: Optional[str] = None
    cloudinary_url: Optional[str] = None
    cloudinary_folder: str = "facemaxx"

    auth_disabled: bool = True
    demo_user_id: str = "00000000-0000-0000-0000-000000000001"

    ai_provider: Literal["dummy", "gemini", "openai"] = "gemini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_fallback_models: str = "gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-flash-lite"
    gemini_retry_attempts: int = 1
    gemini_retry_base_delay_seconds: float = 0.8
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-5-mini"

    revenuecat_secret_api_key: Optional[str] = None
    revenuecat_webhook_bearer_token: Optional[str] = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Local development frequently has stale shell exports from other projects.
        # Prefer this project's .env when it exists, while still allowing real env
        # variables to work in deployed environments that do not ship a .env file.
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def resolved_cloudinary_cloud_name(self) -> Optional[str]:
        if self.cloudinary_cloud_name:
            return self.cloudinary_cloud_name
        parsed = self._parsed_cloudinary_url()
        return parsed.hostname if parsed else None

    @property
    def resolved_cloudinary_api_key(self) -> Optional[str]:
        if self.cloudinary_api_key:
            return self.cloudinary_api_key
        parsed = self._parsed_cloudinary_url()
        return parsed.username if parsed else None

    @property
    def resolved_cloudinary_api_secret(self) -> Optional[str]:
        if self.cloudinary_api_secret:
            return self.cloudinary_api_secret
        parsed = self._parsed_cloudinary_url()
        return parsed.password if parsed else None

    @property
    def cloudinary_configured(self) -> bool:
        return bool(
            self.resolved_cloudinary_cloud_name
            and self.resolved_cloudinary_api_key
            and self.resolved_cloudinary_api_secret
        )

    def _parsed_cloudinary_url(self):
        if not self.cloudinary_url:
            return None
        parsed = urlparse(self.cloudinary_url)
        if parsed.scheme != "cloudinary":
            return None
        return parsed

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gemini_model_candidates(self) -> list[str]:
        candidates = [self.gemini_model]
        candidates.extend(
            model.strip()
            for model in self.gemini_fallback_models.split(",")
            if model.strip()
        )
        return candidates


@lru_cache
def get_settings() -> Settings:
    return Settings()
