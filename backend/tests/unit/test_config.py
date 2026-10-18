"""Phase 0 settings: business dates come from configuration (roadmap §4, §5.4)."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.fixture
def local_config(tmp_path, monkeypatch):
    from app import config

    for name in (
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
        "LLM_PROVIDER",
        "LLM_MODEL_ID",
        "LLM_FALLBACK_PROVIDER",
        "LLM_FALLBACK_MODEL_ID",
        "BUSINESS_AS_OF",
        "DATABASE_URL",
        "LLM_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    path = tmp_path / "synthetic-settings.fixture"
    path.write_text(
        "LLM_PROVIDER=gemini\nLLM_MODEL_ID=recorded-local-model\n"
        "GEMINI_API_KEY='fictional-local-gemini'\n"
        "GROQ_API_KEY='fictional-local-groq'\nBUSINESS_AS_OF=\n"
        "HELDOUT_PATH=never-access-this-placeholder\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", path, raising=False)
    config.get_settings.cache_clear()
    yield config, path
    config.get_settings.cache_clear()


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
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-openai-sentinel")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///synthetic-private.db")
    settings = Settings()

    for value in (
        "synthetic-gemini-sentinel",
        "synthetic-groq-sentinel",
        "synthetic-openai-sentinel",
        "synthetic-private.db",
    ):
        assert value not in repr(settings)
        assert value not in settings.model_dump_json()


def test_coverage_threshold_can_be_configured_in_process_environment(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("MARGIN_MIN_COVERAGE_PCT", "75")
    assert Settings().margin_min_coverage_pct == 75


def test_runtime_loads_only_the_fixed_local_file_from_any_working_directory(
    local_config, tmp_path, monkeypatch
):
    config, _ = local_config
    other = tmp_path / "other-working-directory"
    other.mkdir()
    monkeypatch.chdir(other)
    settings = config.get_settings()
    assert settings.llm_model_id == "recorded-local-model"
    assert settings.gemini_api_key.get_secret_value() == "fictional-local-gemini"
    assert settings.groq_api_key.get_secret_value() == "fictional-local-groq"
    assert settings.business_as_of is None
    assert "never-access-this-placeholder" not in settings.model_dump_json()
    assert "fictional-local" not in repr(settings)
    assert "fictional-local" not in settings.model_dump_json()


def test_process_configuration_overrides_the_local_file(local_config, monkeypatch):
    config, _ = local_config
    monkeypatch.setenv("GEMINI_API_KEY", "fictional-process-credential")
    monkeypatch.setenv("LLM_MODEL_ID", "recorded-process-model")
    settings = config.get_settings()
    assert settings.llm_model_id == "recorded-process-model"
    assert settings.gemini_api_key.get_secret_value() == "fictional-process-credential"


def test_blank_process_values_keep_local_development_defaults(
    local_config, monkeypatch
):
    config, _ = local_config
    for name in ("APP_ENV", "GEMINI_API_KEY", "LLM_MODEL_ID"):
        monkeypatch.setenv(name, "")
    settings = config.get_settings()
    assert settings.llm_model_id == "recorded-local-model"
    assert settings.gemini_api_key.get_secret_value() == "fictional-local-gemini"


@pytest.mark.parametrize("mode", ["test", "production"])
def test_non_development_runtime_ignores_the_local_file(
    local_config, monkeypatch, mode
):
    config, path = local_config
    # A read would fail, proving the mode skips this file rather than discarding it.
    path.write_bytes(b"\xff\xfe\xff")
    monkeypatch.setenv("APP_ENV", mode)
    settings = config.get_settings()
    assert settings.app_env == mode and settings.gemini_api_key is None
    assert settings.llm_model_id is None


def test_bare_settings_never_implicitly_reads_a_local_file(local_config):
    _, path = local_config
    path.write_bytes(b"\xff\xfe\xff")
    assert Settings().gemini_api_key is None


def test_empty_template_and_missing_local_file_are_valid(local_config):
    from pathlib import Path

    config, path = local_config
    template = Path(__file__).resolve().parents[3] / ".env.example"
    path.write_bytes(template.read_bytes())
    assert config.get_settings().business_as_of is None
    assert config.get_settings().llm_model_id is None
    path.unlink()
    config.get_settings.cache_clear()
    assert config.get_settings().gemini_api_key is None


def test_bad_local_configuration_never_echoes_its_value(local_config):
    config, path = local_config
    path.write_text("LLM_TIMEOUT_SECONDS=fictional-sensitive-value\n", encoding="utf-8")
    with pytest.raises(ValidationError) as caught:
        config.get_settings()
    assert "fictional-sensitive-value" not in str(caught.value)


def test_openai_comparison_key_uses_runtime_loading_and_stays_secret(
    local_config, monkeypatch
):
    config, path = local_config
    path.write_text("OPENAI_API_KEY=fictional-openai-local\n", encoding="utf-8")
    assert config.Settings().openai_api_key is None
    settings = config.runtime_settings()
    assert settings.openai_api_key.get_secret_value() == "fictional-openai-local"
    assert "fictional-openai" not in repr(settings)
    assert "fictional-openai" not in settings.model_dump_json()
    monkeypatch.setenv("OPENAI_API_KEY", "fictional-openai-process")
    assert (
        config.runtime_settings().openai_api_key.get_secret_value()
        == "fictional-openai-process"
    )
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setenv("APP_ENV", "production")
    assert config.runtime_settings().openai_api_key is None
