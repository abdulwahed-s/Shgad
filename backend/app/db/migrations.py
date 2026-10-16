"""Atomic, versioned SQLite schema for roadmap §5.2–5.3.

All SQL below is fixed application schema, never an agent or user argument.
Runtime row values must be supplied with sqlite3 parameters.
"""

import re
import sqlite3


def _date(column: str) -> str:
    return f"(length({column}) = 10 AND date({column}, '+0 days') IS {column})"


def _timestamp(column: str) -> str:
    return (
        f"({column} GLOB '????-??-??T??:??:??*+00:00' "
        f"AND substr({column}, -6) = '+00:00' "
        f"AND datetime({column}) IS NOT NULL "
        f"AND {_date(f'substr({column}, 1, 10)')})"
    )


def _json(column: str, kind: str) -> str:
    return (
        f"CASE WHEN json_valid({column}) THEN json_type({column}) = '{kind}' ELSE 0 END"
    )


_SCHEMA_V1 = f"""
CREATE TABLE import_batches (
    import_batch_id TEXT PRIMARY KEY NOT NULL CHECK (length(import_batch_id) > 0),
    source_system TEXT NOT NULL CHECK (source_system IN
        ('synthetic_csv', 'synthetic_wallet', 'synthetic_entry')),
    account_scope TEXT NOT NULL CHECK (account_scope = 'aggregate_cash'),
    file_sha256 TEXT NOT NULL CHECK
        (length(file_sha256) = 64 AND file_sha256 NOT GLOB '*[^0-9a-f]*'),
    imported_at TEXT NOT NULL CHECK ({_timestamp("imported_at")}),
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    accepted_count INTEGER NOT NULL CHECK (accepted_count >= 0),
    flagged_count INTEGER NOT NULL CHECK (flagged_count >= 0),
    rejected_count INTEGER NOT NULL CHECK (rejected_count >= 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'rejected')),
    CHECK (accepted_count <= row_count - flagged_count - rejected_count),
    CHECK (status = 'pending'
        OR accepted_count = row_count - flagged_count - rejected_count)
) STRICT;

CREATE TABLE raw_import_rows (
    raw_row_id TEXT PRIMARY KEY NOT NULL CHECK (length(raw_row_id) > 0),
    import_batch_id TEXT NOT NULL REFERENCES import_batches(import_batch_id),
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    row_json TEXT NOT NULL CHECK ({_json("row_json", "object")}),
    errors_json TEXT NOT NULL CHECK ({_json("errors_json", "array")}),
    status TEXT NOT NULL CHECK (status IN ('accepted', 'flagged', 'rejected')),
    UNIQUE (import_batch_id, source_row)
) STRICT;

CREATE TABLE counterparties (
    counterparty_id TEXT PRIMARY KEY NOT NULL CHECK (length(counterparty_id) > 0),
    display_name TEXT NOT NULL CHECK (length(display_name) > 0),
    kind TEXT NOT NULL CHECK (kind IN ('customer', 'supplier'))
) STRICT;

CREATE TABLE categories (
    category_id TEXT PRIMARY KEY NOT NULL CHECK (length(category_id) > 0),
    name TEXT NOT NULL CHECK (length(name) > 0),
    buy_price_iqd INTEGER CHECK (buy_price_iqd >= 0),
    sell_price_iqd INTEGER CHECK (sell_price_iqd > 0)
) STRICT;

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY NOT NULL CHECK (length(transaction_id) > 0),
    source_id TEXT NOT NULL CHECK (length(source_id) > 0),
    source_system TEXT NOT NULL CHECK (source_system IN
        ('synthetic_csv', 'synthetic_wallet', 'synthetic_entry')),
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    import_batch_id TEXT NOT NULL REFERENCES import_batches(import_batch_id),
    occurred_at TEXT NOT NULL CHECK ({_timestamp("occurred_at")}),
    business_date TEXT NOT NULL CHECK ({_date("business_date")}),
    type TEXT NOT NULL CHECK (type IN ('CASH_SALE', 'CREDIT_SALE', 'CREDIT_COLLECTION',
        'SUPPLIER_INVOICE', 'SUPPLIER_PAYMENT', 'OPERATING_EXPENSE',
        'DAILY_CASH_COUNT', 'OWNER_DRAWING')),
    amount_iqd INTEGER NOT NULL CHECK (amount_iqd > 0),
    counterparty_id TEXT REFERENCES counterparties(counterparty_id),
    obligation_id TEXT REFERENCES obligations(obligation_id)
        DEFERRABLE INITIALLY DEFERRED,
    due_date TEXT CHECK (due_date IS NULL OR {_date("due_date")}),
    category_id TEXT REFERENCES categories(category_id),
    quantity INTEGER CHECK (quantity > 0),
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('valid', 'flagged')),
    idempotency_key TEXT NOT NULL UNIQUE CHECK (length(idempotency_key) > 0),
    UNIQUE (source_system, source_id),
    UNIQUE (import_batch_id, source_row),
    FOREIGN KEY (import_batch_id, source_row)
        REFERENCES raw_import_rows(import_batch_id, source_row),
    CHECK (business_date IS date(occurred_at, '+3 hours')),
    CHECK (type NOT IN ('CREDIT_SALE', 'CREDIT_COLLECTION', 'SUPPLIER_INVOICE',
        'SUPPLIER_PAYMENT') OR counterparty_id IS NOT NULL),
    CHECK (type NOT IN ('CREDIT_SALE', 'SUPPLIER_INVOICE')
        OR obligation_id IS NOT NULL),
    CHECK (type NOT IN ('CREDIT_COLLECTION', 'SUPPLIER_PAYMENT')
        OR obligation_id IS NOT NULL OR status = 'flagged'),
    CHECK (type IN ('CREDIT_SALE', 'CREDIT_COLLECTION', 'SUPPLIER_INVOICE',
        'SUPPLIER_PAYMENT') OR obligation_id IS NULL),
    CHECK (type IN ('CREDIT_SALE', 'SUPPLIER_INVOICE') OR due_date IS NULL),
    CHECK ((category_id IS NULL) = (quantity IS NULL)),
    CHECK (type IN ('CASH_SALE', 'CREDIT_SALE') OR category_id IS NULL)
) STRICT;

CREATE TABLE obligations (
    obligation_id TEXT PRIMARY KEY NOT NULL CHECK (length(obligation_id) > 0),
    kind TEXT NOT NULL CHECK (kind IN ('receivable', 'payable')),
    origin_transaction_id TEXT NOT NULL UNIQUE REFERENCES transactions(transaction_id)
        DEFERRABLE INITIALLY DEFERRED,
    counterparty_id TEXT NOT NULL REFERENCES counterparties(counterparty_id),
    original_amount_iqd INTEGER NOT NULL CHECK (original_amount_iqd > 0),
    due_date TEXT CHECK (due_date IS NULL OR {_date("due_date")})
) STRICT;

CREATE TABLE payment_links (
    payment_link_id TEXT PRIMARY KEY NOT NULL CHECK (length(payment_link_id) > 0),
    payment_transaction_id TEXT NOT NULL REFERENCES transactions(transaction_id),
    obligation_id TEXT NOT NULL REFERENCES obligations(obligation_id),
    amount_iqd INTEGER NOT NULL CHECK (amount_iqd > 0),
    match_basis TEXT NOT NULL CHECK
        (match_basis IN ('definite', 'strong', 'confirmed')),
    created_at TEXT NOT NULL CHECK ({_timestamp("created_at")}),
    UNIQUE (payment_transaction_id, obligation_id)
) STRICT;

CREATE TABLE opening_balances (
    opening_balance_id TEXT PRIMARY KEY NOT NULL CHECK (length(opening_balance_id) > 0),
    source_id TEXT NOT NULL CHECK (length(source_id) > 0),
    source_system TEXT NOT NULL CHECK (source_system IN
        ('synthetic_csv', 'synthetic_wallet', 'synthetic_entry')),
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    import_batch_id TEXT NOT NULL REFERENCES import_batches(import_batch_id),
    business_date TEXT NOT NULL CHECK ({_date("business_date")}),
    account TEXT NOT NULL CHECK (account = 'aggregate_cash'),
    amount_iqd INTEGER NOT NULL CHECK (amount_iqd >= 0),
    UNIQUE (account, business_date),
    UNIQUE (source_system, source_id),
    UNIQUE (import_batch_id, source_row),
    FOREIGN KEY (import_batch_id, source_row)
        REFERENCES raw_import_rows(import_batch_id, source_row)
) STRICT;

CREATE TABLE reconciliation_flags (
    flag_id TEXT PRIMARY KEY NOT NULL CHECK (length(flag_id) > 0),
    type TEXT NOT NULL CHECK (type IN
        ('unmatched', 'suspected_duplicate', 'partially_paid', 'overdue', 'ambiguous')),
    reason_key TEXT NOT NULL CHECK (length(reason_key) > 0),
    amount_iqd INTEGER CHECK (amount_iqd >= 0),
    transaction_id TEXT REFERENCES transactions(transaction_id),
    obligation_id TEXT REFERENCES obligations(obligation_id),
    raw_row_id TEXT REFERENCES raw_import_rows(raw_row_id),
    confidence_basis TEXT NOT NULL,
    next_step_key TEXT NOT NULL CHECK (next_step_key IN ('review', 'provide_details')),
    CHECK (transaction_id IS NOT NULL OR obligation_id IS NOT NULL
        OR raw_row_id IS NOT NULL)
) STRICT;

CREATE TABLE agent_runs (
    run_id TEXT PRIMARY KEY NOT NULL CHECK (length(run_id) > 0),
    started_at TEXT NOT NULL CHECK ({_timestamp("started_at")}),
    completed_at TEXT CHECK (completed_at IS NULL OR {_timestamp("completed_at")}),
    status TEXT NOT NULL CHECK (status IN ('completed', 'error')),
    model_id TEXT,
    prompt_version TEXT,
    error_code TEXT
) STRICT;

CREATE TABLE tool_calls (
    tool_call_id TEXT PRIMARY KEY NOT NULL CHECK (length(tool_call_id) > 0),
    run_id TEXT NOT NULL REFERENCES agent_runs(run_id),
    tool_name TEXT NOT NULL CHECK (tool_name IN
        ('get_sales', 'get_debts', 'reconcile', 'forecast', 'get_margin')),
    started_at TEXT NOT NULL CHECK ({_timestamp("started_at")}),
    completed_at TEXT CHECK (completed_at IS NULL OR {_timestamp("completed_at")}),
    ok INTEGER NOT NULL CHECK (ok IN (0, 1)),
    error_code TEXT,
    sanitized_arguments_json TEXT NOT NULL
        CHECK ({_json("sanitized_arguments_json", "object")}),
    sanitized_result_json TEXT NOT NULL
        CHECK ({_json("sanitized_result_json", "object")})
) STRICT;

CREATE TRIGGER batch_provenance_immutable BEFORE UPDATE OF
    import_batch_id, source_system, account_scope, file_sha256, imported_at, row_count
ON import_batches
BEGIN SELECT RAISE(ABORT, 'batch provenance is immutable'); END;

CREATE TRIGGER batch_delete_immutable BEFORE DELETE ON import_batches
BEGIN SELECT RAISE(ABORT, 'batch provenance is immutable'); END;

CREATE TRIGGER transaction_provenance BEFORE INSERT ON transactions
WHEN NOT EXISTS (
    SELECT 1 FROM import_batches b JOIN raw_import_rows r USING (import_batch_id)
    WHERE b.import_batch_id = NEW.import_batch_id
        AND b.source_system = NEW.source_system
        AND r.source_row = NEW.source_row AND r.status IN ('accepted', 'flagged')
)
BEGIN SELECT RAISE(ABORT, 'transaction requires accepted synthetic raw evidence'); END;

CREATE TRIGGER opening_provenance BEFORE INSERT ON opening_balances
WHEN NOT EXISTS (
    SELECT 1 FROM import_batches b JOIN raw_import_rows r USING (import_batch_id)
    WHERE b.import_batch_id = NEW.import_batch_id
        AND b.source_system = NEW.source_system
        AND r.source_row = NEW.source_row AND r.status IN ('accepted', 'flagged')
)
BEGIN
    SELECT RAISE(ABORT, 'opening balance requires accepted synthetic raw evidence');
END;

CREATE TRIGGER transaction_counterparty BEFORE INSERT ON transactions
WHEN NEW.type IN ('CREDIT_SALE', 'CREDIT_COLLECTION',
    'SUPPLIER_INVOICE', 'SUPPLIER_PAYMENT')
    AND NOT EXISTS (
        SELECT 1 FROM counterparties c WHERE c.counterparty_id = NEW.counterparty_id
        AND c.kind = CASE WHEN NEW.type IN ('CREDIT_SALE', 'CREDIT_COLLECTION')
            THEN 'customer' ELSE 'supplier' END
    )
BEGIN SELECT RAISE(ABORT, 'event requires the correct counterparty kind'); END;

CREATE TRIGGER origin_reference BEFORE INSERT ON transactions
WHEN NEW.type IN ('CREDIT_SALE', 'SUPPLIER_INVOICE')
    AND EXISTS (SELECT 1 FROM obligations WHERE obligation_id = NEW.obligation_id)
BEGIN SELECT RAISE(ABORT, 'obligation already has an originating event'); END;

CREATE TRIGGER payment_reference BEFORE INSERT ON transactions
WHEN NEW.type IN ('CREDIT_COLLECTION', 'SUPPLIER_PAYMENT')
    AND NEW.obligation_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM obligations o WHERE o.obligation_id = NEW.obligation_id
        AND o.counterparty_id = NEW.counterparty_id
        AND o.kind = CASE WHEN NEW.type = 'CREDIT_COLLECTION'
            THEN 'receivable' ELSE 'payable' END
    )
BEGIN SELECT RAISE(ABORT, 'payment reference must match an existing obligation'); END;

CREATE TRIGGER obligation_origin BEFORE INSERT ON obligations
WHEN NOT EXISTS (
    SELECT 1 FROM transactions t JOIN counterparties c USING (counterparty_id)
    WHERE t.transaction_id = NEW.origin_transaction_id
        AND t.obligation_id = NEW.obligation_id
        AND t.counterparty_id = NEW.counterparty_id
        AND t.amount_iqd = NEW.original_amount_iqd AND t.due_date IS NEW.due_date
        AND t.type = CASE WHEN NEW.kind = 'receivable'
            THEN 'CREDIT_SALE' ELSE 'SUPPLIER_INVOICE' END
        AND c.kind = CASE WHEN NEW.kind = 'receivable'
            THEN 'customer' ELSE 'supplier' END
)
BEGIN SELECT RAISE(ABORT, 'obligation must match its originating event'); END;

CREATE TRIGGER payment_link_identity BEFORE INSERT ON payment_links
WHEN NOT EXISTS (
    SELECT 1 FROM transactions p
        JOIN obligations o ON o.obligation_id = NEW.obligation_id
        JOIN transactions origin ON origin.transaction_id = o.origin_transaction_id
    WHERE p.transaction_id = NEW.payment_transaction_id
        AND p.counterparty_id = o.counterparty_id
        AND p.type = CASE WHEN o.kind = 'receivable'
            THEN 'CREDIT_COLLECTION' ELSE 'SUPPLIER_PAYMENT' END
        AND p.occurred_at >= origin.occurred_at
)
BEGIN
    SELECT RAISE(ABORT, 'link requires matching type, counterparty and chronology');
END;

CREATE TRIGGER payment_link_overallocation BEFORE INSERT ON payment_links
WHEN NEW.amount_iqd > (
        SELECT amount_iqd - COALESCE((SELECT SUM(amount_iqd) FROM payment_links
            WHERE payment_transaction_id = NEW.payment_transaction_id), 0)
        FROM transactions WHERE transaction_id = NEW.payment_transaction_id
    ) OR NEW.amount_iqd > (
        SELECT original_amount_iqd - COALESCE((SELECT SUM(amount_iqd) FROM payment_links
            WHERE obligation_id = NEW.obligation_id), 0)
        FROM obligations WHERE obligation_id = NEW.obligation_id
    )
BEGIN SELECT RAISE(ABORT, 'payment overallocation or obligation overpayment'); END;

CREATE TRIGGER counterparty_kind_immutable BEFORE UPDATE OF kind ON counterparties
BEGIN SELECT RAISE(ABORT, 'counterparty kind is immutable'); END;

CREATE INDEX transactions_business_date_type ON transactions(business_date, type);
CREATE INDEX transactions_counterparty ON transactions(counterparty_id);
CREATE INDEX obligations_kind_due ON obligations(kind, due_date);
CREATE INDEX obligations_counterparty ON obligations(counterparty_id);
CREATE INDEX payment_links_obligation ON payment_links(obligation_id);
CREATE INDEX flags_transaction ON reconciliation_flags(transaction_id);
CREATE INDEX flags_obligation ON reconciliation_flags(obligation_id);
CREATE INDEX tool_calls_run ON tool_calls(run_id);
"""

