"""D58: the interpretation is accepted only when its copied fragments are proven."""

import asyncio
import json
from datetime import date

import pytest

from app.agents.interpreter import interpret, parse
from app.services.business_clock import BusinessClock


def obj(**overrides):
    value = {
        "behavior": "answer",
        "intent": "sales",
        "reason": None,
        "sales_kind": "all",
        "direction": "receivable",
        "overdue_only": False,
        "movement": None,
        "days": None,
        "party_mentions": [],
        "collection_party_mentions": [],
        "without_collection": False,
        "time": {"type": "none", "evidence": None},
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False)


def test_accepts_copied_digits_in_arabic_indic_form():
    result = parse(
        obj(time={"type": "since_day", "day": 10, "evidence": "من يوم ١٠"}),
        "المبيعات من يوم ١٠ لليوم",
    )
    assert result.time.day == 10


@pytest.mark.parametrize(
    ("time", "question"),
    [
        ({"type": "since_day", "day": 11, "evidence": "من يوم ١٠"}, "من يوم ١٠ لليوم"),
        ({"type": "today", "evidence": "باچر"}, "شكد بعت اليوم"),
        ({"type": "today", "evidence": None}, "شكد بعت اليوم"),
        ({"type": "month", "month": 7, "evidence": "بآب"}, "شكد ربحت بآب"),
        ({"type": "none", "evidence": "اليوم"}, "شكد بعت اليوم"),
    ],
)
def test_rejects_unproven_time(time, question):
    assert parse(obj(time=time), question) is None


def test_month_name_and_number_words_prove_integers():
    assert parse(
        obj(time={"type": "month", "month": 8, "evidence": "بآب"}), "شكد ربحت بآب"
    )
    assert parse(
        obj(time={"type": "last_n_days", "n": 14, "evidence": "اخر اسبوعين"}),
        "بيع آخر اسبوعين",
    )


def test_party_mentions_must_be_verbatim_after_normalization():
    assert parse(obj(intent="debts", party_mentions=["ابو حيدر"]), "أبو حيدر شكد عليه؟")
    assert (
        parse(obj(intent="debts", party_mentions=["ابو علي"]), "أبو حيدر شكد عليه؟")
        is None
    )


def test_days_must_appear_in_the_question():
    assert (
        parse(obj(intent="upcoming_obligations", days=5), "شنو علي خلال ٥ ايام")
        is not None
    )
    assert (
        parse(obj(intent="upcoming_obligations", days=9), "شنو علي خلال ٥ ايام") is None
    )


@pytest.mark.parametrize(
    "bad",
    [
        obj(behavior="refuse", intent="sales"),
        obj(behavior="answer", intent="unsupported_write"),
        obj(behavior="clarify", reason=None),
        obj(behavior="answer", reason="OUT_OF_SCOPE"),
        obj(intent="period_movements"),
        obj(extra=1),
        "not json",
        "[]",
    ],
)
def test_rejects_inconsistent_or_open_objects(bad):
    assert parse(bad, "شكد بعت") is None


class Reply:
    def __init__(self, content):
        self.content = content


class Client:
    def __init__(self, *contents):
        self.contents, self.calls = list(contents), []

    async def complete(self, messages, *, tools=(), json_mode=False):
        self.calls.append((messages, tools, json_mode))
        return Reply(self.contents.pop(0))


CLOCK = BusinessClock(date(2026, 9, 28))


def test_interpret_retries_once_then_fails_closed():
    client = Client("oops", obj(time={"type": "today", "evidence": "اليوم"}))
    result = asyncio.run(interpret("شكد بعت اليوم", client=client, clock=CLOCK))
    assert result.time.type == "today"
    assert len(client.calls) == 2 and client.calls[0][2] is True
    payload = json.loads(client.calls[0][0][1]["content"])
    assert payload == {
        "today_weekday": "mon",
        "today": "2026-09-28",
        "question": "شكد بعت اليوم",
        "trust": "quoted_merchant_text",
    }
    client = Client("oops", "still bad")
    assert asyncio.run(interpret("شكد", client=client, clock=CLOCK)) is None
    assert len(client.calls) == 2
