"""Human approval binds exact text; edits and new keys remain unreviewed."""

from app.agents.messages_ar import MESSAGES, DraftMessage


def test_confirmed_backend_copy_has_recorded_approval():
    from app.agents.arabic_review import APPROVED_MESSAGES

    assert len(APPROVED_MESSAGES) == 50
    assert {key for key, item in MESSAGES.items() if item.status == "APPROVED"} == set(
        APPROVED_MESSAGES
    )


def test_weekly_suggestion_and_insufficient_margin_copy_needs_human_review():
    for key in (
        "review_unmatched_payment",
        "review_duplicate_payment",
        "review_debts",
        "no_action_needed",
        "margin_insufficient_priced_sales",
    ):
        assert MESSAGES[key].status == "PENDING_REVIEW"


def test_changed_text_loses_approval():
    from app.agents.arabic_review import review_status

    assert review_status("busy", MESSAGES["busy"].text + " changed") == "PENDING_REVIEW"


def test_new_key_cannot_inherit_another_messages_approval():
    from app.agents.arabic_review import review_status

    assert review_status("new_message", MESSAGES["busy"].text) == "PENDING_REVIEW"


def test_new_message_objects_default_to_pending():
    assert DraftMessage("fictional unreviewed text").status == "PENDING_REVIEW"
