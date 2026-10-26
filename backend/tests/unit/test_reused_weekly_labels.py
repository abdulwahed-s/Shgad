"""Reuse D45 keys verbatim; this is not a new language approval."""

import pytest

from app.agents.messages_ar import text


@pytest.mark.parametrize(
    "key,value",
    (
        ("collection", "تحصيل دين"),
        ("operatingExpense", "مصروف المحل"),
        ("ownerDrawing", "سحب صاحب المحل"),
        ("supplierPayment", "دفعة للمجهز"),
        ("capitalInjection", "إضافة رأس مال"),
    ),
)
def test_reused_weekly_label_is_exact_d45_text(key, value):
    assert text(key) == value
