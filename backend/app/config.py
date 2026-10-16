"""Typed environment settings; no implicit .env reads or server-date fallback."""

from datetime import date
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    llm_provider: str | None = None
    llm_model_id: str | None = None
    gemini_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    groq_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    # Unconfigured is explicit: financial services must require this in later phases.
    business_as_of: date | None = None
    database_url: str = Field(default="sqlite:///./shgad.db", repr=False, exclude=True)
    app_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
