"""Application entry point for deterministic synthetic merchant workflows."""

from fastapi import FastAPI

from app.api.daily_close import router as daily_close_router
from app.api.entries import router as entries_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.ledger import router as ledger_router
from app.api.queries import router as queries_router
from app.api.reports import router as reports_router
from app.schemas.tools import ErrorResponse

app = FastAPI(
    title="Shgad",
    version="0.1.0",
    responses={
        status: {"model": ErrorResponse}
        for status in (400, 404, 405, 413, 415, 422, 500, 503)
    },
)
register_error_handlers(app)
app.include_router(health_router)
app.include_router(imports_router)
app.include_router(entries_router)
app.include_router(ledger_router)
app.include_router(daily_close_router)
app.include_router(queries_router)
app.include_router(reports_router)
