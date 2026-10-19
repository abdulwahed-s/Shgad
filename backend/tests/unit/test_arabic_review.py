"""Human approval binds exact text; edits and new keys remain unreviewed."""

from app.agents.messages_ar import MESSAGES, DraftMessage


def test_confirmed_backend_copy_has_recorded_approval():
    assert len(MESSAGES) == 50
    assert {item.status for item in MESSAGES.values()} == {"APPROVED"}


def test_changed_text_loses_approval():
    from app.agents.arabic_review import review_status

    assert review_status("busy", MESSAGES["busy"].text + " changed") == "PENDING_REVIEW"


def test_new_key_cannot_inherit_another_messages_approval():
    from app.agents.arabic_review import review_status

    assert review_status("new_message", MESSAGES["busy"].text) == "PENDING_REVIEW"


def test_new_message_objects_default_to_pending():
    assert DraftMessage("fictional unreviewed text").status == "PENDING_REVIEW"
