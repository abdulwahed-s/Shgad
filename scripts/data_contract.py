"""Offline file formats and I/O only. No financial calculations or app imports."""

import csv
import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, timedelta
from pathlib import Path

TRANSACTION_FIELDS = [
    "transaction_id",
    "source_id",
    "source_system",
    "source_row",
    "import_batch_id",
    "occurred_at",
    "recorded_at",
    "source",
    "client_entry_id",
    "business_date",
    "type",
    "amount_iqd",
    "counterparty_id",
    "obligation_id",
    "due_date",
    "category_id",
    "quantity",
    "description",
    "status",
    "idempotency_key",
]
OBLIGATION_FIELDS = [
    "obligation_id",
    "kind",
    "origin_transaction_id",
    "counterparty_id",
    "original_amount_iqd",
    "due_date",
]
LINK_FIELDS = [
    "payment_link_id",
    "payment_transaction_id",
    "obligation_id",
    "amount_iqd",
    "match_basis",
    "created_at",
]
VOID_FIELDS = [
    "client_entry_id",
    "reason",
    "void_id",
    "transaction_id",
    "source_id",
    "voided_at",
]
INT_FIELDS = {
    "source_row",
    "amount_iqd",
    "quantity",
    "buy_price_iqd",
    "sell_price_iqd",
    "original_amount_iqd",
}
NULLABLE_FIELDS = {
    "recorded_at",
    "client_entry_id",
    "counterparty_id",
    "obligation_id",
    "due_date",
    "category_id",
    "quantity",
    "buy_price_iqd",
    "sell_price_iqd",
}
CATEGORIES = {
    "sales",
    "debt_balance",
    "supplier_dues",
    "weekly_summary",
    "cash_sufficiency",
    "margin",
    "drawings_expenses",
    "relative_dates",
    "reconciliation",
    "missing_data",
    "ambiguous_customer",
    "ambiguous_date",
    "invalid_date",
    "contradictory_records",
    "unsupported_request",
    "injection",
}
TOOLS = {"get_sales", "get_debts", "reconcile", "forecast", "get_margin"}
_OUTPUT_PATHS = ContextVar("generated_output_paths", default=None)
FIXTURES = {
    "small_happy_path",
    "three_instalments_void",
    "cash_difference_review",
    "seven_day_overdue",
    "missing_opening_balance",
    "missing_costs",
    "ambiguous_customers",
    "malicious_descriptions",
    "forecast_scenarios",
}
INTENTS = {
    "sales",
    "debts",
    "supplier_sufficiency",
    "upcoming_obligations",
    "weekly_summary",
    "estimated_gross_margin",
    "reconciliation",
    "unsupported_write",
    "unsafe_instruction",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@contextmanager
def capture_artifacts():
    """Track only actual writes; never discover or hash unrelated input files."""
    written = set()
    token = _OUTPUT_PATHS.set(written)
    try:
        yield written
    finally:
        _OUTPUT_PATHS.reset(token)


def _record_output(path):
    written = _OUTPUT_PATHS.get()
    if written is not None:
        written.add(Path(path).resolve())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _record_output(path)


def write_jsonl(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values
        ),
        encoding="utf-8",
        newline="\n",
    )
    _record_output(path)


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    _record_output(path)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return [
        {
            k: None
            if v == "" and k in NULLABLE_FIELDS
            else int(v)
            if k in INT_FIELDS and v != ""
            else v
            for k, v in row.items()
        }
        for row in rows
    ]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review_signature(value):
    """Bind human approval to exact reviewed text or structured labels."""
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def question_review_signature(question):
    return review_signature(
        {key: value for key, value in question.items() if key != "arabic_review"}
    )