# Source facts and verified allocations are append-only. Corrections require a
# later explicit audit workflow rather than overwriting the original evidence.
for _table in (
    "raw_import_rows",
    "transactions",
    "obligations",
    "payment_links",
    "opening_balances",
    "categories",
):
    for _operation in ("UPDATE", "DELETE"):
        _SCHEMA_V1 += f"""
CREATE TRIGGER {_table}_immutable_{_operation.lower()} BEFORE {_operation} ON {_table}
BEGIN SELECT RAISE(ABORT, '{_table} is immutable'); END;
"""

# Preserve the historical v1 definition. Reuse its exact constraints and guards
# for the v2 table rebuild, adding only the revised vocabulary and provenance.
_v1_transaction_body = _SCHEMA_V1.split("CREATE TABLE transactions (", 1)[1].split(
    ") STRICT;", 1
)[0]
_v2_transaction_body = _v1_transaction_body.replace(
    "'DAILY_CASH_COUNT', 'OWNER_DRAWING'",
    "'DAILY_CASH_COUNT', 'OWNER_DRAWING', 'CAPITAL_INJECTION'",
).replace(
    "    UNIQUE (source_system, source_id),",
    f"""    source TEXT NOT NULL DEFAULT 'synthetic_csv' CHECK
        (source IN ('synthetic_csv', 'manual_entry', 'daily_close_review')),
    client_entry_id TEXT UNIQUE CHECK (client_entry_id IS NULL OR
        length(client_entry_id) > 0),
    recorded_at TEXT NOT NULL CHECK ({_timestamp("recorded_at")}),
    UNIQUE (transaction_id, source_id),
    CHECK (source != 'daily_close_review' OR (
        source_system = 'synthetic_entry' AND client_entry_id IS NOT NULL
        AND type IN ('CASH_SALE', 'CAPITAL_INJECTION', 'OPERATING_EXPENSE',
        'OWNER_DRAWING')
        AND category_id IS NULL)),
    UNIQUE (source_system, source_id),""",
)
_v1_triggers = re.findall(r"CREATE TRIGGER (\w+).*?END;", _SCHEMA_V1, re.DOTALL)
_SCHEMA_V2 = "\n".join(f"DROP TRIGGER IF EXISTS {name};" for name in _v1_triggers)
_SCHEMA_V2 += f"""
CREATE TABLE transactions_new ({_v2_transaction_body}) STRICT;
INSERT INTO transactions_new
SELECT t.*, CASE WHEN t.source_system = 'synthetic_entry' THEN 'manual_entry'
    ELSE 'synthetic_csv' END, NULL, b.imported_at
FROM transactions t JOIN import_batches b USING (import_batch_id);
DROP TABLE transactions;
ALTER TABLE transactions_new RENAME TO transactions;
"""
_SCHEMA_V2 += "\n".join(re.findall(r"CREATE TRIGGER \w+.*?END;", _SCHEMA_V1, re.DOTALL))
_SCHEMA_V2 += "\n".join(
    re.findall(r"CREATE INDEX \w+ ON transactions[^;]+;", _SCHEMA_V1)
)
_SCHEMA_V2 += f"""
CREATE TABLE entry_voids (
    void_id TEXT PRIMARY KEY NOT NULL CHECK (length(void_id) > 0),
    transaction_id TEXT NOT NULL UNIQUE,
    source_id TEXT NOT NULL,
    client_entry_id TEXT NOT NULL UNIQUE CHECK (length(client_entry_id) > 0),
    reason TEXT NOT NULL CHECK (length(trim(reason,
        char(9)||char(10)||char(13)||' ')) > 0),
    voided_at TEXT NOT NULL CHECK ({_timestamp("voided_at")}),
    FOREIGN KEY (transaction_id, source_id) REFERENCES
        transactions(transaction_id, source_id)
) STRICT;

CREATE TRIGGER void_chronology BEFORE INSERT ON entry_voids
WHEN EXISTS (SELECT 1 FROM transactions t WHERE t.transaction_id = NEW.transaction_id
    AND (NEW.voided_at < t.occurred_at OR NEW.voided_at < t.recorded_at))
BEGIN SELECT RAISE(ABORT, 'void cannot precede its original evidence'); END;

CREATE TABLE difference_reviews (
    review_id TEXT PRIMARY KEY NOT NULL CHECK (length(review_id) > 0),
    client_entry_id TEXT NOT NULL UNIQUE CHECK (length(client_entry_id) > 0),
    business_date TEXT NOT NULL CHECK ({_date("business_date")}),
    resolution TEXT NOT NULL CHECK (resolution IN ('cash_sale_unitemized',
        'capital_injection', 'expense_unrecorded', 'owner_drawing_unrecorded',
        'leave_unexplained')),
    amount_iqd INTEGER CHECK (amount_iqd > 0),
    note TEXT,
    created_at TEXT NOT NULL CHECK ({_timestamp("created_at")}),
    previous_count_transaction_id TEXT NOT NULL REFERENCES transactions(transaction_id),
    closing_count_transaction_id TEXT NOT NULL REFERENCES transactions(transaction_id),
    transaction_id TEXT UNIQUE REFERENCES transactions(transaction_id),
    CHECK ((resolution = 'leave_unexplained' AND amount_iqd IS NULL AND
        transaction_id IS NULL)
        OR (resolution != 'leave_unexplained' AND amount_iqd IS NOT NULL AND
        transaction_id IS NOT NULL))
) STRICT;

CREATE TRIGGER review_counts BEFORE INSERT ON difference_reviews
WHEN NOT EXISTS (
    SELECT 1 FROM transactions c, transactions p
    WHERE c.transaction_id = NEW.closing_count_transaction_id
    AND p.transaction_id = NEW.previous_count_transaction_id
    AND c.type = 'DAILY_CASH_COUNT' AND p.type = 'DAILY_CASH_COUNT'
    AND c.business_date = NEW.business_date
    AND p.business_date = date(NEW.business_date, '-1 day')
    AND c.recorded_at <= NEW.created_at AND p.recorded_at <= NEW.created_at
    AND c.occurred_at <= NEW.created_at AND p.occurred_at <= NEW.created_at
    AND NOT EXISTS (SELECT 1 FROM entry_voids v WHERE
        v.transaction_id IN (c.transaction_id, p.transaction_id) AND v.voided_at
        <= NEW.created_at)
    AND NOT EXISTS (SELECT 1 FROM transactions later
        WHERE later.type = 'DAILY_CASH_COUNT' AND later.recorded_at <= NEW.created_at
        AND later.occurred_at <= NEW.created_at
        AND ((later.business_date = c.business_date AND later.transaction_id !=
        c.transaction_id AND later.occurred_at >= c.occurred_at)
            OR (later.business_date = p.business_date AND later.transaction_id
        != p.transaction_id AND later.occurred_at >= p.occurred_at))
        AND NOT EXISTS (SELECT 1 FROM entry_voids v WHERE v.transaction_id =
        later.transaction_id AND v.voided_at <= NEW.created_at))
)
BEGIN SELECT RAISE(ABORT, 'MISSING_COUNT'); END;

CREATE TRIGGER review_created_entry BEFORE INSERT ON difference_reviews
WHEN NEW.resolution != 'leave_unexplained' AND NOT EXISTS (
    SELECT 1 FROM transactions t JOIN transactions c
        ON c.transaction_id = NEW.closing_count_transaction_id
    WHERE t.transaction_id = NEW.transaction_id AND t.client_entry_id =
        NEW.client_entry_id
    AND t.source = 'daily_close_review' AND t.source_system = 'synthetic_entry'
    AND t.business_date = NEW.business_date AND t.occurred_at = c.occurred_at
    AND t.recorded_at = NEW.created_at AND t.amount_iqd = NEW.amount_iqd
    AND t.category_id IS NULL AND t.description = COALESCE(NEW.note, '')
    AND t.type = CASE NEW.resolution WHEN 'cash_sale_unitemized' THEN 'CASH_SALE'
        WHEN 'capital_injection' THEN 'CAPITAL_INJECTION'
        WHEN 'expense_unrecorded' THEN 'OPERATING_EXPENSE'
        WHEN 'owner_drawing_unrecorded' THEN 'OWNER_DRAWING' END
    AND NOT EXISTS (SELECT 1 FROM entry_voids v WHERE v.transaction_id =
        t.transaction_id AND v.voided_at <= NEW.created_at)
)
BEGIN SELECT RAISE(ABORT, 'review must match its created entry'); END;
"""

