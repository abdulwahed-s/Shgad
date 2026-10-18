"""Daily workflow integration of D21 consecutive-count and audit primitives."""

from app.db.records import atomic_import
from app.schemas.daily_close import DailyCloseView, ResolutionReceipt, ResolvedReview
from app.schemas.entries import EntryReceipt
from app.schemas.forecast import Amount
from app.services.errors import FinancialRuleError
from app.services.evidence import project_item
from app.services.ledger_audit import read_ledger, resolve_difference
from app.services.ledger_rules import daily_close
from app.services.observed import OBSERVED_START, observed_day
from app.services.validation import parse_business_date, parse_timestamp


def _day(value, clock):
    day = parse_business_date(value)
    if not OBSERVED_START <= day <= observed_day(clock):
        raise FinancialRuleError(
            "VALIDATION_ERROR", details={"reason": "OUTSIDE_OBSERVED_DATA"}
        )
    return day


def daily_close_view(connection, business_date, *, clock, known_at) -> DailyCloseView:
    day, known = _day(business_date, clock), parse_timestamp(known_at)
    connection.execute("SAVEPOINT daily_close_view")
    try:
        snapshot = read_ledger(connection, as_of=day, known_at=known)
        close = daily_close(
            snapshot.transactions,
            business_date=day,
            voids=snapshot.voids,
            known_at=known,
        )
        by_id = {r.transaction_id: r for r in snapshot.transactions}

        def amount(value, key, formula, sources, kind="calculated"):
            return Amount(
                amount_iqd=value,
                kind="missing" if value is None else kind,
                label_key=key,
                formula=formula,
                source_ids=sources,
            )

        count_sources = (
            (by_id[close.closing_count_transaction_id].source_id,)
            if close.closing_count_transaction_id
            else ()
        )
        previous_sources = (
            (by_id[close.previous_count_transaction_id].source_id,)
            if close.previous_count_transaction_id
            else ()
        )
        difference = amount(
            close.unexplained_difference_iqd,
            "unexplained_cash_difference",
            "count[d] - (count[d-1] + recorded inflows[d] - recorded outflows[d])",
            close.source_ids,
            "flagged",
        )
        reviews = tuple(
            ResolvedReview(
                review_id=r.review_id,
                resolution=r.resolution,
                entry=project_item(connection, by_id[r.transaction_id], known_at=known)
                if r.transaction_id in by_id
                else None,
                note=r.note,
                created_at=r.created_at,
            )
            for r in snapshot.reviews
            if r.business_date == day
        )
        return DailyCloseView(
            date=day,
            count=amount(
                close.count_iqd,
                "cash_count",
                "closing DAILY_CASH_COUNT[d]",
                count_sources,
                "verified",
            ),
            previous_count=amount(
                close.previous_count_iqd,
                "previous_cash_count",
                "closing DAILY_CASH_COUNT[d-1]",
                previous_sources,
                "verified",
            ),
            expected_close=amount(
                close.expected_close_iqd,
                "expected_close",
                "count[d-1] + recorded inflows[d] - recorded outflows[d]",
                close.source_ids,
            ),
            unexplained_difference=difference,
            remaining_difference=difference,
            resolved=reviews,
            rows=close.source_ids,
        )
    finally:
        connection.execute("RELEASE SAVEPOINT daily_close_view")


def review_daily_close(
    connection, request, business_date, *, clock, recorded_at
) -> ResolutionReceipt:
    day = _day(business_date, clock)
    with atomic_import(connection):
        result = resolve_difference(
            connection, request, business_date=day, recorded_at=recorded_at
        )
        return ResolutionReceipt(
            entry=EntryReceipt(
                transaction_id=result.entry.transaction_id,
                source_id=result.entry.source_id,
                duplicate=result.duplicate,
            )
            if result.entry
            else None,
            daily_close=daily_close_view(
                connection, day, clock=clock, known_at=recorded_at
            ),
            duplicate=result.duplicate,
        )