def validate_question(question):
    """Validate only the public format. Errors never include question content."""

    def check(condition):
        if not condition:
            raise ValueError("Invalid question format")

    def business_date(value):
        check(isinstance(value, str))
        parsed = date.fromisoformat(value)
        check(str(parsed) == value)
        return parsed

    check(
        isinstance(question, dict)
        and set(question)
        == {
            "id",
            "category",
            "question_ar",
            "business_as_of",
            "dataset",
            "arabic_review",
            "spec",
        }
    )
    check(isinstance(question["id"], str) and bool(question["id"].strip()))
    check(
        isinstance(question["question_ar"], str)
        and bool(question["question_ar"].strip())
    )
    check(question["category"] in CATEGORIES)
    check(question["dataset"] in {"primary"} | FIXTURES)
    check(question["arabic_review"] in {"pending", "approved"})
    as_of = business_date(question["business_as_of"])
    check(date(2026, 7, 1) <= as_of <= date(2026, 9, 28))
    spec = question["spec"]
    required = {
        "intent",
        "expected_tools",
        "counterparty_ids",
        "resolved_period",
        "expected_behavior",
        "calculation",
        "parameters",
    }
    check(
        isinstance(spec, dict) and required <= spec.keys() <= required | {"error_code"}
    )
    check(spec["intent"] in INTENTS)
    check(spec["expected_behavior"] in {"answer", "clarify", "refuse"})
    for key in ("expected_tools", "counterparty_ids"):
        values = spec[key]
        check(isinstance(values, list) and all(isinstance(v, str) for v in values))
        check(len(values) == len(set(values)))
    check(set(spec["expected_tools"]) <= TOOLS)
    parties = {f"CUST-{i:02}" for i in range(1, 7)} | {"SUP-01", "SUP-02"}
    check(set(spec["counterparty_ids"]) <= parties)
    calc = spec["calculation"]
    allowed_params = {
        "sales": {"kind"},
        "debts": {"direction", "overdue_only"},
        "upcoming": {"days"},
        "cash": set(),
        "margin": set(),
        "weekly_summary": set(),
        "j1": set(),
        "none": set(),
    }
    check(calc in allowed_params)
    params = spec["parameters"]
    check(isinstance(params, dict) and params.keys() <= allowed_params[calc])
    if "kind" in params:
        check(params["kind"] in {"cash", "credit", "all"})
    if "direction" in params:
        check(params["direction"] in {"receivable", "payable", "both"})
    if "overdue_only" in params:
        check(type(params["overdue_only"]) is bool)
    days = params.get("days", 7)
    check(type(days) is int and 1 <= days <= 30)
    period = spec["resolved_period"]
    if period is not None:
        check(isinstance(period, dict) and set(period) == {"start", "end"})
        start, end = business_date(period["start"]), business_date(period["end"])
        check(date(2026, 7, 1) <= start <= end)
        if calc in {"sales", "margin", "weekly_summary", "cash", "debts"}:
            check(end <= as_of)
        elif calc in {"upcoming", "j1"}:
            check(start == as_of and end <= as_of + timedelta(days=29))
            if calc == "upcoming":
                check(end == as_of + timedelta(days=days - 1))
    elif spec["expected_behavior"] == "answer":
        check(calc in {"cash", "debts"})
    if spec["expected_behavior"] == "answer":
        check(calc != "none")
    if "error_code" in spec:
        check(isinstance(spec["error_code"], str) and bool(spec["error_code"]))
    return question


QUESTION_SCHEMA_V2 = "shgad-question-v2"
INTENTS_V2 = INTENTS | {"cash_on_hand", "period_movements", "out_of_scope"}
# LABEL_RULES_V2 §2: the tool set each answer intent implies.
TOOLS_BY_INTENT_V2 = {
    "sales": {"get_sales"},
    "cash_on_hand": {"get_debts"},
    "debts": {"get_debts"},
    "upcoming_obligations": {"get_debts"},
    "supplier_sufficiency": {"get_debts", "forecast"},
    "weekly_summary": {"get_sales", "get_debts", "get_margin", "reconcile"},
    "period_movements": {"get_sales"},
    "estimated_gross_margin": {"get_margin"},
    "reconciliation": {"reconcile"},
}
CALCULATION_BY_INTENT_V2 = {
    "sales": "sales",
    "cash_on_hand": "cash",
    "debts": "debts",
    "upcoming_obligations": "upcoming",
    "supplier_sufficiency": "j1",
    "weekly_summary": "weekly_summary",
    "period_movements": "sales",
    "estimated_gross_margin": "margin",
    "reconciliation": "none",
}
ERROR_CODES_V2 = {
    "AMBIGUOUS_COUNTERPARTY",
    "UNKNOWN_COUNTERPARTY",
    "AMBIGUOUS_DATE",
    "VALIDATION_ERROR",
    "NO_HISTORICAL_DATA",
    "MISSING_OPENING_BALANCE",
    "MISSING_COSTS",
    "REVIEW_REQUIRED",
    "OUT_OF_SCOPE",
}
MOVEMENTS_V2 = {
    "owner_drawings",
    "operating_expenses",
    "supplier_payments",
    "collections",
    "capital_injections",
    "drawings_and_expenses",
}
FLAG_TYPES_V2 = {
    "unmatched",
    "suspected_duplicate",
    "partially_paid",
    "overdue",
    "ambiguous",
}


