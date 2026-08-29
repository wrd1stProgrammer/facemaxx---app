from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True, slots=True)
class InsightSentryConnection:
    base_url: str
    headers: tuple[tuple[str, str], ...]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True, populate_by_name=True)

    app_env: str = Field(default="local", validation_alias=AliasChoices("CHARTAGENT_APP_ENV", "APP_ENV"))
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CHARTAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    insightsentry_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CHARTAGENT_INSIGHTSENTRY_API_KEY", "INSIGHTSENTRY_API_KEY"),
    )
    insightsentry_base_url: str = Field(
        default="https://api.insightsentry.com",
        validation_alias=AliasChoices("CHARTAGENT_INSIGHTSENTRY_BASE_URL", "INSIGHTSENTRY_BASE_URL"),
    )
    insightsentry_rapidapi_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CHARTAGENT_INSIGHTSENTRY_RAPIDAPI_KEY",
            "INSIGHTSENTRY_RAPIDAPI_KEY",
        ),
    )
    insightsentry_rapidapi_host: Literal["insightsentry.p.rapidapi.com"] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CHARTAGENT_INSIGHTSENTRY_RAPIDAPI_HOST",
            "INSIGHTSENTRY_RAPIDAPI_HOST",
        ),
    )
    codex_binary: str = Field(
        default="codex",
        validation_alias=AliasChoices("CHARTAGENT_CODEX_BINARY", "CODEX_BINARY"),
    )
    codex_timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices("CHARTAGENT_CODEX_TIMEOUT_SECONDS", "CODEX_TIMEOUT_SECONDS"),
    )
    codex_max_concurrency: int = Field(
        default=5,
        validation_alias=AliasChoices("CHARTAGENT_CODEX_MAX_CONCURRENCY", "CODEX_MAX_CONCURRENCY"),
    )
    codex_model: Literal["gpt-5.6-luna"] = "gpt-5.6-luna"
    codex_reasoning_effort: Literal["low"] = "low"
    openai_model: str = Field(
        default="gpt-5-mini",
        validation_alias=AliasChoices("CHARTAGENT_OPENAI_MODEL", "OPENAI_MODEL"),
    )
    max_image_bytes: int = 12 * 1024 * 1024

    @property
    def insightsentry_connection(self) -> InsightSentryConnection | None:
        if self.insightsentry_rapidapi_key and self.insightsentry_rapidapi_host:
            return InsightSentryConnection(
                base_url=f"https://{self.insightsentry_rapidapi_host}",
                headers=(
                    ("Accept", "application/json"),
                    ("x-rapidapi-host", self.insightsentry_rapidapi_host),
                    ("x-rapidapi-key", self.insightsentry_rapidapi_key),
                ),
            )
        if self.insightsentry_api_key:
            return InsightSentryConnection(
                base_url=self.insightsentry_base_url,
                headers=(("Authorization", f"Bearer {self.insightsentry_api_key}"),),
            )
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
