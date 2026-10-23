"""Independent claim catalogue, using observed rows and the frozen stdlib truth.

No backend imports, model calls or expected-answer files. Evidence sets contain
the exact rows/reference prices needed for the named calculation. Unsupported
historical claim shapes fail closed instead of receiving provenance credit.
"""

from collections import defaultdict
from datetime import timedelta

from scripts.make_ground_truth import SALES, TruthError, cutoff


def claim_catalogue(ledger, as_of, start, end, *, parties=(), parameters=None):
    parameters = parameters or {}
    catalogue = {}
    rows = ledger.visible(as_of)
    selected = [r for r in rows if str(start) <= r["business_date"] <= str(end)]

    def add(key, value, label, ids, unit="IQD"):
        if value is not None:
            catalogue[key] = dict(
                value=value, unit=unit, label=label, source_ids=sorted(set(ids))
            )

    def ids(items):
        return [r["source_id"] for r in items]

    def debt_ids(items):
        return [s for r in items for s in r["source_ids"]]

    sale_rows = [r for r in selected if r["type"] in SALES]
    for key, kind, label in (
        ("cash_sales", "CASH_SALE", "recorded_cash_sales"),
        ("credit_sales", "CREDIT_SALE", "credit_sales"),
    ):
        items = [r for r in sale_rows if r["type"] == kind]
        add(key, sum(r["amount_iqd"] for r in items), label, ids(items))
    add(
        "total_sales",
        sum(r["amount_iqd"] for r in sale_rows),
        "total_recorded_sales",
        ids(sale_rows),
    )
    kind = parameters.get("kind", "all")
    catalogue["selected_sales"] = catalogue[
        {"cash": "cash_sales", "credit": "credit_sales", "all": "total_sales"}[kind]
    ]
    if end <= as_of:
        sales = ledger.sales(start, end, known_at=cutoff(as_of))
        add(
            "unexplained_cash_difference",
            sales["unexplained_difference_iqd"],
            "unexplained_cash_difference",
            sales["difference_source_ids"],
        )
    for key, kind in (
        ("owner_drawings", "OWNER_DRAWING"),
        ("operating_expenses", "OPERATING_EXPENSE"),
        ("collections", "CREDIT_COLLECTION"),
    ):
        items = [r for r in selected if r["type"] == kind]
        add("weekly." + key, sum(r["amount_iqd"] for r in items), key, ids(items))

    priced = [
        r
        for r in sale_rows
        if ledger.categories.get(r["category_id"], {}).get("buy_price_iqd") is not None
    ]
    if priced:
        margin = ledger.margin(start, min(end, as_of), known_at=cutoff(as_of))
        categories = sorted({r["category_id"] for r in priced})
        evidence = ids(priced) + categories
        expenses = [r for r in selected if r["type"] == "OPERATING_EXPENSE"]
        for key, source_key, label, sources, unit in (
            (
                "gross_margin",
                "estimated_gross_margin_iqd",
                "estimated_gross_margin",
                evidence,
                "IQD",
            ),
            (
                "after_recorded_expenses",
                "after_recorded_expenses_iqd",
                "after_recorded_expenses",
                evidence + ids(expenses),
                "IQD",
            ),
            (
                "coverage_pct",
                "coverage_pct",
                "recorded_sales_coverage",
                ids(sale_rows),
                "percent",
            ),
            (
                "unpriced_sales_count",
                "unpriced_sales_count",
                "unpriced_sales_count",
                ids(sale_rows),
                "count",
            ),
        ):
            add(key, margin[source_key], label, sources, unit)
        cost = sum(
            r["quantity"] * ledger.categories[r["category_id"]]["buy_price_iqd"]
            for r in priced
        )
        add(
            "priced_sales",
            sum(r["amount_iqd"] for r in priced),
            "priced_recorded_sales",
            ids(priced),
        )
        add("cost_of_goods", cost, "cost_of_goods", evidence)
        for i, key in enumerate(categories):
            add(
                f"price_basis.{i}.buy_price",
                ledger.categories[key]["buy_price_iqd"],
                "category_buy_price",
                [key],
            )

    balances = [r for r in ledger.debts(as_of) if r["outstanding_iqd"] > 0]
    filtered = [r for r in balances if not parties or r["counterparty_id"] in parties]
    if parameters.get("overdue_only"):
        filtered = [r for r in filtered if r["days_overdue"] > 0]
    origins = {
        r["obligation_id"]: r
        for r in rows
        if r["type"] in {"CREDIT_SALE", "SUPPLIER_INVOICE"}
    }
    for direction, singular in (("receivables", "receivable"), ("payables", "payable")):
        debts = [r for r in filtered if r["kind"] == singular]
        add(
            direction + ".total_outstanding",
            sum(r["outstanding_iqd"] for r in debts),
            "total_outstanding",
            debt_ids(debts),
        )
        for bucket in ("not_due", "d1_7", "d8_30", "d31_60", "d60_plus"):
            items = [r for r in debts if r["bucket"] == bucket]
            if all(r["due_date"] is not None for r in debts):
                add(
                    f"{direction}.aging.{bucket}",
                    sum(r["outstanding_iqd"] for r in items),
                    bucket,
                    debt_ids(items),
                )
        groups = defaultdict(list)
        for debt in debts:
            groups[debt["counterparty_id"]].append(debt)

        def days(items):
            return max((r["days_overdue"] for r in items), default=0)

        ordered = sorted(
            groups,
            key=lambda party: (
                -days(groups[party]),
                -sum(r["outstanding_iqd"] for r in groups[party]),
                party,
            ),
        )
        for i, party in enumerate(ordered):
            items = groups[party]
            prefix = f"{direction}.customers.{i}"
            add(
                prefix + ".outstanding",
                sum(r["outstanding_iqd"] for r in items),
                "outstanding",
                debt_ids(items),
            )
            if all(r["due_date"] is not None for r in items):
                add(
                    prefix + ".days_overdue",
                    days(items),
                    "days_overdue",
                    debt_ids(items),
                    "days",
                )
            for j, debt in enumerate(
                sorted(
                    items,
                    key=lambda r: (r["due_date"] or "9999-12-31", r["obligation_id"]),
                )
            ):
                base = f"{prefix}.obligations.{j}"
                origin = origins[debt["obligation_id"]]
                add(
                    base + ".original",
                    origin["amount_iqd"],
                    "original_obligation",
                    [origin["source_id"]],
                )
                add(
                    base + ".outstanding",
                    debt["outstanding_iqd"],
                    "outstanding",
                    debt["source_ids"],
                )

    try:
        cash = ledger.cash(as_of)
    except TruthError:
        cash = {"amount_iqd": None, "source_ids": []}
    dues = [r for r in balances if r["kind"] == "payable" and r["due_date"] == str(end)]
    expected = [
        r
        for r in balances
        if r["kind"] == "receivable"
        and r["due_date"]
        and str(as_of) <= r["due_date"] <= str(end)
    ]
    if as_of <= end <= as_of + timedelta(days=29) and cash["amount_iqd"] is not None:
        j1 = ledger.j1(as_of, end)
        due_ids, expected_ids, cash_ids = (
            debt_ids(dues),
            debt_ids(expected),
            cash["source_ids"],
        )
        for key, source_key, sources in (
            ("cash_on_hand", "cash_iqd", cash_ids),
            ("supplier_due", "dues_iqd", due_ids),
            ("expected_collection", "expected_iqd", expected_ids),
            (
                "shortfall_with_collection",
                "shortfall_with_iqd",
                cash_ids + due_ids + expected_ids,
            ),
            (
                "shortfall_without_collection",
                "shortfall_without_iqd",
                cash_ids + due_ids,
            ),
        ):
            add("j1." + key, j1[source_key], key, sources)
    upcoming = ledger.upcoming(as_of, parameters.get("days", 7))
    due_ids, expected_ids, cash_ids = (
        debt_ids(upcoming["dues"]),
        debt_ids(upcoming["expected"]),
        cash["source_ids"],
    )
    for key, source_key, label, sources in (
        ("cash_on_hand", "cash_iqd", "cash_on_hand", cash_ids),
        ("dues_total", "dues_total_iqd", "supplier_dues", due_ids),
        ("expected_total", "expected_total_iqd", "expected_collections", expected_ids),
        (
            "position_confirmed",
            "position_confirmed_iqd",
            "position_confirmed",
            cash_ids + due_ids,
        ),
        (
            "position_with_expected",
            "position_with_expected_iqd",
            "position_with_expected",
            cash_ids + due_ids + expected_ids,
        ),
    ):
        add("upcoming." + key, upcoming[source_key], label, sources)
    for i, day in enumerate(upcoming["days"]):
        through_dues = [r for r in upcoming["dues"] if r["due_date"] <= day["date"]]
        through_expected = [
            r for r in upcoming["expected"] if r["due_date"] <= day["date"]
        ]
        today_dues = [
            r for r in through_dues if max(str(as_of), r["due_date"]) == day["date"]
        ]
        today_expected = [r for r in through_expected if r["due_date"] == day["date"]]
        for key, sources in (
            ("dues_iqd", debt_ids(today_dues)),
            ("expected_iqd", debt_ids(today_expected)),
            ("running_confirmed_iqd", cash_ids + debt_ids(through_dues)),
            (
                "running_with_expected_iqd",
                cash_ids + debt_ids(through_dues) + debt_ids(through_expected),
            ),
        ):
            add(f"upcoming.days.{i}.{key}", day[key], key.removesuffix("_iqd"), sources)
    return catalogue


