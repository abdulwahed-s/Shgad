"""Cooperative wall-clock budget for bounded CSV parsing and atomic imports."""

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import monotonic

from app.services.errors import FinancialRuleError

MAX_PROCESSING_SECONDS = 10
_deadline = ContextVar("import_deadline", default=None)
_guarded = ContextVar("import_connections", default=())


def checkpoint():
    deadline = _deadline.get()
    if deadline is not None and monotonic() >= deadline:
        raise FinancialRuleError(
            "IMPORT_REJECTED", details={"reason": "PROCESSING_TIMEOUT"}
        )


@contextmanager
def import_budget():
    token = None
    if _deadline.get() is None:
        token = _deadline.set(monotonic() + MAX_PROCESSING_SECONDS)
    try:
        checkpoint()
        yield
    finally:
        if token is not None:
            _deadline.reset(token)


def bounded_import(function):
    @wraps(function)
    def bounded(*args, **kwargs):
        with import_budget():
            connection = (
                args[0] if args and isinstance(args[0], sqlite3.Connection) else None
            )
            if (
                connection is None
                or connection in _guarded.get()
                or connection.in_transaction
            ):
                # SQLITE_INTERRUPT during DML rolls back the entire transaction.
                # Nested service callers retain their parent work and use the
                # parser/per-row/precommit checkpoints instead. HTTP imports own
                # their outer transaction and retain VM interruption as well.
                return function(*args, **kwargs)
            timed_out = False

            def interrupt():
                nonlocal timed_out
                if monotonic() >= _deadline.get():
                    timed_out = True
                    # Rollback must be allowed to run after the interrupted SQL.
                    connection.set_progress_handler(None, 0)
                    return 1
                return 0

            token = _guarded.set((*_guarded.get(), connection))
            connection.set_progress_handler(interrupt, 1000)
            try:
                return function(*args, **kwargs)
            except sqlite3.OperationalError:
                if timed_out:
                    raise FinancialRuleError(
                        "IMPORT_REJECTED", details={"reason": "PROCESSING_TIMEOUT"}
                    ) from None
                raise
            finally:
                connection.set_progress_handler(None, 0)
                _guarded.reset(token)

    return bounded
