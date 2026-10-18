"""Phase 0 settings: business dates come from configuration (roadmap §4, §5.4)."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_read_configured_business_date(monkeypatch):
    monkeypatch.setenv("BUSINESS_AS_OF", "2026-09-28")
    monkeypatch.setenv("LLM_PROVIDER", "synthetic-provider")
    monkeypatch.setenv("LLM_MODEL_ID", "synthetic-model")
    monkeypatch.setenv("APP_ENV", "test")
    settings = Settings()

    assert settings.business_as_of == date(2026, 9, 28)
    assert settings.llm_provider == "synthetic-provider"
    assert settings.llm_model_id == "synthetic-model"
    assert settings.app_env == "test"


def test_missing_business_date_stays_unconfigured(monkeypatch):
    monkeypatch.delenv("BUSINESS_AS_OF", raising=False)
    assert Settings().business_as_of is None


def test_invalid_business_date_is_rejected(monkeypatch):
    monkeypatch.setenv("BUSINESS_AS_OF", "not-a-date")
    with pytest.raises(ValidationError):
        Settings()


def test_private_settings_are_redacted(monkeypatch):
    monkeypatch.delenv("BUSINESS_AS_OF", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-sentinel")
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-groq-sentinel")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///synthetic-private.db")
    settings = Settings()

    for value in (
        "synthetic-gemini-sentinel",
        "synthetic-groq-sentinel",
        "synthetic-private.db",
    ):
        assert value not in repr(settings)
        assert value not in settings.model_dump_json()


def test_coverage_threshold_can_be_configured_in_process_environment(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("MARGIN_MIN_COVERAGE_PCT", "75")
    assert Settings().margin_min_coverage_pct == 75
