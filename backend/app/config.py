"""Typed settings and explicit local runtime loading; no server-date fallback."""

import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, StrictInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Constructing this model in a test/helper never implicitly reads a file.
    model_config = SettingsConfigDict(
        env_file=None,
        env_ignore_empty=True,
        hide_input_in_errors=True,
        extra="ignore",
    )

    llm_provider: str | None = None
    llm_model_id: str | None = None
    llm_fallback_provider: str | None = None
    llm_fallback_model_id: str | None = None
    llm_timeout_seconds: int = Field(default=10, ge=1, le=30)
    gemini_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    groq_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    # Application fallback and optional development comparison credentials.
    openai_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    build_nvidia_api_key: SecretStr | None = Field(
        default=None, repr=False, exclude=True
    )
    # Preserve raw configuration; BusinessClock applies the specified day-90 default.
    business_as_of: date | None = None
    database_url: str = Field(default="sqlite:///./shgad.db", repr=False, exclude=True)
    app_env: str = "development"
    margin_min_coverage_pct: StrictInt = Field(default=80, ge=0, le=100)

    @field_validator("margin_min_coverage_pct", mode="before")
    @classmethod
    def parse_percentage_setting(cls, value):
        if isinstance(value, str) and re.fullmatch(r"[0-9]{1,3}", value):
            return int(value)
        return value


def runtime_settings() -> Settings:
    """Only runtime entry points load the fixed development file (decision D31).

    Process variables take precedence. Tests/production disable file loading by
    setting APP_ENV before launch. Never search parent folders or print settings.
    """
    local_file = (
        LOCAL_ENV_FILE
        if (os.environ.get("APP_ENV") or "development").lower() == "development"
        else None
    )
    return Settings(_env_file=local_file, _env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return runtime_settings()
