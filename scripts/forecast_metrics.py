"""Independent integer-IQD benchmark arithmetic, FINANCIAL_RULES §6/§7b.

No app imports, dataset I/O or forecast implementation. Rates may be fractional;
money and error sums remain integers, including rounded presentation MAE.
"""

from datetime import date, timedelta


def ratio(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def _integers(values):
    if any(type(v) is not int for v in values):
        raise ValueError("IQD_MUST_BE_INTEGER")


def rounded_mean(total, count):
    if count <= 0:
        raise ValueError("MISSING_METRIC_INPUT")
    sign = -1 if total < 0 else 1
    quotient, remainder = divmod(abs(total), count)
    return sign * (quotient + (2 * remainder >= count))


def balance_errors(predicted, realized):
    if not predicted or len(predicted) != len(realized):
        raise ValueError("METRIC_HORIZON_MISMATCH")
    _integers([*predicted, *realized])
    errors = [abs(p - r) for p, r in zip(predicted, realized, strict=True)]
    return {
        "scored_days": len(errors),
        "absolute_error_sum_iqd": sum(errors),
        "mae_iqd": rounded_mean(sum(errors), len(errors)),
        "worst_day_error_iqd": max(errors),
    }


def first_shortfall(days, scheduled_dues):
    for row in days:
        closing = row["closing_iqd"]
        following = str(date.fromisoformat(row["date"]) + timedelta(days=1))
        due = scheduled_dues.get(following, 0)
        _integers([closing, due])
        if closing < 0 or closing < due:
            return row["date"]
    return None


def shortfall_timing(predicted_date, realized_date):
    error = (
        abs(
            (
                date.fromisoformat(predicted_date) - date.fromisoformat(realized_date)
            ).days
        )
        if predicted_date and realized_date
        else None
    )
    return {
        "predicted_date": predicted_date,
        "realized_date": realized_date,
        "absolute_error_days": error,
        **ratio(int(error is not None and error <= 2), int(realized_date is not None)),
    }


def false_ok(cases):
    numerator = denominator = 0
    for case in cases:
        _integers(list(case.values()))
        due = case["amount_due_iqd"]
        if due <= 0:
            raise ValueError("INVALID_INVOICE_AMOUNT")
        predicted_ok = (
            case["predicted_closing_iqd"] + case["predicted_payment_iqd"] >= due
        )
        realized_ok = case["realized_closing_iqd"] + case["realized_payment_iqd"] >= due
        denominator += not realized_ok
        numerator += predicted_ok and not realized_ok
    return {**ratio(numerator, denominator), "eligible_invoices": len(cases)}
