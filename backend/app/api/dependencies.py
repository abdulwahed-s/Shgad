"""Request-scoped SQLite, business clock and explicit audit time boundaries."""

import sqlite3
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings
from app.db.connection import connect_database
from app.db.migrations import apply_migrations
from app.services.business_clock import BusinessClock
from app.services.csv_mapping import UnavailableMappingProposer
from app.services.errors import FinancialRuleError
from app.services.observed import observed_day


def audit_timestamp() -> datetime:
    # Wall time belongs at the HTTP boundary, never in financial domain logic.
    return datetime.now(UTC)


def mapping_model():
    return UnavailableMappingProposer()


def business_clock(
    settings: Annotated[Settings, Depends(get_settings)],
) -> BusinessClock:
    clock = BusinessClock.from_settings(settings)
    observed_day(clock)
    return clock


async def database(settings: Annotated[Settings, Depends(get_settings)]):
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        raise FinancialRuleError("INTERNAL")
    connection = connect_database(settings.database_url.removeprefix(prefix))
    try:
        apply_migrations(connection)
        yield connection
    finally:
        connection.close()


Database = Annotated[sqlite3.Connection, Depends(database)]
Clock = Annotated[BusinessClock, Depends(business_clock)]
AuditTime = Annotated[datetime, Depends(audit_timestamp)]
