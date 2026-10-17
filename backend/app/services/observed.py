"""Application history boundary: roadmap §6.1/§10.4; never a host-clock date."""

from datetime import date

from app.services.business_clock import DEFAULT_BUSINESS_AS_OF, BusinessClock
from app.services.errors import FinancialRuleError

OBSERVED_START = date(2026, 7, 1)
OBSERVED_END = DEFAULT_BUSINESS_AS_OF


def observed_day(clock: BusinessClock) -> date:
    if not isinstance(clock, BusinessClock) or not (
        OBSERVED_START <= clock.today <= OBSERVED_END
    ):
        raise FinancialRuleError(
            "VALIDATION_ERROR", details={"reason": "OUTSIDE_OBSERVED_DATA"}
        )
    return clock.today
