"""Immutable storage validates IDs, contents and ownership instead of trusting its index."""
import json

import pytest

from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.test_opora_changesets import baseline, service  # noqa: F401
from backend.canvas.canvas_service import CanvasService
from backend.canvas.test_opora_changesets import legacy_save


@pytest.mark.parametrize("mutation", ["id", "scope", "content", "type"])
def test_read_rejects_corrupt_record(service, mutation):
    initial = baseline(service)
    value = dict(initial)
    if mutation == "id":
        value["id"] = "0" * 40
    elif mutation == "scope":
        value["workspace"] = "other"
    elif mutation == "content":
        value["subject"] = "Tampered"
    else:
        value = []
    db = service.db_for("draft")
    with service.lock_for("draft"), db:
        db.execute("UPDATE opora_spec_revisions SET content=? WHERE id=?", (json.dumps(value), initial["id"]))
    with pytest.raises(ValueError, match="Otisk"):
        OporaChangesets(service).revision("draft", "draft", initial["id"])


def test_foreign_revision_and_missing_revision_are_not_readable(service):
    initial = baseline(service)
    changesets = OporaChangesets(service)
    with pytest.raises(ValueError, match="neexistuje"):
        changesets.revision("draft", "other", initial["id"])
    with pytest.raises(ValueError, match="neexistuje"):
        changesets.revision("draft", "draft", "0" * 40)


def test_opening_pre_changeset_database_adds_empty_schema_without_rewriting_working_specs(service, tmp_path):
    previous = legacy_save(service)
    db = service.db_for("draft")
    with service.lock_for("draft"), db:
        for table in ("opora_spec_refs", "opora_spec_revisions", "opora_spec_proposals"):
            db.execute(f"DROP TABLE {table}")
    service.close()
    reopened = CanvasService(tmp_path / "data")
    try:
        changesets = OporaChangesets(reopened)
        assert changesets.context("draft", "draft")["acceptedHead"] is None
        assert changesets.list("draft", "draft")["items"] == []
        assert reopened.node_spec("draft", "draft", "a") == previous
    finally:
        reopened.close()
