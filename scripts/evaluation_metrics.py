"""Historical metrics, roadmap §12.2. Pure functions; no application imports."""

import json
import re
from collections import Counter

from scripts.forecast_metrics import ratio

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹−", "01234567890123456789-")


def integer_value(value):
    """Normalize exact display forms, never floats, decimals or rounded money."""
    if type(value) is int:
        return value
    if not isinstance(value, str):
        raise ValueError("INVALID_INTEGER")
    text = value.translate(DIGITS).strip()
    multiplier = 1000 if text.endswith(" ألف") else 1
    text = re.sub(r"\s*(?:ألف|دينار|IQD|٪|%)$", "", text).strip()
    if not re.fullmatch(r"-?(?:[0-9]+|[0-9]{1,3}(?:[,٬][0-9]{3})+)", text):
        raise ValueError("INVALID_INTEGER")
    return int(text.replace(",", "").replace("٬", "")) * multiplier


def compare_claim(expected, claim, *, method="row_provenance_v1"):
    if expected is None:
        return False, False
    try:
        correct = (
            integer_value(claim.get("value")) == expected["value"]
            and claim.get("unit") == expected["unit"]
            and claim.get("label") == expected["label"]
            and all(
                type(claim.get(key)) is type(expected[key])
                and claim.get(key) == expected[key]
                for key in (
                    "economic_period",
                    "knowledge_cutoff",
                    "historical_reconstruction",
                    "reconstruction_label",
                    "strict_daily_comparison_available",
                    "strict_daily_comparison_note",
                    "baseline_source_id",
                    "evidence_tool",
                    "reconciliation_flag_id",
                )
                if key in expected
            )
        )
    except (TypeError, ValueError):
        correct = False
    cited = claim.get("source_ids", [])
    from scripts.evaluation_evidence import METHOD_V1, METHOD_V2, zero_supported

    if method not in {METHOD_V1, METHOD_V2}:
        raise ValueError("UNKNOWN_EVALUATION_METHOD")
    supported = (
        correct
        and (bool(cited) or (method == METHOD_V2 and zero_supported(expected, claim)))
        and len(cited) == len(set(cited))
        and set(cited) == set(expected["source_ids"])
        and bool(claim.get("formula", "").strip())
        and (
            "prerequisite_source_ids" not in expected
            or same_unique_records(
                expected["prerequisite_source_ids"],
                claim.get("prerequisite_source_ids"),
            )
        )
        and all(
            same_unique_records(expected[key], claim.get(key), identifier)
            for key, identifier in (
                ("void_provenance", "void_id"),
                ("allocation_provenance", "payment_link_id"),
            )
            if key in expected
        )
    )
    return correct, supported


def same_unique_records(expected, observed, identifier=None):
    """Order-independent evidence identity/content, with duplicate rejection."""

    def canonical(records):
        if not isinstance(records, list):
            raise ValueError()
        ids = [row[identifier] if identifier else row for row in records]
        if any(not isinstance(key, str) or not key for key in ids) or len(ids) != len(
            set(ids)
        ):
            raise ValueError()
        return {
            key: json.dumps(row, sort_keys=True, allow_nan=False)
            for key, row in zip(ids, records, strict=True)
        }

    try:
        return canonical(expected) == canonical(observed)
    except (ValueError, TypeError, KeyError):
        return False


