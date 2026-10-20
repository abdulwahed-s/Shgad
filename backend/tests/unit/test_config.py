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
        "BUILD_NVIDIA_API_KEY",
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
    monkeypatch.setenv("BUILD_NVIDIA_API_KEY", "synthetic-nvidia-sentinel")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///synthetic-private.db")
    settings = Settings()

    for value in (
        "synthetic-gemini-sentinel",
        "synthetic-groq-sentinel",
        "synthetic-openai-sentinel",
        "synthetic-nvidia-sentinel",
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


def test_selected_template_has_no_credentials_and_missing_file_is_valid(local_config):
    from pathlib import Path

    from app.agents.llm_client import provider_configs

    config, path = local_config
    template = Path(__file__).resolve().parents[3] / ".env.example"
    path.write_bytes(template.read_bytes())
    selected = config.get_settings()
    assert selected.business_as_of is None
    assert (selected.llm_provider, selected.llm_model_id) == (
        "gemini",
        "gemini-3.8-flash",
    )
    assert (selected.llm_fallback_provider, selected.llm_fallback_model_id) == (
        "openai",
        "gpt-6-luna",
    )
    assert selected.gemini_api_key is selected.openai_api_key is None
    assert selected.llm_max_output_tokens == 8192
    assert provider_configs(selected) == ()  # Example IDs cannot enable network calls.
    path.unlink()
    config.get_settings.cache_clear()
    assert config.get_settings().gemini_api_key is None


def test_bad_local_configuration_never_echoes_its_value(local_config):
    config, path = local_config
    path.write_text("LLM_TIMEOUT_SECONDS=fictional-sensitive-value\n", encoding="utf-8")
    with pytest.raises(ValidationError) as caught:
        config.get_settings()
    assert "fictional-sensitive-value" not in str(caught.value)


@pytest.mark.parametrize(
    ("variable", "field"),
    [
        ("OPENAI_API_KEY", "openai_api_key"),
        ("BUILD_NVIDIA_API_KEY", "build_nvidia_api_key"),
    ],
)
def test_comparison_keys_use_runtime_loading_and_stay_secret(
    local_config, monkeypatch, variable, field
):
    config, path = local_config
    path.write_text(f"{variable}=fictional-comparison-local\n", encoding="utf-8")
    assert getattr(config.Settings(), field) is None
    settings = config.runtime_settings()
    assert getattr(settings, field).get_secret_value() == "fictional-comparison-local"
    assert "fictional-comparison" not in repr(settings)
    assert "fictional-comparison" not in settings.model_dump_json()
    monkeypatch.setenv(variable, "fictional-comparison-process")
    assert (
        getattr(config.runtime_settings(), field).get_secret_value()
        == "fictional-comparison-process"
    )
    monkeypatch.delenv(variable)
    monkeypatch.setenv("APP_ENV", "production")
    assert getattr(config.runtime_settings(), field) is None
