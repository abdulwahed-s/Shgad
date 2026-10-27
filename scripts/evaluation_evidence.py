"""Independent observed-query evidence for the separately frozen v2 method.

No application imports. Only this evaluator constructs IndependentZero after
selecting active rows from its own truth ledger and checking package coverage.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, timedelta

from scripts.make_ground_truth import TruthError, cutoff, stamp

METHOD_V1 = "row_provenance_v1"
METHOD_V2 = "observed_query_evidence_v2_D56"
EVENTS = {
    "cash_sales": ("CASH_SALE",),
    "credit_sales": ("CREDIT_SALE",),
    "total_sales": ("CASH_SALE", "CREDIT_SALE"),
    "weekly.collections": ("CREDIT_COLLECTION",),
    "weekly.supplier_payments": ("SUPPLIER_PAYMENT",),
    "weekly.operating_expenses": ("OPERATING_EXPENSE",),
    "weekly.owner_drawings": ("OWNER_DRAWING",),
    "weekly.capital_injections": ("CAPITAL_INJECTION",),
}


@dataclass(frozen=True)
class IndependentZero:
    query_json: str


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sales_tool(evidence, expected):
    """D58: the reconcile audit view runs the identical collections event query."""
    if (
        isinstance(evidence, dict)
        and evidence.get("tool") == "reconcile"
        and expected.get("label") == "collections"
    ):
        return evidence | {"tool": "get_sales"}
    return evidence


def zero_supported(expected, claim):
    proof = expected.get("independent_zero")
    if type(proof) is not IndependentZero:
        return False
    try:
        return (
            type(claim.get("value")) is int
            and claim["value"] == expected["value"] == 0
            and claim.get("source_ids") == expected["source_ids"] == []
            and canonical(_sales_tool(claim.get("query_evidence"), expected))
            == proof.query_json
        )
    except (ValueError, TypeError):
        return False


def add_independent_evidence(
    catalogue, ledger, as_of, start, end, *, parameters, parties=()
):
    """Query evaluator-owned rows; never derive expected facts from app proof."""
    add_debt_zero_evidence(catalogue, ledger, as_of, parameters, parties)
    add_schedule_zero_evidence(catalogue, ledger, as_of, end, parties)
    coverage = getattr(ledger, "evaluation_zero_coverage", None)
    if coverage is not None and coverage[0] <= start <= end <= coverage[1] <= as_of:
        rows = ledger.visible(as_of, known_at=cutoff(as_of))
        events = EVENTS | {
            "selected_sales": EVENTS[
                {"cash": "cash_sales", "credit": "credit_sales", "all": "total_sales"}[
                    parameters.get("kind", "all")
                ]
            ]
        }
        for key, kinds in events.items():
            expected = catalogue.get(key)
            if expected is None or expected["value"] != 0 or expected["source_ids"]:
                continue
            matching = [
                row
                for row in rows
                if str(start) <= row["business_date"] <= str(end)
                and row["type"] in kinds
            ]
            if matching:
                continue
            query = dict(
                tool="get_sales",
                period=dict(start=str(start), end=str(end)),
                filters=dict(
                    event_types=list(kinds),
                    active_only=True,
                    known_at=cutoff(as_of).astimezone(UTC).isoformat(),
                ),
                matching_rows=0,
            )
            catalogue[key] = expected | dict(
                independent_zero=IndependentZero(canonical(query))
            )
    catalogue.update(reconciliation_catalogue(ledger, as_of, start, end))


def add_debt_zero_evidence(catalogue, ledger, as_of, parameters, parties):
    """D58: an empty debt selection at the cutoff, from evaluator-owned debts.

    Only unambiguous filters qualify: no party or exactly one, no due window.
    """
    if len(parties) > 1:
        return
    party = parties[0] if parties else None
    try:
        balances = ledger.debts(as_of, known_at=cutoff(as_of))
    except TruthError:
        return
    overdue = bool(parameters.get("overdue_only", False))
    for group, kind in (("receivables", "receivable"), ("payables", "payable")):
        key = group + ".total_outstanding"
        expected = catalogue.get(key)
        if expected is None or expected["value"] != 0 or expected["source_ids"]:
            continue
        if any(
            row["kind"] == kind
            and row["outstanding_iqd"] > 0
            and (party is None or row["counterparty_id"] == party)
            and (not overdue or row["days_overdue"] > 0)
            for row in balances
        ):
            continue
        query = dict(
            tool="get_debts",
            as_of=str(as_of),
            filters=dict(
                direction=kind,
                overdue_only=overdue,
                counterparty_id=party,
                due_start=None,
                due_end=None,
            ),
            known_at=cutoff(as_of).astimezone(UTC).isoformat(),
            matching_obligations=0,
        )
        catalogue[key] = expected | dict(
            independent_zero=IndependentZero(canonical(query))
        )


def add_schedule_zero_evidence(catalogue, ledger, as_of, end, parties):
    """D58: nothing scheduled in an upcoming window/day, from evaluator-owned debts.

    Dues count on max(as_of, due date); expected collections exclude overdue.
    """
    if (
        len(parties) > 1
        or end < as_of
        or not any(k.startswith("upcoming.") for k in catalogue)
    ):
        return
    party = parties[0] if parties else None
    try:
        balances = [
            row
            for row in ledger.debts(as_of, known_at=cutoff(as_of))
            if row["outstanding_iqd"] > 0
            and (party is None or row["counterparty_id"] == party)
        ]
    except TruthError:
        return
    if any(row["due_date"] is None for row in balances):
        return

    def matches(schedule, first, last):
        for row in balances:
            due = date.fromisoformat(row["due_date"])
            if schedule == "dues" and row["kind"] == "payable":
                if first <= max(as_of, due) <= last:
                    return True
            if schedule == "expected" and row["kind"] == "receivable":
                if as_of <= due and first <= due <= last:
                    return True
        return False

    windows = {
        "upcoming.dues_total": ("dues", as_of, end),
        "upcoming.expected_total": ("expected", as_of, end),
    }
    for offset in range((end - as_of).days + 1):
        day = as_of + timedelta(days=offset)
        windows[f"upcoming.days.{offset}.dues_iqd"] = ("dues", day, day)
        windows[f"upcoming.days.{offset}.expected_iqd"] = ("expected", day, day)
    for key, (schedule, first, last) in windows.items():
        expected = catalogue.get(key)
        if expected is None or expected["value"] != 0 or expected["source_ids"]:
            continue
        if matches(schedule, first, last):
            continue
        query = dict(
            tool="get_debts",
            as_of=str(as_of),
            schedule=schedule,
            start=str(first),
            end=str(last),
            counterparty_id=party,
            known_at=cutoff(as_of).astimezone(UTC).isoformat(),
            matching_obligations=0,
        )
        catalogue[key] = expected | dict(
            independent_zero=IndependentZero(canonical(query))
        )


def reconciliation_catalogue(ledger, as_of, start, end):
    """Narrow mapping of sourced partial/overdue balances (§10, D55-F3).

    Unallocated payments could introduce unsupported flag shapes/order: fail
    closed for that entire view. No stored/importer flags enter the evaluation
    adapter's fresh database. Nothing about a flag confirms a suspected cause.
    """
    try:
        rows = ledger.visible(as_of, known_at=cutoff(as_of))
        by_id = {r["transaction_id"]: r for r in rows}
        links = [
            r
            for r in ledger.links
            if r["payment_transaction_id"] in by_id
            and stamp(r["created_at"]) <= cutoff(as_of)
        ]
        for row in rows:
            if (
                row["type"] in {"CREDIT_COLLECTION", "SUPPLIER_PAYMENT"}
                and sum(
                    link["amount_iqd"]
                    for link in links
                    if link["payment_transaction_id"] == row["transaction_id"]
                )
                != row["amount_iqd"]
            ):
                return {}
        selected = {
            r["source_id"] for r in rows if str(start) <= r["business_date"] <= str(end)
        }
        origins = {
            r["obligation_id"]: r
            for r in rows
            if r["type"] in {"CREDIT_SALE", "SUPPLIER_INVOICE"}
        }
        flags = []
        for debt in ledger.debts(as_of, known_at=cutoff(as_of)):
            amount = debt["outstanding_iqd"]
            origin = origins[debt["obligation_id"]]
            if amount <= 0 or not selected.intersection(debt["source_ids"]):
                continue
            for prefix, qualifies in (
                ("PARTIAL-", amount < origin["amount_iqd"]),
                ("OVERDUE-", debt["days_overdue"] > 0),
            ):
                if qualifies:
                    flags.append(
                        (
                            prefix + debt["obligation_id"],
                            dict(
                                value=amount,
                                unit="IQD",
                                label="reconciliation_amount",
                                source_ids=sorted(set(debt["source_ids"])),
                                evidence_tool="reconcile",
                                reconciliation_flag_id=prefix + debt["obligation_id"],
                            ),
                        )
                    )
        return {
            f"items.{index}.amount": fact
            for index, (_, fact) in enumerate(sorted(flags))
        }
    except (TruthError, KeyError):
        return {}
