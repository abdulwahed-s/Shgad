"""Fixed merchant copy with human approval bound to each exact reviewed text.

Imported notes are never used as templates or executable instructions.
"""

import hashlib
from dataclasses import dataclass
from typing import Literal

from app.agents.arabic_review import review_status


@dataclass(frozen=True)
class DraftMessage:
    text: str
    status: Literal["PENDING_REVIEW", "APPROVED"] = "PENDING_REVIEW"


MESSAGES = {
    key: DraftMessage(value, status=review_status(key, value))
    for key, value in {
        "period": "للفترة من {start} إلى {end}.",
        "customer": "الحساب: {name}.",
        "no_figures": "ما عندي أرقام موثقة كافية لهالجواب.",
        "collections_expected_not_guaranteed": "التحصيل المتوقع مو مضمون.",
        "forecast": "هذا تقدير نقدي، مو مبلغ مؤكد. السيناريو: {scenarios}.",
        "base": "أساسي",
        "conservative": "متحفظ",
        "stress": "ضغط",
        "margin_excludes_unrecorded_costs": (
            "هذا هامش إجمالي تقديري للمبيعات المسجلة المسعّرة؛ "
            "المصاريف غير المسجلة مو مشمولة."
        ),
        "unexplained_difference_excluded": (
            "الفرق غير المفسّر مو داخل بحساب تغطية المبيعات المسجلة."
        ),
        "coverage": "يشمل {value} من المبيعات المسجلة.",
        "difference_note": "الفرق غير مفسّر، وما نحدد سببه من هالسجلات.",
        "recorded_cash_sales": "المبيعات النقدية المسجلة",
        "credit_sales": "المبيعات الآجلة المسجلة",
        "total_recorded_sales": "مجموع المبيعات المسجلة",
        "unexplained_cash_difference": "الفرق غير المفسّر",
        "cash_on_hand": "النقد المتوفر",
        "supplier_due": "المبلغ المستحق للمجهز",
        "supplier_dues": "مستحقات المجهزين",
        "expected_collection": "التحصيل المتوقع",
        "expected_collections": "التحصيل المتوقع",
        "shortfall_with_collection": "النقص إذا صار التحصيل المتوقع",
        "shortfall_without_collection": "النقص بدون التحصيل المتوقع",
        "position_confirmed": "الرصيد بعد المستحقات بالنقد المؤكد",
        "position_with_expected": "الرصيد بعد المستحقات ويا التحصيل المتوقع",
        "receivables": "بذمة الزبائن",
        "payables": "مستحقات المجهزين",
        "estimated_gross_margin": "هامش إجمالي تقديري",
        "after_recorded_expenses": "بعد المصاريف المسجلة",
        "unpriced_sales_count": "عدد المبيعات بدون كلفة مسجلة",
        "reconciliation_amount": "مبلغ يحتاج مراجعة",
        "flag_sources": "مصادر القيد: {ids}.",
        "expense_kind_unrecorded": (
            "هذا مجموع مصاريف المحل المسجلة؛ التفصيل حسب نوع المصروف مو مسجل."
        ),
        "review_unmatched_payment": "راجع الدفعة اللي ما تطابقت وكمل تفاصيلها.",
        "review_duplicate_payment": "راجع القيود المتشابهة قبل أي تعديل.",
        "review_debts": "راجع الديون الباقية وتواريخ استحقاقها.",
        "no_action_needed": "ماكو تنبيه يحتاج مراجعة بهالسجلات.",
        "margin_insufficient_priced_sales": (
            "المبيعات اللي إلها كلفة مسجلة ما تكفي لعرض الهامش التقديري."
        ),
        "forecast_lowest": "أقل نقد متوقع",
        "thousand": "ألف",
        "iqd": "دينار",
        "busy": "الخدمة مشغولة هسه، جرّب بعد شوية.",
        "needs_internet": "المحادثة تحتاج اتصال. تكدر ترجع للتقارير المحفوظة.",
        "provider_unconfigured": (
            "المحادثة بعد ما جاهزة. تكدر تستخدم السجلات والتقارير."
        ),
        "template_fallback": (
            "هذا جواب من قالب السجلات الموثقة لأن صياغة النموذج ما توفرت."
        ),
        "clarify_period": "تقصد هاليوم لو يوم ثاني؟ وضّح الفترة بسؤالك.",
        "clarify_customer": "أي حساب تقصد؟ اختار الاسم واذكره بسؤالك.",
        "clarify_request": "شنو تريد تعرف من السجلات؟ وضّح سؤالك والفترة.",
        "clarify_opening_balance": "ما عندي رصيد افتتاحي أو عدّ نقد موثق. تكدر تسجله؟",
        "clarify_costs": "أسعار الشراء المسجلة ما تكفي للهامش التقديري. تكدر تكملها؟",
        "clarify_history": "ما عندي سجلات كافية لهاي الفترة. أي فترة من الدفتر تقصد؟",
        "clarify_due_date": "أكو استحقاق بدون تاريخ موثق. تكدر تكمل تاريخ الاستحقاق؟",
        "clarify_counts": "عدّ النقد اللازم للمقارنة مو مسجل. تكدر تكمل العدّ؟",
        "unsupported_write": (
            "أگدر أقرأ السجلات وأوضحها. تسجيل أو دفع أو إلغاء قيد يحتاج إجراء منك."
        ),
        "unsafe_instruction": (
            "أعتمد على السجلات الموثقة، وما أغيّر القواعد أو أخمّن الرصيد."
        ),
        "help": (
            "اسألني عن المبيعات والديون والاستحقاقات أو الهامش الإجمالي التقديري، "
            "واذكر الفترة."
        ),
        "chat_error": "ما گدرت أتحقق من الجواب. جرّب توضح سؤالك.",
    }.items()
}


