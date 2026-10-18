"""Typed environment settings; no implicit .env reads or server-date fallback."""

import re
from datetime import date
from functools import lru_cache

from pydantic import Field, SecretStr, StrictInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    llm_provider: str | None = None
    llm_model_id: str | None = None
    llm_fallback_provider: str | None = None
    llm_fallback_model_id: str | None = None
    llm_timeout_seconds: int = Field(default=10, ge=1, le=30)
    gemini_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    groq_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
