"""Application entry point for deterministic synthetic merchant workflows."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.daily_close import router as daily_close_router
from app.api.demo import router as demo_router
from app.api.entries import router as entries_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.ledger import router as ledger_router
from app.api.queries import router as queries_router
from app.api.reports import router as reports_router
from app.api.request_safety import RequestSafety
from app.api.source_evidence import router as source_evidence_router
from app.schemas.tools import ErrorResponse

app = FastAPI(
    title="Shgad",
    version="0.1.0",
    responses={
        status: {"model": ErrorResponse}
        for status in (400, 403, 404, 405, 408, 413, 415, 422, 429, 500, 503)
    },
)
app.add_middleware(RequestSafety)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(?:localhost|127\.0\.0\.1)(?::[0-9]+)?",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
register_error_handlers(app)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(imports_router)
app.include_router(entries_router)
app.include_router(ledger_router)
app.include_router(daily_close_router)
app.include_router(queries_router)
app.include_router(reports_router)
app.include_router(source_evidence_router)
app.include_router(demo_router)
