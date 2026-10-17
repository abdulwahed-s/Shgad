"""Typed domain failures using codes already defined in API_CONTRACT."""

from typing import Literal

ErrorCode = Literal[
    "MISSING_OPENING_BALANCE",
    "MISSING_COSTS",
    "AMBIGUOUS_DATE",
    "VALIDATION_ERROR",
    "MISSING_COUNT",
    "DIFFERENCE_SIGN_MISMATCH",
    "DIFFERENCE_EXCEEDED",
    "NOT_FOUND",
    "IMPORT_REJECTED",
    "MISSING_FORECAST_HISTORY",
    "MISSING_DUE_DATE",
]


class FinancialRuleError(ValueError):
    def __init__(self, code: ErrorCode, *, details: dict[str, object] | None = None):
        self.code = code
        self.message_key = f"error_{code.lower()}"
        self.details = details or {}
        super().__init__(code)