def validate_question_v2(question):
    """LABEL_RULES_V2 format (D58). Errors never include question content."""

    def check(condition):
        if not condition:
            raise ValueError("Invalid question format")

    def business_date(value):
        check(isinstance(value, str))
        parsed = date.fromisoformat(value)
        check(str(parsed) == value)
        return parsed

    check(
        isinstance(question, dict)
        and set(question)
        == {
            "id",
            "category",
            "question_ar",
            "business_as_of",
            "dataset",
            "arabic_review",
            "spec",
        }
    )
    check(isinstance(question["id"], str) and bool(question["id"].strip()))
    check(
        isinstance(question["question_ar"], str)
        and bool(question["question_ar"].strip())
    )
    check(question["category"] in CATEGORIES)
    check(question["dataset"] in {"primary"} | FIXTURES)
    check(question["arabic_review"] in {"pending", "approved"})
    as_of = business_date(question["business_as_of"])
    check(date(2026, 7, 1) <= as_of <= date(2026, 9, 28))
    spec = question["spec"]
    required = {
        "intent",
        "expected_tools",
        "counterparty_ids",
        "resolved_period",
        "expected_behavior",
        "calculation",
        "parameters",
    }
    check(
        isinstance(spec, dict) and required <= spec.keys() <= required | {"error_code"}
    )
    intent, behavior = spec["intent"], spec["expected_behavior"]
    check(intent in INTENTS_V2 and behavior in {"answer", "clarify", "refuse"})
    for key in ("expected_tools", "counterparty_ids"):
        values = spec[key]
        check(isinstance(values, list) and all(isinstance(v, str) for v in values))
        check(len(values) == len(set(values)))
    parties = {f"CUST-{i:02}" for i in range(1, 7)} | {"SUP-01", "SUP-02"}
    check(set(spec["counterparty_ids"]) <= parties)
    refusal = intent in {"unsupported_write", "unsafe_instruction"}
    check(refusal == (behavior == "refuse"))
    check((behavior == "clarify") == ("error_code" in spec))
    if behavior == "clarify":
        check(spec["error_code"] in ERROR_CODES_V2)
    params = spec["parameters"]
    check(isinstance(params, dict))
    if "kind" in params:
        check(params["kind"] in {"cash", "credit", "all"})
    if "direction" in params:
        check(params["direction"] in {"receivable", "payable", "both"})
    if "overdue_only" in params:
        check(type(params["overdue_only"]) is bool)
    if "movement" in params:
        check(params["movement"] in MOVEMENTS_V2)
    if "types" in params:
        types = params["types"]
        check(isinstance(types, list) and set(types) <= FLAG_TYPES_V2)
    days = params.get("days", 7)
    check(type(days) is int and 1 <= days <= 30)
    check(
        params.keys()
        <= {"kind", "direction", "overdue_only", "movement", "types", "days"}
    )
    if behavior != "answer":
        # LABEL_RULES_V2 §5: decisions carry no tools or period.
        check(spec["expected_tools"] == [] and spec["resolved_period"] is None)
        check(spec["calculation"] == "none")
        if behavior == "refuse" or spec["error_code"] != "AMBIGUOUS_COUNTERPARTY":
            check(spec["counterparty_ids"] == [])
        return question
    check(intent in TOOLS_BY_INTENT_V2)
    check(set(spec["expected_tools"]) == TOOLS_BY_INTENT_V2[intent])
    check(spec["calculation"] == CALCULATION_BY_INTENT_V2[intent])
    if intent == "period_movements":
        check("movement" in params)
    period = spec["resolved_period"]
    check(isinstance(period, dict) and set(period) == {"start", "end"})
    start, end = business_date(period["start"]), business_date(period["end"])
    check(date(2026, 7, 1) <= start <= end)
    if intent in {"cash_on_hand", "debts"}:
        check(start == end == as_of)
    elif intent == "upcoming_obligations":
        check(start == as_of and end == as_of + timedelta(days=days - 1))
    elif intent == "supplier_sufficiency":
        check(start == as_of < end <= as_of + timedelta(days=29))
    else:
        check(end <= as_of)
    return question