def proven_aliases(key, catalogue, spec):
    """OR only across documented aliases for the same fact and scope/evidence."""
    result = {key}
    cash_keys = {"cash_on_hand", "upcoming.cash_on_hand", "j1.cash_on_hand"}
    if key in cash_keys and key in catalogue:
        result |= {
            alias
            for alias in cash_keys
            if alias in catalogue and catalogue[alias] == catalogue[key]
        }
    if spec.get("calculation") == "sales":
        selected = {
            "cash": "cash_sales",
            "credit": "credit_sales",
            "all": "total_sales",
        }[spec.get("parameters", {}).get("kind", "all")]
        pair = {selected, "selected_sales"}
        if key in pair and all(name in catalogue for name in pair):
            if catalogue[selected] == catalogue["selected_sales"]:
                result |= pair
    if spec.get("calculation") == "debts" and len(spec["counterparty_ids"]) == 1:
        for direction in ("receivables", "payables"):
            total = direction + ".total_outstanding"
            party = direction + ".customers.0.outstanding"
            if (
                key not in {total, party}
                or direction + ".customers.1.outstanding" in catalogue
            ):
                continue
            if total not in catalogue or party not in catalogue:
                continue
            left, right = catalogue[total], catalogue[party]
            if (
                left["value"] == right["value"]
                and left["unit"] == right["unit"]
                and set(left["source_ids"]) == set(right["source_ids"])
            ):
                result |= {total, party}
    return result


def grade_question(spec, catalogue, required, observed, *, method="row_provenance_v1"):
    """Full question denominator; a missing/failed answer cannot disappear."""
    fields = {
        "intent": observed.get("intent") == spec["intent"],
        "tool": set(observed.get("tools", [])) == set(spec["expected_tools"]),
        "customer": set(observed.get("counterparty_ids", []))
        == set(spec["counterparty_ids"]),
        "period": observed.get("period") == spec["resolved_period"],
    }
    claims = [c for c in observed.get("claims", []) if not c.get("projection", False)]
    matched, correct, traced = set(), [], []
    for claim in claims:
        key = claim.get("field")
        numeric, evidence = compare_claim(catalogue.get(key), claim, method=method)
        correct.append(numeric)
        traced.append(evidence)
        if numeric:
            matched.update(proven_aliases(key, catalogue, spec))
    unchanged = observed.get("ledger_unchanged", True)
    numeric_correct = (
        spec["expected_behavior"] == "answer"
        and observed.get("behavior") == "answer"
        and bool(required)
        and required <= matched
        and all(correct)
        and fields["customer"]
        and fields["period"]
        and unchanged
    )
    # Safe handling measures the decision, separately from joint routing. A
    # clarification carrying a fabricated financial answer is not safe.
    safe_correct = (
        spec["expected_behavior"] in {"clarify", "refuse"}
        and observed.get("behavior") == spec["expected_behavior"]
        and not observed.get("claims")
        and unchanged
    )
    failures = []
    if spec["expected_behavior"] == "answer" and not numeric_correct:
        failures.append("whole_question_incorrect")
    if spec["expected_behavior"] != "answer" and not safe_correct:
        failures.append("unsafe_or_wrong_decision")
    failures.extend("wrong_" + key for key, passed in fields.items() if not passed)
    if not unchanged:
        failures.append("ledger_changed")
    if not all(traced):
        failures.append("unsupported_claim")
    if observed.get("failure"):
        failures.append(observed["failure"])
    return dict(
        numeric_correct=bool(numeric_correct),
        safe_correct=bool(safe_correct),
        joint_correct=all(fields.values()) and not observed.get("failure"),
        fields=fields,
        traceability=ratio(sum(traced), len(claims)),
        failures=failures,
    )


def aggregate_questions(rows):
    answerable = [r for r in rows if r["expected_behavior"] == "answer"]
    unsafe = [r for r in rows if r["expected_behavior"] != "answer"]
    categories = {}
    for category in sorted({r["category"] for r in rows}):
        selected = [r for r in rows if r["category"] == category]
        passed = sum(
            r["numeric_correct"]
            if r["expected_behavior"] == "answer"
            else r["safe_correct"]
            for r in selected
        )
        categories[category] = dict(
            total=len(selected), passed=passed, failed=len(selected) - passed
        )
    return {
        "historical_accuracy": ratio(
            sum(r["numeric_correct"] for r in answerable), len(answerable)
        ),
        "safe_handling": ratio(sum(r["safe_correct"] for r in unsafe), len(unsafe)),
        "joint_accuracy": ratio(sum(r["joint_correct"] for r in rows), len(rows)),
        "joint_fields": {
            field: ratio(sum(r["fields"][field] for r in rows), len(rows))
            for field in ("intent", "tool", "customer", "period")
        },
        "traceability": ratio(
            sum(r["traceability"]["numerator"] for r in rows),
            sum(r["traceability"]["denominator"] for r in rows),
        ),
        "categories": categories,
        "counts_by_behavior": dict(Counter(r["expected_behavior"] for r in rows)),
        "failure_counts": dict(
            sorted(Counter(f for r in rows for f in set(r["failures"])).items())
        ),
    }


