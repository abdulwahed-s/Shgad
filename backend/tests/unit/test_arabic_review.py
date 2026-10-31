"""Human approval binds exact text; edits and new keys remain unreviewed."""

from app.agents.messages_ar import MESSAGES, DraftMessage


def test_confirmed_backend_copy_has_recorded_approval():
    from app.agents.arabic_review import (
        APPROVED_MESSAGES,
        D59_APPROVED_MESSAGES,
        WEEKLY_APPROVED_MESSAGES,
    )

    assert len(APPROVED_MESSAGES) == 50
    assert {key for key, item in MESSAGES.items() if item.status == "APPROVED"} == set(
        APPROVED_MESSAGES
    ) | set(WEEKLY_APPROVED_MESSAGES) | set(D59_APPROVED_MESSAGES)


def test_weekly_copy_approval_binds_the_five_exact_reviewed_texts():
    from app.agents.arabic_review import review_status

    for key in (
        "review_unmatched_payment",
        "review_duplicate_payment",
        "review_debts",
        "no_action_needed",
        "margin_insufficient_priced_sales",
    ):
        assert MESSAGES[key].status == "APPROVED"
        assert review_status(key, MESSAGES[key].text + " changed") == "PENDING_REVIEW"


def test_weekly_copy_has_a_separate_canonical_approval_snapshot():
    import hashlib
    import json

    from app.agents.arabic_review import (
        APPROVED_TEXT_SHA256,
        REVIEWED_ON,
        WEEKLY_APPROVED_MESSAGES,
        WEEKLY_APPROVED_TEXT_SHA256,
        WEEKLY_REVIEWED_ON,
    )

    assert REVIEWED_ON == "2026-10-19" and WEEKLY_REVIEWED_ON == "2026-10-20"
    assert APPROVED_TEXT_SHA256 == (
        "98e65cbc75df68410294ca4527e193706508fedef2e66555bded88f2806bb28a"
    )
    canonical = json.dumps(
        {key: MESSAGES[key].text for key in WEEKLY_APPROVED_MESSAGES},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == WEEKLY_APPROVED_TEXT_SHA256


def test_changed_text_loses_approval():
    from app.agents.arabic_review import review_status

    assert review_status("busy", MESSAGES["busy"].text + " changed") == "PENDING_REVIEW"


def test_new_key_cannot_inherit_another_messages_approval():
    from app.agents.arabic_review import review_status

    assert review_status("new_message", MESSAGES["busy"].text) == "PENDING_REVIEW"


def test_new_message_objects_default_to_pending():
    assert DraftMessage("fictional unreviewed text").status == "PENDING_REVIEW"


def test_d59_approval_binds_the_two_exact_backend_texts():
    import hashlib
    import json

    from app.agents.arabic_review import (
        D59_APPROVED_MESSAGES,
        D59_APPROVED_TEXT_SHA256,
        D59_REVIEWED_ON,
        review_status,
    )

    assert D59_REVIEWED_ON == "2026-10-31"
    assert set(D59_APPROVED_MESSAGES) == {"flag_sources", "expense_kind_unrecorded"}
    values = {key: MESSAGES[key].text for key in D59_APPROVED_MESSAGES}
    canonical = json.dumps(
        values, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert hashlib.sha256(canonical.encode()).hexdigest() == D59_APPROVED_TEXT_SHA256
    for key, value in values.items():
        assert MESSAGES[key].status == review_status(key, value) == "APPROVED"
        assert review_status(key, value + " changed") == "PENDING_REVIEW"
