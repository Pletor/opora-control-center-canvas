"""A plan acceptance owns the transaction across multiple specification writes."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.editor.node.node_specs import EMPTY_FIELDS

FIRST = ("draft", "draft", "first")
SECOND = ("draft", "architecture", "second")
FIELDS = {**EMPTY_FIELDS, "goal": "Accepted assignment"}


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def test_transactional_write_requires_both_lock_and_open_transaction(service):
    db = service.db_for("draft")
    with service.lock_for("draft"):
        with pytest.raises(RuntimeError, match="caller transaction"):
            service.specs.save_in_transaction(FIRST, 0, FIELDS)
    with db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(RuntimeError, match="caller transaction"):
            service.specs.save_in_transaction(FIRST, 0, FIELDS)
    assert service.specs.read(FIRST)["revision"] == 0


def test_two_document_owners_commit_only_when_caller_commits(service):
    db = service.db_for("draft")
    with service.lock_for("draft"), db:
        db.execute("BEGIN IMMEDIATE")
        first = service.specs.save_in_transaction(FIRST, 0, FIELDS)
        second = service.specs.save_in_transaction(SECOND, 0, FIELDS)
        assert db.in_transaction
        assert service.specs.read(FIRST) == first
        assert service.specs.read(SECOND) == second
    assert not db.in_transaction
    assert service.specs.read(FIRST)["revision"] == 1
    assert service.specs.read(SECOND)["revision"] == 1
    assert service.specs.read(("draft", "draft", "second"))["revision"] == 0


def test_failure_after_two_writes_rolls_back_both_histories(service):
    db = service.db_for("draft")
    with pytest.raises(RuntimeError, match="accepted reference"):
        with service.lock_for("draft"), db:
            db.execute("BEGIN IMMEDIATE")
            service.specs.save_in_transaction(FIRST, 0, FIELDS)
            service.specs.save_in_transaction(SECOND, 0, FIELDS)
            raise RuntimeError("Failed accepted reference update")
    assert service.specs.history(FIRST)["items"] == []
    assert service.specs.history(SECOND)["items"] == []


@pytest.mark.parametrize("revision,fields", [(1, FIELDS), (0, {"goal": "Incomplete"}),
                                            (False, FIELDS)])
def test_second_write_conflict_or_invalid_content_rolls_back_first(service, revision, fields):
    db = service.db_for("draft")
    with pytest.raises(ValueError):
        with service.lock_for("draft"), db:
            db.execute("BEGIN IMMEDIATE")
            service.specs.save_in_transaction(FIRST, 0, FIELDS)
            service.specs.save_in_transaction(SECOND, revision, fields)
    assert service.specs.read(FIRST)["revision"] == 0
    assert service.specs.read(SECOND)["revision"] == 0


def test_public_save_still_commits_and_preserves_prior_revision_on_conflict(service):
    saved = service.specs.save(FIRST, 0, FIELDS)
    assert saved["revision"] == 1 and saved["saved_at"]
    assert not service.db_for("draft").in_transaction
    with pytest.raises(ValueError, match="Konflikt"):
        service.specs.save(FIRST, 0, {**FIELDS, "goal": "Stale"})
    assert service.specs.read(FIRST) == saved
    assert service.specs.history(FIRST)["items"] == [saved]
