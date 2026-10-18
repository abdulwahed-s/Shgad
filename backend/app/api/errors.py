"""Sanitized API_CONTRACT error envelopes; untrusted input is never echoed."""

import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas.tools import ErrorDetail, ErrorResponse
from app.services.errors import FinancialRuleError


def _error(code, status, details=None):
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(
            error=ErrorDetail(
                code=code, message_key=f"error_{code.lower()}", details=details or {}
            )
        ).model_dump(mode="json"),
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FinancialRuleError)
    async def financial_error(request: Request, exc: FinancialRuleError):
        status = 404 if exc.code == "NOT_FOUND" else 422
        if exc.code in {"INTERNAL", "LLM_UNAVAILABLE"}:
            status = 503 if exc.code == "LLM_UNAVAILABLE" else 500
        return _error(exc.code, status, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return _error("VALIDATION_ERROR", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "VALIDATION_ERROR"
        return _error(code, exc.status_code)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exc: sqlite3.Error):
        return _error("INTERNAL", 500)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        return _error("INTERNAL", 500)
