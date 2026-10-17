"""Small allowlisted inserts/atomic writes shared by deterministic ingestion."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.schemas.ledger import (
    ImportBatch,
    LedgerModel,
    Obligation,
    PaymentLink,
    RawImportRow,
    ReconciliationFlag,
    Transaction,
)

_TABLES = {
    ImportBatch: "import_batches",
    RawImportRow: "raw_import_rows",
    Transaction: "transactions",
    Obligation: "obligations",
    PaymentLink: "payment_links",
    ReconciliationFlag: "reconciliation_flags",
}


def insert_record(connection: sqlite3.Connection, record: LedgerModel) -> None:
    payload = record.model_dump(mode="json")
    columns = ", ".join(payload)
    values = ", ".join(f":{key}" for key in payload)
    connection.execute(
        f"INSERT INTO {_TABLES[type(record)]} ({columns}) VALUES ({values})", payload
    )


@contextmanager
def atomic_import(connection: sqlite3.Connection) -> Iterator[None]:
    nested = connection.in_transaction
    connection.execute("SAVEPOINT csv_import" if nested else "BEGIN IMMEDIATE")
    try:
        yield
        if nested:
            connection.execute("RELEASE SAVEPOINT csv_import")
        else:
            connection.commit()
    except BaseException:
        if nested:
            connection.execute("ROLLBACK TO SAVEPOINT csv_import")
            connection.execute("RELEASE SAVEPOINT csv_import")
        else:
            connection.rollback()
        raise
