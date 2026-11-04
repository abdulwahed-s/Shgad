"""D61 user approval5Nov2026 binds exact supplied text, including character order."""

import hashlib
import json
from pathlib import Path

from app.agents.arabic_review import review_status
from app.agents.messages_ar import COLLECTION_COPY, MESSAGES

ROOT = Path(__file__).resolve().parents[3]
EXACT_BACKEND = {
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
    "collection_reminded": "خيراتب ناج ريكذت رخآ {{date:last_reminded}}.",
}
EXACT_FRONTEND = {
    "collectionLastReminded": "خيراتب ناج ريكذت رخآ {date}",
    "collectionNeverReminded": "هتركّذ ام دعب",
    "collectionHandoffLogged": "تلصو ةلاسرلا نإ ينعي ام باستاو حتف .ريكذتلا ظفحنا.",
    "collectionCopiedLogged": "ريكذتلا ظفحناو ةلاسرلا تخسننا.",
    "collectionShareNotice": "اهزدت اذإ ررقت تنإ ؛لاصتالا ةهج راتخت ىتح حتفي باستاو.",
}


def test_d61_exact_backend_texts_are_user_approved_and_edits_lose_approval():
    from app.agents.arabic_review import (
        D61_APPROVED_MESSAGES,
        D61_APPROVED_TEXT_SHA256,
        D61_REVIEWED_BY,
        D61_REVIEWED_ON,
    )

    assert D61_REVIEWED_ON == "2026-11-05" and D61_REVIEWED_BY == "user"
    assert {key: COLLECTION_COPY[key] for key in EXACT_BACKEND} == EXACT_BACKEND
    assert set(D61_APPROVED_MESSAGES) == set(COLLECTION_COPY)
    assert len(D61_APPROVED_MESSAGES) == 18
    for key, value in COLLECTION_COPY.items():
        assert MESSAGES[key].status == review_status(key, value) == "APPROVED"
        assert review_status(key, value + " changed") == "PENDING_REVIEW"
        assert review_status("unreviewed_" + key, value) == "PENDING_REVIEW"
    canonical = json.dumps(
        COLLECTION_COPY, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert hashlib.sha256(canonical.encode()).hexdigest() == D61_APPROVED_TEXT_SHA256
    assert "{{date:last_reminded}}" in COLLECTION_COPY["collection_reminded"]
    assert "reminder_age" not in COLLECTION_COPY["collection_reminded"]


def test_d61_frontend_exact_text_and_all_32_approval_hashes():
    source = json.loads((ROOT / "frontend/lib/l10n/app_ar.arb").read_text("utf-8"))
    assert {key: source[key] for key in EXACT_FRONTEND} == EXACT_FRONTEND
    keys = [
        key
        for key in source
        if not key.startswith("@")
        and source.get("@" + key, {}).get("x-review-decision") == "D61"
    ]
    assert len(keys) == 32
    for key in keys:
        meta = source["@" + key]
        assert meta["x-review"] == "approved Iraqi Arabic review"
        assert meta["x-review-date"] == "2026-11-05"
        assert meta["x-review-by"] == "user"
        assert (
            meta["x-review-sha256"] == hashlib.sha256(source[key].encode()).hexdigest()
        )
    assert source["@collectionLastReminded"]["placeholders"] == {
        "date": {"type": "String"}
    }
