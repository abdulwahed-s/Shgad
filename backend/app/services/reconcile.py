"""Read-only reconciliation and deterministic ingestion matching (§7.2/§10).

Exact party IDs remain identities. Name similarity can suggest candidates only.
This module never creates links, updates evidence or confirms a review decision.
"""

import json
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from app.schemas.evidence import FlagView
from app.schemas.forecast import Amount
from app.schemas.ledger import EventType, Transaction
from app.services.ledger_audit import read_ledger
from app.services.ledger_rules import active_transactions, outstanding_balance
from app.services.observed import OBSERVED_START, observed_day
from app.services.validation import parse_timestamp

_PAYMENTS = {EventType.CREDIT_COLLECTION, EventType.SUPPLIER_PAYMENT}


@dataclass(frozen=True)
class PaymentMatch:
    payment_source_id: str
    level: Literal["definite", "strong", "candidate", "unmatched"]
    obligation_id: str | None
    candidate_obligation_ids: tuple[str, ...]
    reason_key: str | None
    evidence_source_ids: tuple[str, ...]
    unallocated_iqd: int


@dataclass(frozen=True)
class ReconciliationReport:
    matches: tuple[PaymentMatch, ...]
    flags: tuple[FlagView, ...]


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).translate(
        str.maketrans("أإآىة", "ااايه")
    )
    return " ".join(
        "".join(c for c in text if not unicodedata.combining(c) and c != "ـ")
        .casefold()
        .split()
    )


def _similar(first, second):
    a, b = normalize_name(first), normalize_name(second)
    if not a or not b:
        return False
    matched = sum(
        block.size
        for block in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
    )
    # Similarity >= 4/5, using integer text lengths (no amount rounding/coercion).
    return 10 * matched >= 4 * (len(a) + len(b))


class _Context:
    def __init__(self, connection, *, clock, known_at):
        self.day, self.known = observed_day(clock), parse_timestamp(known_at)
        self.snapshot = read_ledger(connection, as_of=self.day, known_at=self.known)
        active = active_transactions(
            self.snapshot.transactions,
            as_of=self.day,
            voids=self.snapshot.voids,
            known_at=self.known,
        )
        self.rows = {r.transaction_id: r for r in active}
        self.known_rows = {r.transaction_id: r for r in self.snapshot.transactions}
        self.known_obligations = {o.obligation_id: o for o in self.snapshot.obligations}
        self.obligations = {
            o.obligation_id: o
            for o in self.snapshot.obligations
            if o.origin_transaction_id in self.rows
        }
        self.links = tuple(
            link
            for link in self.snapshot.payment_links
            if link.payment_transaction_id in self.rows
            and link.obligation_id in self.obligations
        )
        self.remaining = {
            key: outstanding_balance(
                o.original_amount_iqd,
                (link.amount_iqd for link in self.links if link.obligation_id == key),
            )
            for key, o in self.obligations.items()
        }
        self.names = {
            r["counterparty_id"]: r["display_name"]
            for r in connection.execute(
                "SELECT counterparty_id, display_name FROM counterparties"
            )
        }

    def evidence(self, row, obligations):
        references = tuple(obligations) + (
            (row.obligation_id,) if row.obligation_id else ()
        )
        return tuple(
            dict.fromkeys(
                [row.source_id]
                + [
                    self.known_rows[
                        self.known_obligations[key].origin_transaction_id
                    ].source_id
                    for key in references
                    if key in self.known_obligations
                ]
            )
        )


def _decide(context: _Context, row: Transaction) -> PaymentMatch:
    kind = "receivable" if row.type == EventType.CREDIT_COLLECTION else "payable"
    compatible = {
        key: o
        for key, o in context.obligations.items()
        if o.kind == kind
        and context.rows[o.origin_transaction_id].occurred_at <= row.occurred_at
    }

    def result(level, keys=(), reason=None, reference=None):
        keys = tuple(sorted(keys))
        return PaymentMatch(
            row.source_id,
            level,
            reference,
            keys,
            reason,
            context.evidence(row, keys),
            row.amount_iqd,
        )

    if row.obligation_id is not None:
        origin = compatible.get(row.obligation_id)
        if origin is None or origin.counterparty_id != row.counterparty_id:
            original = context.known_obligations.get(row.obligation_id)
            voided_origin = original is not None and any(
                audit.transaction_id == original.origin_transaction_id
                for audit in context.snapshot.voids
            )
            return result(
                "unmatched",
                reason="origin_voided" if voided_origin else "unmatched_payment",
            )
        if row.amount_iqd > context.remaining[row.obligation_id]:
            return result(
                "candidate",
                (row.obligation_id,),
                "payment_exceeds_outstanding",
                row.obligation_id,
            )
        return result("definite", (row.obligation_id,), reference=row.obligation_id)

    exact = {
        key: o
        for key, o in compatible.items()
        if o.counterparty_id == row.counterparty_id and context.remaining[key] > 0
    }
    if len(exact) == 1:
        key, obligation = next(iter(exact.items()))
        if row.amount_iqd > context.remaining[key]:
            return result("candidate", (key,), "payment_exceeds_outstanding")
        if obligation.due_date is None:
            return result("candidate", (key,), "missing_due_date")
        if abs((row.business_date - obligation.due_date).days) > 30:
            return result("candidate", (key,), "outside_due_window")
        return result("strong", (key,), reference=key)
    if exact:
        return result("candidate", exact, "ambiguous_obligations")
    candidates = [
        key
        for key, o in compatible.items()
        if context.remaining[key] > 0
        and _similar(
            context.names.get(row.counterparty_id, ""),
            context.names.get(o.counterparty_id, ""),
        )
    ]
    if candidates:
        return result("candidate", candidates, "similar_name_only")
    return result("unmatched", reason="unmatched_payment")


