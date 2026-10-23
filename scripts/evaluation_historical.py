"""Independent historical reconstruction for the approved ten-selector registry.

Economic scope E is separate from knowledge K. No app/services, forecast outcomes,
question files or model inputs. Only explicitly complete observed packages qualify.
"""

from datetime import date, timedelta

from scripts.make_ground_truth import (
    BAGHDAD,
    INFLOWS,
    OUTFLOWS,
    TruthError,
    cutoff,
    stamp,
)

BASELINE_POLICY = "allowlisted_observed_baseline_from_economic_date"
LABEL = "historical, reconstructed using records known by the question cutoff"


def historical_catalogue(ledger, as_of, start, end, *, parties=(), parameters=None):
    parameters = parameters or {}
    coverage = getattr(ledger, "evaluation_coverage", None)
    if not coverage or not coverage[0] <= start <= end <= as_of <= coverage[1]:
        return {}
    if not date(2026, 7, 1) <= start <= end <= as_of <= date(2026, 9, 28):
        return {}
    known = cutoff(as_of)
    result = {}
    try:
        raw = [
            r
            for r in ledger.rows
            if r["business_date"] <= str(end)
            and stamp(r["occurred_at"]) <= cutoff(end)
            and stamp(r["recorded_at"]) <= known
            and r.get("accepted", True) is True
        ]
        if len({r["transaction_id"] for r in raw}) != len(raw):
            return {}
        if any(
            type(r["amount_iqd"]) is not int
            or r["amount_iqd"] < 0
            or (r["amount_iqd"] == 0 and r["type"] != "DAILY_CASH_COUNT")
            or r.get("status", "valid") not in {"valid", "flagged"}
            or str(stamp(r["occurred_at"]).astimezone(BAGHDAD).date())
            != r["business_date"]
            for r in raw
        ):
            return {}
        voids = [v for v in ledger.voids if stamp(v["voided_at"]) <= known]
        removed = {v["transaction_id"] for v in voids}
        rows = [r for r in raw if r["transaction_id"] not in removed]
    except (KeyError, TypeError, ValueError):
        return {}
    by_id = {r["transaction_id"]: r for r in rows}
    raw_ids = {r["transaction_id"] for r in raw}

    def audit(predicate):
        relevant = {r["transaction_id"] for r in raw if predicate(r)}
        return [v for v in voids if v["transaction_id"] in relevant]

    def add(
        key,
        amount,
        label,
        inputs,
        *,
        period=None,
        prerequisites=(),
        audits=(),
        allocations=(),
        **metadata,
    ):
        result[key] = dict(
            value=amount,
            unit="IQD",
            label=label,
            source_ids=sorted({r["source_id"] for r in inputs}),
            economic_period=period or dict(start=str(end), end=str(end)),
            knowledge_cutoff=known.isoformat(),
            historical_reconstruction=end < as_of,
            reconstruction_label=LABEL
            if end < as_of
            else "records known at the question cutoff",
            prerequisite_source_ids=sorted({r["source_id"] for r in prerequisites}),
            void_provenance=sorted(
                audits, key=lambda v: (v["voided_at"], v["void_id"])
            ),
            allocation_provenance=sorted(
                allocations, key=lambda v: v["payment_link_id"]
            ),
            **metadata,
        )

    def count(items):
        ordered = sorted(items, key=lambda r: stamp(r["occurred_at"]))
        if not ordered:
            return None
        if len(ordered) > 1 and stamp(ordered[-2]["occurred_at"]) == stamp(
            ordered[-1]["occurred_at"]
        ):
            raise TruthError("AMBIGUOUS_CASH_COUNT")
        return ordered[-1]

    def signed(items):
        return sum(r["amount_iqd"] * (1 if r["type"] in INFLOWS else -1) for r in items)

    flows = [r for r in rows if r["type"] in INFLOWS | OUTFLOWS]
    period = dict(start=str(start), end=str(end))
    for key, kinds, label in (
        ("inflows", INFLOWS, "recorded_cash_inflows"),
        ("outflows", OUTFLOWS, "recorded_cash_outflows"),
    ):
        items = [
            r for r in flows if str(start) <= r["business_date"] and r["type"] in kinds
        ]
        add(
            "period.cash_" + key + "_iqd",
            sum(r["amount_iqd"] for r in items),
            label,
            items,
            period=period,
            audits=audit(
                lambda r: str(start) <= r["business_date"] and r["type"] in kinds
            ),
        )

    def balance(candidates, boundary=None):
        anchor = count(candidates)
        opening_recorded_at = None
        if anchor:
            if any(
                stamp(r["occurred_at"]) == stamp(anchor["occurred_at"])
                and r.get("source") != "daily_close_review"
                for r in flows
            ):
                raise TruthError("AMBIGUOUS_CASH_ORDER")
            # A later entry retaining a pre-count economic timestamp is already
            # reflected in the count. Never add it based on its recording time.
            movements = [
                r
                for r in flows
                if stamp(r["occurred_at"]) > stamp(anchor["occurred_at"])
            ]
            inputs = [anchor]
            initial = anchor["amount_iqd"]
        else:
            opening = ledger.opening
            if not getattr(ledger, "evaluation_opening_baseline", False) or not opening:
                raise TruthError("MISSING_OPENING_BALANCE")
            if opening["business_date"] > str(end):
                raise TruthError("MISSING_OPENING_BALANCE")
            opening_recorded_at = opening.get("recorded_at")
            if opening_recorded_at and stamp(opening_recorded_at) > known:
                raise TruthError("MISSING_OPENING_BALANCE")
            if type(opening["amount_iqd"]) is not int or opening["amount_iqd"] < 0:
                raise TruthError("INVALID_OPENING_BALANCE")
            initial, inputs = opening["amount_iqd"], [opening]
            movements = [
                r for r in flows if r["business_date"] >= opening["business_date"]
            ]
        if inputs[0]["business_date"] < str(coverage[0]):
            raise TruthError("INCOMPLETE_CASH_HISTORY")
        if boundary:
            movements = [
                r
                for r in movements
                if stamp(r["occurred_at"]) < boundary
                or (
                    stamp(r["occurred_at"]) == boundary
                    and r.get("source") == "daily_close_review"
                )
            ]
            # Equal-time ordinary events have no recorded pre-count ordering.
            if any(
                stamp(r["occurred_at"]) == boundary
                and r.get("source") != "daily_close_review"
                for r in flows
            ):
                raise TruthError("AMBIGUOUS_CASH_ORDER")
        return initial + signed(movements), inputs + movements, opening_recorded_at

    counts = [r for r in rows if r["type"] == "DAILY_CASH_COUNT"]

    def balance_audits(inputs, boundary=None):
        anchor = inputs[0]

        def relevant(row):
            if row["type"] not in INFLOWS | OUTFLOWS | {"DAILY_CASH_COUNT"}:
                return False
            when = stamp(row["occurred_at"])
            if boundary and (
                when > boundary
                or (when == boundary and row.get("source") != "daily_close_review")
            ):
                return False
            if anchor.get("type") == "DAILY_CASH_COUNT":
                # Later voided counts can affect baseline selection; older
                # movements/counts already superseded by the anchor cannot.
                return (
                    when >= stamp(anchor["occurred_at"])
                    if row["type"] == "DAILY_CASH_COUNT"
                    else when > stamp(anchor["occurred_at"])
                )
            return row["business_date"] >= anchor["business_date"]

        return audit(relevant)

    try:
        amount, inputs, recorded = balance(counts)
        add(
            "period_end.cash_on_hand",
            amount,
            "historical_cash_on_hand",
            inputs,
            audits=balance_audits(inputs),
            opening_recorded_at=recorded,
        )
    except TruthError:
        pass

    target = previous = None
    try:
        target = count(r for r in counts if r["business_date"] == str(end))
        previous = count(
            r for r in counts if r["business_date"] == str(end - timedelta(days=1))
        )
    except TruthError:
        # An ambiguous prior count need not hide an unambiguous target count.
        try:
            target = count(r for r in counts if r["business_date"] == str(end))
        except TruthError:
            target = None
    strict = bool(target and previous)
    day_flows = [r for r in flows if r["business_date"] == str(end)]
    if target:
        target_audits = audit(
            lambda r: (
                r["type"] == "DAILY_CASH_COUNT"
                and stamp(r["occurred_at"]) == stamp(target["occurred_at"])
            )
        )
        add(
            "closing.counted_cash_iqd",
            target["amount_iqd"],
            "counted_closing_cash",
            [target],
            audits=target_audits,
        )
        if strict:
            amount = previous["amount_iqd"] + signed(day_flows)
            audits = audit(
                lambda r: (
                    (
                        r["type"] == "DAILY_CASH_COUNT"
                        and r["business_date"]
                        in {str(end), str(end - timedelta(days=1))}
                    )
                    or (
                        r["type"] in INFLOWS | OUTFLOWS
                        and r["business_date"] == str(end)
                    )
                )
            )
            add(
                "closing.expected_cash_iqd",
                amount,
                "expected_closing_cash",
                [previous, *day_flows],
                prerequisites=[target],
                audits=audits,
            )
            add(
                "closing.unexplained_difference_iqd",
                target["amount_iqd"] - amount,
                "unexplained_cash_difference",
                [previous, target, *day_flows],
                audits=audits,
            )
        try:
            boundary = stamp(target["occurred_at"])
            amount, inputs, recorded = balance(
                [r for r in counts if stamp(r["occurred_at"]) < boundary], boundary
            )
            book_audits = list(
                {
                    v["void_id"]: v
                    for v in [*balance_audits(inputs, boundary), *target_audits]
                }.values()
            )
            add(
                "closing.pre_count_book_cash_iqd",
                amount,
                "pre_count_book_cash",
                inputs,
                prerequisites=[target],
                audits=book_audits,
                opening_recorded_at=recorded,
                strict_daily_comparison_available=strict,
                strict_daily_comparison_note="available"
                if strict
                else "requires active closing counts on E-1 and E",
                baseline_source_id=inputs[0]["source_id"],
            )
            add(
                "closing.book_to_count_difference_iqd",
                target["amount_iqd"] - amount,
                "book_to_count_difference",
                [*inputs, target],
                audits=book_audits,
                strict_daily_comparison_available=strict,
                strict_daily_comparison_note="available"
                if strict
                else "requires active closing counts on E-1 and E",
                baseline_source_id=inputs[0]["source_id"],
            )
        except TruthError:
            pass

    for direction, origin_type, payment_type in (
        ("receivables", "CREDIT_SALE", "CREDIT_COLLECTION"),
        ("payables", "SUPPLIER_INVOICE", "SUPPLIER_PAYMENT"),
    ):
        try:
            origins = [
                r
                for r in rows
                if r["type"] == origin_type
                and (not parties or r["counterparty_id"] in parties)
            ]
            if len({r["obligation_id"] for r in origins}) != len(origins):
                raise TruthError("DUPLICATE_OBLIGATION")
            selected, allocations, inputs = [], [], []
            for origin in origins:
                links = [
                    link
                    for link in ledger.links
                    if link["obligation_id"] == origin["obligation_id"]
                    and stamp(link["created_at"]) <= known
                    and link["payment_transaction_id"] in by_id
                ]
                if any(
                    link.get("match_basis") not in {"confirmed", "definite", "strong"}
                    or type(link["amount_iqd"]) is not int
                    or link["amount_iqd"] <= 0
                    or by_id[link["payment_transaction_id"]]["type"] != payment_type
                    or by_id[link["payment_transaction_id"]]["counterparty_id"]
                    != origin["counterparty_id"]
                    for link in links
                ):
                    raise TruthError("INVALID_ALLOCATION")
                if len({link["payment_link_id"] for link in links}) != len(links):
                    raise TruthError("INVALID_ALLOCATION")
                for link in links:
                    payment = by_id[link["payment_transaction_id"]]
                    allocated = sum(
                        item["amount_iqd"]
                        for item in ledger.links
                        if item["payment_transaction_id"] == payment["transaction_id"]
                        and item["payment_transaction_id"] in raw_ids
                        and stamp(item["created_at"]) <= known
                    )
                    if allocated > payment["amount_iqd"]:
                        raise TruthError("OVERPAYMENT")
                amount = origin["amount_iqd"] - sum(
                    link["amount_iqd"] for link in links
                )
                if amount < 0:
                    raise TruthError("OVERPAYMENT")
                if parameters.get("overdue_only") and amount:
                    if not origin["due_date"]:
                        raise TruthError("MISSING_DUE_DATE")
                    if origin["due_date"] >= str(end):
                        continue
                selected.append(amount)
                inputs.extend(
                    [origin, *(by_id[link["payment_transaction_id"]] for link in links)]
                )
                allocations.extend(links)
            add(
                "period_end." + direction + ".total_outstanding",
                sum(selected),
                "historical_" + direction + "_outstanding",
                inputs,
                allocations=allocations,
                audits=audit(
                    lambda r: (
                        r["type"] in {origin_type, payment_type}
                        and (not parties or r["counterparty_id"] in parties)
                    )
                ),
            )
        except (TruthError, KeyError, TypeError, ValueError):
            continue
    return result
