import pytest

from backend.claude_code.assistant.approval_book import ApprovalBook, ApprovalNotFound, Pending
from backend.claude_code.assistant.errors import AssistantError


def entry(aid, sid="s1", created=0.0):
    return Pending(aid, sid, f"req-{aid}", {"command": "x"}, created)


def test_take_once_then_conflict():
    book = ApprovalBook()
    book.add(entry("a"))
    assert book.session_of("a") == "s1" and book.has_pending("s1")
    assert book.take("a", "s1").request_id == "req-a"
    assert not book.has_pending("s1") and book.session_of("a") == "s1"
    with pytest.raises(AssistantError) as twice:
        book.take("a", "s1")
    assert twice.value.status == 409 and not isinstance(twice.value, ApprovalNotFound)
    with pytest.raises(ApprovalNotFound):
        book.take("a", "s2")
    with pytest.raises(ApprovalNotFound):
        book.session_of("zzz")


def test_expired_and_drop_session():
    book = ApprovalBook()
    book.add(entry("old", created=0.0))
    book.add(entry("new", created=500.0))
    book.add(entry("other", sid="s2", created=0.0))
    assert [e.approval_id for e in book.expired(601.0, 600.0)] == ["old", "other"]
    assert [e.approval_id for e in book.drop_session("s1")] == ["new"]
    assert not book.has_pending("s1") and not book.has_pending("s2")
