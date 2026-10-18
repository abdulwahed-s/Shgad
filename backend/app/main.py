"""Application entry point for deterministic synthetic merchant workflows."""

from fastapi import FastAPI

from app.api.entries import router as entries_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.imports import router as imports_router

app = FastAPI(title="Shgad", version="0.1.0")
register_error_handlers(app)
app.include_router(health_router)
app.include_router(imports_router)
app.include_router(entries_router)