# D61 user-approved5Nov2026; exact per-key hashes are in arabic_review.py.
COLLECTION_COPY = {
    "collection_greeting": "هلا {name}،",
    "collection_signoff": "ممنونين لتعاونك.",
    "collection_zaincash": "إذا يناسبك، تكدر تسدد بتحويل زين كاش.",
    "reminder_gentle": (
        "كيلع يقابلاب كركّذأ تيبح {{fig:overdue_amount}}، "
        "هدعوم ناج يللا {{date:oldest_due}}. ؟هددست كبساني تكوش"
    ),
    "reminder_normal": (
        "رخأتملا غلبملاب كركّذن {{fig:overdue_amount}}، "
        "هدعوم ناج يللا {{date:oldest_due}}. هددست كبساني تكوش انلّك."
    ),
    "reminder_firm": (
        "غلبملا {{fig:overdue_amount}} نم رخأتم هدعب {{date:oldest_due}}. "
        "ردكت تكوش يلّك ،ديدستلل دعوم ىلع قفتن مزال."
    ),
    "collection_nothing_owed": "هالحساب ما عليه دين باقي بالسجلات.",
    "collection_not_due": (
        "دين هالحساب بعده مو متأخر؛ أقرب استحقاق بتاريخ {{date:next_due}}."
    ),
    "collection_priorities": "الديون المتأخرة، مرتبة حسب المبلغ وبعدين مدة التأخير.",
    "collection_empty": "ماكو ديون زبائن متأخرة بالسجلات.",
    "collection_overdue_amount": "المبلغ المتأخر",
    "collection_days_overdue": "أيام التأخير",
    "collection_reminded": "خيراتب ناج ريكذت رخآ {{date:last_reminded}}.",
    "brief_title": "ملخص الصبح",
    "brief_dues_today": "مستحقات اليوم ويا المتأخر",
    "brief_dues_week": "المستحقات من اليوم لنهاية أسبوع الشغل",
    "brief_overdue_count": "عدد الزبائن المتأخرين",
    "brief_flags_count": "عدد القيود اللي تحتاج مراجعة هالأسبوع",
}
MESSAGES.update(
    {
        key: DraftMessage(value, status=review_status(key, value))
        for key, value in COLLECTION_COPY.items()
    }
)


# Verbatim D45 frontend keys reused by D54, not a new approval or an extension
# of D38/D44. Hashes are from FRONTEND_ARABIC_APPROVAL_2026-10-20.json.
REUSED_FRONTEND_LABELS = {
    "collection": (
        "تحصيل دين",
        "930c1a0ea40f2325b69c4eff7ae16f0dabbf8a5f494494dc21fda8f29102ade7",
    ),
    "operatingExpense": (
        "مصروف المحل",
        "acfbd0a4f9f317acf7b931885b07ec5792ae18d53c98a038b857642f05cb89ea",
    ),
    "ownerDrawing": (
        "سحب صاحب المحل",
        "c9f4022caaeee6e430ce3976bb2ae5e754cdac3995abd54b311541be272b6de3",
    ),
    "supplierPayment": (
        "دفعة للمجهز",
        "cadff17cd37c02b1aaff357aa6df157f218ccf179251dee60faef601f54fd80c",
    ),
    "capitalInjection": (
        "إضافة رأس مال",
        "fd4136b7751bcc9af05c3207681d113c721c6cbb63aee7d031b38cfd8b57ce4d",
    ),
}


def text(key):
    if key in MESSAGES:
        return MESSAGES[key].text
    value, approved = REUSED_FRONTEND_LABELS[key]
    if hashlib.sha256(value.encode("utf-8")).hexdigest() != approved:
        raise ValueError("Reused copy differs from its reviewed text")
    return value