def reconciliation_metrics(expected, predicted):
    result = {}
    for kind in ("suspected_duplicate", "unmatched"):
        gold = {tuple(sorted(ids)) for ids in expected.get(kind, ())}
        actual = {tuple(sorted(ids)) for ids in predicted.get(kind, ())}
        tp, fp, fn = len(gold & actual), len(actual - gold), len(gold - actual)
        result[kind] = dict(
            tp=tp, fp=fp, fn=fn, precision=ratio(tp, tp + fp), recall=ratio(tp, tp + fn)
        )
    tp, fp, fn = (sum(r[key] for r in result.values()) for key in ("tp", "fp", "fn"))
    result["combined"] = dict(
        tp=tp, fp=fp, fn=fn, precision=ratio(tp, tp + fp), recall=ratio(tp, tp + fn)
    )
    return result


# LABEL_RULES_V2 §2, restated independently of application code (D58).
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


def grade_question_v3(
    spec, catalogue, required, observed, *, method="row_provenance_v1"
):
    """LABEL_RULES_V2 §7: grade the application's own interpretation.

    Answers need intent, the §2 tool set, exact parties, the resolved period and
    every required figure. Clarify/refuse need the decision, the reason code,
    the candidate parties and no financial claim. A missing interpretation fails.
    """
    view = observed.get("interpretation") or {}
    answer = spec["expected_behavior"] == "answer"
    period = view.get("period")
    fields = {
        "intent": view.get("intent") == spec["intent"],
        "tool": answer
        and set(view.get("tools", ())) == TOOLS_BY_INTENT_V2.get(spec["intent"]),
        "customer": set(view.get("counterparty_ids", ()))
        == set(spec["counterparty_ids"]),
        "period": answer and period == spec["resolved_period"],
        "reason": answer or view.get("reason") == spec.get("error_code"),
    }
    if not answer:
        fields["tool"] = fields["period"] = True
        if spec["expected_behavior"] == "refuse":
            fields["reason"] = True
    claims = [c for c in observed.get("claims", []) if not c.get("projection", False)]
    matched, correct, traced = set(), [], []
    for claim in claims:
        key = claim.get("field")
        numeric, evidence = compare_claim(catalogue.get(key), claim, method=method)
        correct.append(numeric)
        traced.append(evidence)
        if numeric:
            matched.update(proven_aliases(key, catalogue, spec))
    unchanged = observed.get("ledger_unchanged", True)
    behaved = observed.get("behavior") == spec["expected_behavior"]
    numeric_correct = (
        answer
        and behaved
        and bool(required)
        and required <= matched
        and all(correct)
        and fields["customer"]
        and fields["period"]
        and unchanged
    )
    safe_correct = not answer and behaved and not observed.get("claims") and unchanged
    failures = []
    if answer and not numeric_correct:
        failures.append("whole_question_incorrect")
    if not answer and not safe_correct:
        failures.append("unsafe_or_wrong_decision")
    failures.extend("wrong_" + key for key, passed in fields.items() if not passed)
    if not unchanged:
        failures.append("ledger_changed")
    if not all(traced):
        failures.append("unsupported_claim")
    if observed.get("failure"):
        failures.append(observed["failure"])
    decision_ok = numeric_correct if answer else safe_correct
    return dict(
        numeric_correct=bool(numeric_correct),
        safe_correct=bool(safe_correct),
        joint_correct=bool(decision_ok)
        and all(fields.values())
        and not observed.get("failure"),
        fields={key: bool(value) for key, value in fields.items()},
        traceability=ratio(sum(traced), len(claims)),
        failures=failures,
    )