def required_fields(spec, catalogue):
    if spec["expected_behavior"] != "answer":
        return set()
    calculation = spec["calculation"]
    if calculation == "sales":
        kind = spec["parameters"].get("kind", "all")
        result = (
            {"cash_sales"}
            if kind == "cash"
            else {"credit_sales"}
            if kind == "credit"
            else {"cash_sales", "credit_sales", "total_sales"}
        )
        if kind != "credit" and "unexplained_cash_difference" in catalogue:
            result.add("unexplained_cash_difference")
        return result
    if calculation == "debts":
        direction = spec["parameters"].get("direction", "receivable")
        directions = (
            {"receivables", "payables"}
            if direction == "both"
            else {"receivables" if direction == "receivable" else "payables"}
        )
        return {
            key
            for key in catalogue
            if key.split(".")[0] in directions
            and (
                key.endswith(".total_outstanding")
                or (
                    ".customers." in key
                    and key.endswith(".outstanding")
                    and ".obligations." not in key
                )
            )
        }
    if calculation == "margin":
        return {"gross_margin", "coverage_pct"}
    if calculation == "j1":
        return {
            "j1." + key
            for key in (
                "cash_on_hand",
                "supplier_due",
                "expected_collection",
                "shortfall_with_collection",
                "shortfall_without_collection",
            )
        }
    if calculation in {"upcoming", "cash"}:
        return (
            {"upcoming.cash_on_hand"}
            if calculation == "cash"
            else {
                "upcoming." + key
                for key in (
                    "cash_on_hand",
                    "dues_total",
                    "expected_total",
                    "position_confirmed",
                    "position_with_expected",
                )
            }
        )
    if calculation == "weekly_summary":
        result = {
            "cash_sales",
            "credit_sales",
            "total_sales",
            "weekly.owner_drawings",
            "weekly.operating_expenses",
            "weekly.collections",
            "receivables.total_outstanding",
        }
        if "unexplained_cash_difference" in catalogue:
            result.add("unexplained_cash_difference")
        if catalogue.get("coverage_pct", {}).get("value", 0) >= 80:
            result |= {"gross_margin", "coverage_pct"}
        return result
    return set()
