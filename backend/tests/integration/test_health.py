"""T14: API_CONTRACT endpoints /health; roadmap §17."""

import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


def test_t14_health_returns_only_status_and_version(monkeypatch):
    # Synthetic sentinels: the endpoint must never serialize environment settings.
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-sentinel")
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-groq-sentinel")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///synthetic-private.db")

    async def request_health():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
    assert response.headers["content-type"] == "application/json"


def test_runtime_http_uses_fake_local_configuration_without_disclosing_it(
    api, monkeypatch, tmp_path
):
    from app import config

    fake_file = tmp_path / "synthetic-runtime-settings.fixture"
    fake_file.write_text(
        "LLM_PROVIDER=groq\nLLM_MODEL_ID=recorded-local-model\n"
        "GROQ_API_KEY=fictional-local-secret\nBUSINESS_AS_OF=2026-09-28\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", fake_file)
    monkeypatch.setenv("APP_ENV", "development")
    # Exercise the actual runtime settings factory instead of the API fixture's
    # file-free override. Meta never constructs a provider request.
    app.dependency_overrides.pop(config.get_settings)
    response = api.get("/api/meta")
    assert response.status_code == 200 and response.json()["llm_available"] is True
    health = api.get("/health")
    assert health.status_code == 200
    assert "fictional-local-secret" not in response.text + health.text
    assert "recorded-local-model" not in response.text + health.text
