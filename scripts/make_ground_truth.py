"""Independent, offline development truth. Uses stdlib and file I/O, never app code.

Default inputs are an explicit observed-history allowlist. This script does not
read future outcomes, cause labels, unseen shops or HELDOUT_PATH.
"""

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from fractions import Fraction
from pathlib import Path

if __package__ in {None, ""}:
    from data_contract import (
        FIXTURES,
        read_csv,
        read_json,
        sha256,
        validate_question,
        write_json,
    )
else:
    from .data_contract import (
        FIXTURES,
        read_csv,
        read_json,
        sha256,
        validate_question,
        write_json,
    )

BAGHDAD = timezone(timedelta(hours=3))
INFLOWS = {"CASH_SALE", "CREDIT_COLLECTION", "CAPITAL_INJECTION"}
OUTFLOWS = {"SUPPLIER_PAYMENT", "OPERATING_EXPENSE", "OWNER_DRAWING"}
SALES = {"CASH_SALE", "CREDIT_SALE"}


class TruthError(ValueError):
    """Typed unavailable/invalid truth, never a fabricated monetary zero."""


def stamp(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if value.tzinfo is None or value.utcoffset() is None:
        raise TruthError("VALIDATION_ERROR")
    return value


def cutoff(as_of, known_at=None):
    return stamp(known_at) if known_at else datetime.combine(as_of, time.max, BAGHDAD)


def round_half_up(numerator, denominator):
    if denominator <= 0:
        raise TruthError("MISSING_DATA")
    sign = -1 if numerator < 0 else 1
    q, r = divmod(abs(numerator), denominator)
    return sign * (q + (2 * r >= denominator))


def mean(values):
    return round_half_up(sum(values), len(values))


def median_days(values):
    if not values:
        raise TruthError("MISSING_LATENESS_HISTORY")
    values = sorted(values)
    middle = len(values) // 2
    return (
        values[middle]
        if len(values) % 2
        else Fraction(values[middle - 1] + values[middle], 2)
    )


class TruthLedger:
    def __init__(self, rows, *, opening=None, categories=(), links=(), voids=()):
        self.rows = list(rows)
        self.opening = opening
        self.categories = {r["category_id"]: r for r in categories}
        self.links = list(links)
        self.voids = list(voids)

    def visible(self, as_of, known_at=None):
        known = cutoff(as_of, known_at)
        removed = {
            r["transaction_id"] for r in self.voids if stamp(r["voided_at"]) <= known
        }
        result = [
            r
            for r in self.rows
            if r["transaction_id"] not in removed
            and r["business_date"] <= str(as_of)
            and stamp(r["occurred_at"]) <= known
            and stamp(r["recorded_at"]) <= known
        ]
        if len({r["transaction_id"] for r in result}) != len(result):
            raise TruthError("DUPLICATE_TRANSACTION")
        return sorted(
            result, key=lambda r: (stamp(r["occurred_at"]), r["transaction_id"])
        )

    def cash(self, as_of, known_at=None):
        rows = self.visible(as_of, known_at)
        counts = [r for r in rows if r["type"] == "DAILY_CASH_COUNT"]
        if counts:
            anchor = counts[-1]
            if len(counts) > 1 and counts[-2]["occurred_at"] == anchor["occurred_at"]:
                raise TruthError("AMBIGUOUS_CASH_COUNT")
            balance = anchor["amount_iqd"]
            rows = [
                r
                for r in rows
                if stamp(r["occurred_at"]) > stamp(anchor["occurred_at"])
            ]
            sources = [anchor["source_id"]]
            counted_at = anchor["occurred_at"]
        elif self.opening and self.opening["business_date"] <= str(as_of):
            balance = self.opening["amount_iqd"]
            rows = [
                r for r in rows if r["business_date"] >= self.opening["business_date"]
            ]
            sources = [self.opening["source_id"]]
            counted_at = None
        else:
            raise TruthError("MISSING_OPENING_BALANCE")
        for r in rows:
            if r["type"] in INFLOWS | OUTFLOWS:
                balance += r["amount_iqd"] * (1 if r["type"] in INFLOWS else -1)
                sources.append(r["source_id"])
        return {"amount_iqd": balance, "source_ids": sources, "counted_at": counted_at}

    def daily_close(self, day, known_at=None):
        rows = self.visible(day, known_at)
        counts = {}
        for r in rows:
            if r["type"] == "DAILY_CASH_COUNT":
                prior = counts.get(r["business_date"])
                if prior and prior["occurred_at"] == r["occurred_at"]:
                    raise TruthError("AMBIGUOUS_CASH_COUNT")
                counts[r["business_date"]] = r
        previous = counts.get(str(day - timedelta(days=1)))
        closing = counts.get(str(day))
        flows = [
            r
            for r in rows
            if r["business_date"] == str(day) and r["type"] in INFLOWS | OUTFLOWS
        ]
        expected = (
            None
            if previous is None
            else previous["amount_iqd"]
            + sum(r["amount_iqd"] * (1 if r["type"] in INFLOWS else -1) for r in flows)
        )
        difference = (
            None
            if expected is None or closing is None
            else closing["amount_iqd"] - expected
        )
        return {
            "date": str(day),
            "expected_close_iqd": expected,
            "unexplained_difference_iqd": difference,
            "recorded_cash_sales_iqd": sum(
                r["amount_iqd"] for r in flows if r["type"] == "CASH_SALE"
            ),
            "kind": "missing" if difference is None else "flagged",
            "source_ids": [r["source_id"] for r in (previous, closing) if r]
            + [r["source_id"] for r in flows],
        }

    def sales(self, start, end, known_at=None):
        rows = [
            r for r in self.visible(end, known_at) if str(start) <= r["business_date"]
        ]
        daily = [
            self.daily_close(start + timedelta(days=i), known_at or cutoff(end))
            for i in range((end - start).days + 1)
        ]
        cash = sum(r["amount_iqd"] for r in rows if r["type"] == "CASH_SALE")
        credit = sum(r["amount_iqd"] for r in rows if r["type"] == "CREDIT_SALE")
        gap = (
            None
            if any(r["unexplained_difference_iqd"] is None for r in daily)
            else sum(r["unexplained_difference_iqd"] for r in daily)
        )
        return {
            "recorded_cash_sales_iqd": cash,
            "recorded_credit_sales_iqd": credit,
            "total_recorded_sales_iqd": cash + credit,
            "unexplained_difference_iqd": gap,
            "source_ids": [r["source_id"] for r in rows if r["type"] in SALES],
            "difference_source_ids": list(
                dict.fromkeys(s for r in daily for s in r["source_ids"])
            ),
        }

    def debts(self, as_of, *, direction="both", known_at=None):
        rows = self.visible(as_of, known_at)
        known = cutoff(as_of, known_at)
        by_id = {r["transaction_id"]: r for r in rows}
        origins = [r for r in rows if r["type"] in {"CREDIT_SALE", "SUPPLIER_INVOICE"}]
        balances = []
        for origin in origins:
            kind = "receivable" if origin["type"] == "CREDIT_SALE" else "payable"
            if direction not in {"both", kind}:
                continue
            links = [
                r
                for r in self.links
                if r["obligation_id"] == origin["obligation_id"]
                and r["payment_transaction_id"] in by_id
                and stamp(r["created_at"]) <= known
            ]
            amount = origin["amount_iqd"] - sum(r["amount_iqd"] for r in links)
            if amount < 0:
                raise TruthError("OVERPAYMENT")
            due = date.fromisoformat(origin["due_date"]) if origin["due_date"] else None
            overdue = max(0, (as_of - due).days) if due else 0
            bucket = (
                "not_due"
                if overdue == 0
                else "d1_7"
                if overdue <= 7
                else "d8_30"
                if overdue <= 30
                else "d31_60"
                if overdue <= 60
                else "d60_plus"
            )
            balances.append(
                {
                    "obligation_id": origin["obligation_id"],
                    "counterparty_id": origin["counterparty_id"],
                    "kind": kind,
                    "due_date": origin["due_date"],
                    "outstanding_iqd": amount,
                    "days_overdue": overdue,
                    "bucket": bucket,
                    "source_ids": [origin["source_id"]]
                    + [by_id[r["payment_transaction_id"]]["source_id"] for r in links],
                }
            )
        return sorted(
            balances,
            key=lambda r: (
                -r["days_overdue"],
                -r["outstanding_iqd"],
                r["obligation_id"],
            ),
        )

    def upcoming(self, as_of, days=7, known_at=None):
        if type(days) is not int or not 1 <= days <= 30:
            raise TruthError("VALIDATION_ERROR")
        end = as_of + timedelta(days=days - 1)
        balances = [
            r for r in self.debts(as_of, known_at=known_at) if r["outstanding_iqd"] > 0
        ]
        dues, expected, overdue = [], [], []
        for r in balances:
            if not r["due_date"]:
                continue
            due = date.fromisoformat(r["due_date"])
            if r["kind"] == "payable" and due <= end:
                dues.append(r | {"due_now": due < as_of})
            elif r["kind"] == "receivable":
                if due < as_of:
                    overdue.append(r | {"timing": "unknown"})
                elif due <= end:
                    expected.append(r)
        try:
            starting = self.cash(as_of, known_at)
        except TruthError as exc:
            if str(exc) != "MISSING_OPENING_BALANCE":
                raise
            starting = {"amount_iqd": None, "counted_at": None, "source_ids": []}
        confirmed = with_expected = starting["amount_iqd"]
        daily = []
        for i in range(days):
            day = as_of + timedelta(days=i)
            due = sum(
                r["outstanding_iqd"]
                for r in dues
                if max(as_of, date.fromisoformat(r["due_date"])) == day
            )
            collected = sum(
                r["outstanding_iqd"] for r in expected if r["due_date"] == str(day)
            )
            if confirmed is not None:
                confirmed -= due
                with_expected += collected - due
            daily.append(
                {
                    "date": str(day),
                    "dues_iqd": due,
                    "expected_iqd": collected,
                    "running_confirmed_iqd": confirmed,
                    "running_with_expected_iqd": with_expected,
                }
            )
        return {
            "cash_iqd": starting["amount_iqd"],
            "counted_at": starting["counted_at"],
            "dues": dues,
            "expected": expected,
            "overdue_receivables": overdue,
            "dues_total_iqd": sum(r["outstanding_iqd"] for r in dues),
            "expected_total_iqd": sum(r["outstanding_iqd"] for r in expected),
            "position_confirmed_iqd": confirmed,
            "position_with_expected_iqd": with_expected,
            "days": daily,
            "first_short_date_confirmed": next(
                (
                    r["date"]
                    for r in daily
                    if r["running_confirmed_iqd"] is not None
                    and r["running_confirmed_iqd"] < 0
                ),
                None,
            ),
            "first_short_date_with_expected": next(
                (
                    r["date"]
                    for r in daily
                    if r["running_with_expected_iqd"] is not None
                    and r["running_with_expected_iqd"] < 0
                ),
                None,
            ),
            "source_ids": list(
                dict.fromkeys(
                    starting["source_ids"]
                    + [s for r in dues + expected for s in r["source_ids"]]
                )
            ),
        }

    def j1(self, as_of, due_date):
        balances = [r for r in self.debts(as_of) if r["outstanding_iqd"]]
        cash = self.cash(as_of)
        dues = [
            r
            for r in balances
            if r["kind"] == "payable" and r["due_date"] == str(due_date)
        ]
        expected = [
            r
            for r in balances
            if r["kind"] == "receivable"
            and r["due_date"]
            and str(as_of) <= r["due_date"] <= str(due_date)
        ]
        due = sum(r["outstanding_iqd"] for r in dues)
        collection = sum(r["outstanding_iqd"] for r in expected)
        return {
            "cash_iqd": cash["amount_iqd"],
            "dues_iqd": due,
            "expected_iqd": collection,
            "shortfall_with_iqd": max(0, due - cash["amount_iqd"] - collection),
            "shortfall_without_iqd": max(0, due - cash["amount_iqd"]),
            "source_ids": cash["source_ids"]
            + [s for r in dues + expected for s in r["source_ids"]],
        }

    def margin(self, start, end, known_at=None):
        rows = [
            r for r in self.visible(end, known_at) if str(start) <= r["business_date"]
        ]
        sales = [r for r in rows if r["type"] in SALES]
        priced = [
            r
            for r in sales
            if self.categories.get(r["category_id"], {}).get("buy_price_iqd")
            is not None
        ]
        total = sum(r["amount_iqd"] for r in sales)
        if total and not priced:
            raise TruthError("MISSING_COSTS")
        priced_total = sum(r["amount_iqd"] for r in priced)
        coverage = 100 * priced_total // total if total else None
        margin = sum(
            r["amount_iqd"]
            - r["quantity"] * self.categories[r["category_id"]]["buy_price_iqd"]
            for r in priced
        )
        return {
            "estimated_gross_margin_iqd": margin if total else None,
            "coverage_pct": coverage,
            "unpriced_sales_count": len(sales) - len(priced),
            "weekly_margin_shown": coverage is not None and coverage >= 80,
            "after_recorded_expenses_iqd": margin
            - sum(r["amount_iqd"] for r in rows if r["type"] == "OPERATING_EXPENSE")
            if total
            else None,
            "source_ids": [r["source_id"] for r in sales],
            "note_key": "margin_excludes_unrecorded_costs",
        }

    def lateness(self, as_of):
        rows = {r["transaction_id"]: r for r in self.visible(as_of)}
        settled = {
            r["obligation_id"]
            for r in self.debts(as_of, direction="receivable")
            if r["outstanding_iqd"] == 0
        }
        customer = defaultdict(list)
        for r in rows.values():
            if (
                r["type"] != "CREDIT_SALE"
                or r["obligation_id"] not in settled
                or not r["due_date"]
            ):
                continue
            links = [
                link
                for link in self.links
                if link["obligation_id"] == r["obligation_id"]
                and link["payment_transaction_id"] in rows
                and stamp(link["created_at"]) <= cutoff(as_of)
            ]
            ordered = sorted(
                links,
                key=lambda link: stamp(
                    rows[link["payment_transaction_id"]]["occurred_at"]
                ),
            )
            total = 0
            for link in ordered:
                total += link["amount_iqd"]
                if total == r["amount_iqd"]:
                    paid = date.fromisoformat(
                        rows[link["payment_transaction_id"]]["business_date"]
                    )
                    customer[r["counterparty_id"]].append(
                        max(0, (paid - date.fromisoformat(r["due_date"])).days)
                    )
                    break
        all_days = [d for values in customer.values() for d in values]
        return customer, all_days

    def forecast(self, as_of, scenario):
        if scenario not in {"base", "conservative", "stress"}:
            raise TruthError("VALIDATION_ERROR")
        rows = self.visible(as_of)
        history_start = as_of - timedelta(days=55)
        by_day = defaultdict(lambda: defaultdict(int))
        for r in rows:
            by_day[r["business_date"]][r["type"]] += r["amount_iqd"]
        sales, gaps = defaultdict(list), defaultdict(list)
        for i in range(56):
            day = history_start + timedelta(days=i)
            sales[day.weekday()].append(by_day[str(day)]["CASH_SALE"])
            gap = self.daily_close(day, cutoff(as_of))["unexplained_difference_iqd"]
            if gap is not None:
                gaps[day.weekday()].append(gap)
        if any(not gaps[w] for w in range(7)):
            raise TruthError("MISSING_COUNT")
        sales_means = {w: mean(v) for w, v in sales.items()}
        gap_means = {w: mean(v) for w, v in gaps.items()}
        expenses = mean(
            [
                by_day[str(as_of - timedelta(days=i))]["OPERATING_EXPENSE"]
                for i in range(28)
            ]
        )
        drawings = mean(
            [by_day[str(as_of - timedelta(days=i))]["OWNER_DRAWING"] for i in range(28)]
        )
        balances = [r for r in self.debts(as_of) if r["outstanding_iqd"] > 0]
        customer, all_lateness = self.lateness(as_of)
        receipts, payments = defaultdict(int), defaultdict(int)
        for debt in balances:
            if not debt["due_date"]:
                continue
            due = date.fromisoformat(debt["due_date"])
            if debt["kind"] == "payable":
                payments[str(due)] += debt["outstanding_iqd"]
            elif due >= as_of and scenario != "stress":
                values = customer[debt["counterparty_id"]]
                delay = (
                    median_days(values if len(values) >= 2 else all_lateness)
                    if scenario == "conservative"
                    else 0
                )
                # Median lateness may be half a day. Keep it exact and assign
                # the receipt to the Baghdad date containing that instant.
                arrival = datetime.combine(due, time.min, BAGHDAD) + timedelta(
                    seconds=int(delay * 86400)
                )
                receipts[str(arrival.date())] += debt["outstanding_iqd"]
        opening = self.cash(as_of)["amount_iqd"]
        daily = []
        for i in range(1, 31):
            day = as_of + timedelta(days=i)
            sale, gap = sales_means[day.weekday()], gap_means[day.weekday()]
            collected, paid = receipts[str(day)], payments[str(day)]
            closing = opening + sale + gap + collected - paid - expenses - drawings
            daily.append(
                {
                    "date": str(day),
                    "opening_iqd": opening,
                    "cash_sales_iqd": sale,
                    "unlinked_cash_iqd": gap,
                    "collections_iqd": collected,
                    "supplier_payments_iqd": paid,
                    "expenses_iqd": expenses,
                    "owner_drawings_iqd": drawings,
                    "closing_iqd": closing,
                }
            )
            opening = closing
        lowest = min(daily, key=lambda r: r["closing_iqd"])
        first_short = next(
            (
                r["date"]
                for r in daily
                if r["closing_iqd"] < 0
                or r["closing_iqd"]
                < payments[str(date.fromisoformat(r["date"]) + timedelta(days=1))]
            ),
            None,
        )
        inflows = {
            "recorded_cash_sales": sum(r["cash_sales_iqd"] for r in daily),
            "expected_collections": sum(r["collections_iqd"] for r in daily),
        }
        outflows = {
            "supplier_payments": sum(r["supplier_payments_iqd"] for r in daily),
            "expenses": 30 * expenses,
            "owner_drawings": 30 * drawings,
        }
        unlinked = sum(r["unlinked_cash_iqd"] for r in daily)
        (inflows if unlinked >= 0 else outflows)["unlinked_cash"] = abs(unlinked)
        assumptions = [
            "collections_expected_not_guaranteed",
            "sales_from_weekday_averages",
            "unlinked_cash_projected_from_counts",
        ]
        return {
            "days": daily,
            "lowest": {"date": lowest["date"], "closing_iqd": lowest["closing_iqd"]},
            "first_shortfall_date": first_short,
            "top_inflows": sorted(inflows.items(), key=lambda x: (-x[1], x[0]))[:3],
            "top_outflows": sorted(outflows.items(), key=lambda x: (-x[1], x[0]))[:3],
            "assumption_keys": assumptions,
        }

    def baseline(self, as_of):
        counts = {
            r["business_date"]: r
            for r in self.visible(as_of)
            if r["type"] == "DAILY_CASH_COUNT"
        }
        left, right = counts.get(str(as_of - timedelta(days=7))), counts.get(str(as_of))
        if left is None or right is None:
            raise TruthError("MISSING_COUNT")
        change = round_half_up(right["amount_iqd"] - left["amount_iqd"], 7)
        starting = self.cash(as_of)
        return {
            "daily_change_iqd": change,
            "days": [
                {
                    "date": str(as_of + timedelta(days=i)),
                    "closing_iqd": starting["amount_iqd"] + i * change,
                }
                for i in range(1, 31)
            ],
            "source_ids": [left["source_id"], right["source_id"]]
            + starting["source_ids"],
        }


def load_ledger(folder, fixture=None):
    """Read only named observed inputs. No filename is supplied by a question."""
    folder = Path(folder)
    prefix = fixture or "observed_90d"
    if fixture and (Path(fixture).name != fixture or fixture not in FIXTURES):
        raise TruthError("INVALID_FIXTURE")

    def optional(name, reader, default):
        path = folder / name
        return reader(path) if path.is_file() else default

    support = fixture + "." if fixture else ""
    rows = read_csv(folder / f"{prefix}.csv")
    if any(r["business_date"] > "2026-09-28" for r in rows):
        raise TruthError("FUTURE_DATA_REJECTED")
    return TruthLedger(
        rows,
        opening=optional(support + "opening_balance.json", read_json, None),
        categories=optional(support + "categories.csv", read_csv, []),
        links=optional(support + "payment_links.csv", read_csv, []),
        voids=optional(support + "entry_voids.csv", read_csv, []),
    )


def answer_question(question, data_root):
    validate_question(question)
    spec = question["spec"]
    behavior = spec["expected_behavior"]
    if spec["calculation"] == "none":
        return {"behavior": behavior, "error_code": spec.get("error_code")}
    dataset = question["dataset"]
    ledger = (
        load_ledger(Path(data_root) / "synthetic")
        if dataset == "primary"
        else load_ledger(Path(data_root) / "fixtures", fixture=dataset)
    )
    as_of = date.fromisoformat(question["business_as_of"])
    period = spec["resolved_period"]
    start, end = (
        (date.fromisoformat(period[k]) for k in ("start", "end"))
        if period
        else (as_of, as_of)
    )
    params = spec["parameters"]
    calculation = spec["calculation"]
    known = cutoff(as_of)
    try:
        if calculation == "sales":
            result = ledger.sales(start, end, known_at=known)
        elif calculation == "cash":
            result = ledger.cash(as_of)
        elif calculation == "debts":
            result = ledger.debts(
                as_of, direction=params.get("direction", "receivable")
            )
            result = [r for r in result if r["outstanding_iqd"] > 0]
            if spec["counterparty_ids"]:
                result = [
                    r
                    for r in result
                    if r["counterparty_id"] in spec["counterparty_ids"]
                ]
            if params.get("overdue_only"):
                result = [
                    r for r in result if r["days_overdue"] > 0 and r["outstanding_iqd"]
                ]
        elif calculation == "margin":
            result = ledger.margin(start, end, known_at=known)
        elif calculation == "upcoming":
            result = ledger.upcoming(as_of, params.get("days", 7))
        elif calculation == "j1":
            result = ledger.j1(as_of, end)
        elif calculation == "weekly_summary":
            rows = [
                r
                for r in ledger.visible(as_of)
                if str(start) <= r["business_date"] <= str(end)
            ]
            balances = ledger.debts(as_of, direction="receivable")
            result = ledger.sales(start, end, known_at=known) | {
                "totals_by_type_iqd": {
                    kind: sum(r["amount_iqd"] for r in rows if r["type"] == kind)
                    for kind in INFLOWS | OUTFLOWS | SALES
                },
                "margin": ledger.margin(start, end, known_at=known),
                "outstanding_receivables_iqd": sum(
                    r["outstanding_iqd"] for r in balances
                ),
                "overdue_receivables_iqd": sum(
                    r["outstanding_iqd"] for r in balances if r["days_overdue"] > 0
                ),
                "receivable_aging": balances,
            }
        else:
            raise TruthError("UNSUPPORTED_CALCULATION")
    except TruthError as exc:
        return {"behavior": "clarify", "error_code": str(exc)}
    return {"behavior": "answer", "result": result}


def generate_development_truth(data_root):
    data_root = Path(data_root)
    questions_path = data_root / "evaluation/development_questions.jsonl"
    questions = [
        json.loads(line)
        for line in questions_path.read_text(encoding="utf-8").splitlines()
    ]
    answers = {q["id"]: answer_question(q, data_root) for q in questions}
    write_json(
        data_root / "evaluation/development_expected.json",
        {
            "split": "development",
            "question_sha256": sha256(questions_path),
            "calculator": "independent_stdlib_v1",
            "answers": answers,
        },
    )
    ledger = load_ledger(data_root / "synthetic")
    expected = {}
    for number in (60, 75):
        as_of = date(2026, 7, 1) + timedelta(days=number - 1)
        expected[str(number)] = {
            "cutoff": str(as_of),
            "prediction_days": 30,
            "scored_days": 90 - number,
            "score_end": "2026-09-28",
            "baseline": ledger.baseline(as_of),
            "scenarios": {
                scenario: ledger.forecast(as_of, scenario)
                for scenario in ("base", "conservative", "stress")
            },
        }
    write_json(
        data_root / "evaluation/forecast_expected.json",
        {
            "split": "development",
            "realized_outcomes_read": False,
            "cutoffs": expected,
            "metrics": None,
            "final_test_run": False,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root", type=Path, default=Path(__file__).resolve().parents[1] / "data"
    )
    args = parser.parse_args()
    generate_development_truth(args.data_root)
    print("Independent development truth written; no realized future outcomes read.")


if __name__ == "__main__":
    main()
