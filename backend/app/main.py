"""Application entry point; Phase 0 exposes health only."""

from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(title="Shgad", version="0.1.0")
app.include_router(health_router)