# Reconstruct the pre-review residual from active recorded events. The created
# row is already in the transaction, so omit it from this validation sum only.
_review_remaining = """(
    SELECT c.amount_iqd - p.amount_iqd - COALESCE((
        SELECT SUM(CASE WHEN t.type IN ('CASH_SALE', 'CREDIT_COLLECTION',
        'CAPITAL_INJECTION') THEN t.amount_iqd
            WHEN t.type IN ('SUPPLIER_PAYMENT', 'OPERATING_EXPENSE',
        'OWNER_DRAWING') THEN -t.amount_iqd ELSE 0 END)
        FROM transactions t WHERE t.business_date = NEW.business_date
        AND t.transaction_id IS NOT NEW.transaction_id AND t.recorded_at <=
        NEW.created_at
        AND t.occurred_at <= NEW.created_at
        AND NOT EXISTS (SELECT 1 FROM entry_voids v WHERE v.transaction_id =
        t.transaction_id AND v.voided_at <= NEW.created_at)
    ), 0) FROM transactions c, transactions p
    WHERE c.transaction_id = NEW.closing_count_transaction_id
    AND p.transaction_id = NEW.previous_count_transaction_id
)"""
_SCHEMA_V2 += f"""
CREATE TRIGGER review_sign BEFORE INSERT ON difference_reviews
WHEN NEW.resolution != 'leave_unexplained' AND (
    ({_review_remaining} > 0 AND NEW.resolution NOT IN ('cash_sale_unitemized',
        'capital_injection'))
    OR ({_review_remaining} < 0 AND NEW.resolution NOT IN ('expense_unrecorded',
        'owner_drawing_unrecorded')))
BEGIN SELECT RAISE(ABORT, 'DIFFERENCE_SIGN_MISMATCH'); END;

CREATE TRIGGER review_remaining_amount BEFORE INSERT ON difference_reviews
WHEN NEW.resolution != 'leave_unexplained' AND NEW.amount_iqd > abs({_review_remaining})
BEGIN SELECT RAISE(ABORT, 'DIFFERENCE_EXCEEDED'); END;

DROP TRIGGER payment_link_identity;
CREATE TRIGGER payment_link_identity BEFORE INSERT ON payment_links
WHEN NOT EXISTS (
    SELECT 1 FROM transactions p JOIN obligations o ON o.obligation_id =
        NEW.obligation_id
    JOIN transactions origin ON origin.transaction_id = o.origin_transaction_id
    WHERE p.transaction_id = NEW.payment_transaction_id AND p.counterparty_id =
        o.counterparty_id
    AND p.type = CASE WHEN o.kind = 'receivable' THEN 'CREDIT_COLLECTION' ELSE
        'SUPPLIER_PAYMENT' END
    AND p.occurred_at >= origin.occurred_at
    AND p.occurred_at <= NEW.created_at AND origin.occurred_at <= NEW.created_at
    AND p.recorded_at <= NEW.created_at AND origin.recorded_at <= NEW.created_at
    AND NOT EXISTS (SELECT 1 FROM entry_voids v WHERE v.transaction_id IN
        (p.transaction_id, origin.transaction_id)
        AND v.voided_at <= NEW.created_at)
)
BEGIN
    SELECT RAISE(ABORT, 'link requires active type, counterparty and chronology');
END;

DROP TRIGGER payment_link_overallocation;
CREATE TRIGGER payment_link_overallocation BEFORE INSERT ON payment_links
WHEN NEW.amount_iqd > (
    SELECT p.amount_iqd - COALESCE((SELECT SUM(l.amount_iqd) FROM payment_links l
        WHERE l.payment_transaction_id = p.transaction_id), 0)
    FROM transactions p WHERE p.transaction_id = NEW.payment_transaction_id
) OR NEW.amount_iqd > (
    SELECT o.original_amount_iqd - COALESCE((SELECT SUM(l.amount_iqd)
        FROM payment_links l JOIN transactions p ON p.transaction_id =
        l.payment_transaction_id
        WHERE l.obligation_id = o.obligation_id
        AND NOT EXISTS (SELECT 1 FROM entry_voids v WHERE v.transaction_id =
        p.transaction_id
            AND v.voided_at <= NEW.created_at)), 0)
    FROM obligations o WHERE o.obligation_id = NEW.obligation_id
)
BEGIN SELECT RAISE(ABORT, 'payment overallocation or obligation overpayment'); END;

CREATE INDEX entry_voids_cutoff ON entry_voids(voided_at);
CREATE INDEX difference_reviews_date ON difference_reviews(business_date, created_at);
CREATE INDEX transactions_recorded_at ON transactions(recorded_at);
"""
for _table in ("entry_voids", "difference_reviews"):
    for _operation in ("UPDATE", "DELETE"):
        _SCHEMA_V2 += f"""
CREATE TRIGGER {_table}_immutable_{_operation.lower()} BEFORE {_operation} ON {_table}
BEGIN SELECT RAISE(ABORT, '{_table} is immutable'); END;
"""

_MIGRATIONS = (_SCHEMA_V1, _SCHEMA_V2)


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Upgrade atomically, without committing or rolling back a caller's work."""
    if connection.in_transaction:
        raise ValueError("Apply migrations before starting a data transaction")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > len(_MIGRATIONS):
        raise ValueError("Database schema is newer than this application")
    if version == len(_MIGRATIONS):
        return
    # SQLite's documented table-rebuild sequence requires FK enforcement off
    # before BEGIN. Validate every FK before committing and restore enforcement
    # on both success and failure. No caller transaction is ever disturbed.
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        for index in range(version, len(_MIGRATIONS)):
            statement = ""
            for character in _MIGRATIONS[index]:
                statement += character
                if character == ";" and sqlite3.complete_statement(statement):
                    connection.execute(statement)
                    statement = ""
            if statement.strip():
                raise sqlite3.DatabaseError("Incomplete migration statement")
            connection.execute(f"PRAGMA user_version = {index + 1}")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise sqlite3.IntegrityError("Migration foreign key check failed")
        connection.commit()
    except sqlite3.DatabaseError:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
