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