def match_payment(connection, row: Transaction, *, clock, known_at) -> PaymentMatch:
    return _decide(_Context(connection, clock=clock, known_at=known_at), row)


def _flag(flag_id, flag_type, reason, amount, sources, *, formula, basis):
    return FlagView(
        flag_id=flag_id,
        type=flag_type,
        reason_key=reason,
        amount=Amount(
            amount_iqd=amount,
            kind="flagged",
            label_key="reconciliation_amount",
            source_ids=sources,
            formula=formula,
        ),
        source_ids=sources,
        confidence_basis=basis,
        next_step_key="review",
    )


def reconciliation_report(connection, *, clock, known_at) -> ReconciliationReport:
    connection.execute("SAVEPOINT reconciliation_read")
    try:
        context = _Context(connection, clock=clock, known_at=known_at)
        matches, flags = [], []
        for row in context.rows.values():
            if row.type not in _PAYMENTS:
                continue
            links = [
                link
                for link in context.links
                if link.payment_transaction_id == row.transaction_id
            ]
            if links:
                keys = tuple(sorted({link.obligation_id for link in links}))
                level = (
                    "strong"
                    if all(link.match_basis == "strong" for link in links)
                    else "definite"
                )
                match = PaymentMatch(
                    row.source_id,
                    level,
                    keys[0] if len(keys) == 1 else None,
                    keys,
                    None,
                    context.evidence(row, keys),
                    row.amount_iqd - sum(link.amount_iqd for link in links),
                )
            else:
                # An invalid explicit reference remains in immutable raw evidence
                # after normalization deliberately leaves the payment unallocated.
                raw = connection.execute(
                    """SELECT row_json FROM raw_import_rows WHERE import_batch_id = ?
                    AND source_row = ?""",
                    (row.import_batch_id, row.source_row),
                ).fetchone()
                original = json.loads(raw[0])
                original = original.get("canonical", original)
                reference = original.get("obligation_id") or row.obligation_id
                match = _decide(
                    context, row.model_copy(update={"obligation_id": reference})
                )
            matches.append(match)
            if match.unallocated_iqd:
                reason = match.reason_key or "unallocated_payment"
                flags.append(
                    _flag(
                        f"RECON-{row.transaction_id}",
                        "ambiguous" if match.level == "candidate" else "unmatched",
                        reason,
                        match.unallocated_iqd,
                        match.evidence_source_ids,
                        formula="payment amount - active verified allocations",
                        basis=match.level,
                    )
                )
        for key, obligation in context.obligations.items():
            remaining = context.remaining[key]
            if not remaining:
                continue
            source = context.rows[obligation.origin_transaction_id].source_id
            sources = tuple(
                dict.fromkeys(
                    [source]
                    + [
                        context.rows[link.payment_transaction_id].source_id
                        for link in context.links
                        if link.obligation_id == key
                    ]
                )
            )
            if remaining < obligation.original_amount_iqd:
                flags.append(
                    _flag(
                        f"PARTIAL-{key}",
                        "partially_paid",
                        "partially_paid",
                        remaining,
                        sources,
                        formula="original amount - active verified allocations",
                        basis="verified_partial_allocations",
                    )
                )
            if obligation.due_date is not None and obligation.due_date < context.day:
                flags.append(
                    _flag(
                        f"OVERDUE-{key}",
                        "overdue",
                        "overdue",
                        remaining,
                        sources,
                        formula="original amount - active verified allocations",
                        basis="due_date_before_business_as_of",
                    )
                )
        for stored in connection.execute(
            """SELECT f.* FROM reconciliation_flags f JOIN transactions t
            ON t.transaction_id = f.transaction_id WHERE f.type = 'suspected_duplicate'
            AND t.business_date BETWEEN ? AND ? AND t.recorded_at <= ?
            AND t.occurred_at <= ? AND NOT EXISTS (SELECT 1 FROM entry_voids v
            WHERE v.transaction_id = t.transaction_id
            AND v.voided_at <= ?) ORDER BY f.flag_id""",
            (
                OBSERVED_START.isoformat(),
                context.day.isoformat(),
                context.known.isoformat(),
                context.known.isoformat(),
                context.known.isoformat(),
            ),
        ):
            row = context.rows[stored["transaction_id"]]
            peers = [
                r.source_id
                for r in context.rows.values()
                if r.type == row.type
                and r.amount_iqd == row.amount_iqd
                and r.counterparty_id == row.counterparty_id
                and r.business_date == row.business_date
            ]
            if len(peers) < 2:
                continue
            flags.append(
                _flag(
                    stored["flag_id"],
                    "suspected_duplicate",
                    stored["reason_key"],
                    row.amount_iqd,
                    tuple(dict.fromkeys(peers)),
                    formula="same amount, party and day on distinct source identities",
                    basis="same_amount_party_day",
                )
            )
        return ReconciliationReport(
            tuple(matches), tuple(sorted(flags, key=lambda flag: flag.flag_id))
        )
    finally:
        connection.execute("RELEASE SAVEPOINT reconciliation_read")
