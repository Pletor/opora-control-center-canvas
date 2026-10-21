"""Bounded raw snapshot and semantic replay tests using the real SQLite schema."""
import copy
import json
import sqlite3

import pytest

from database.repositories import opora_context_snapshot
from database.repositories.opora_context_events import enroll, install
from database.repositories.opora_context_events_sources import SOURCES
from database.repositories.opora_context_replay import replay
from database.repositories.opora_context_snapshot import MAX_ROWS, capture
from database.schema.project_initialization import initialize_project_schema


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    connection.commit()
    yield connection
    connection.close()


def begin(db, *projects):
    db.execute("BEGIN IMMEDIATE")
    install(db)
    return {project: enroll(db, project) for project in projects}


def insert(db, table, project="p", suffix="x", revision=1):
    values = [revision if key == "revision" else project if key == "project_id"
              else f"{key}-{suffix}" for key in SOURCES[table]]
    db.execute(f'INSERT INTO "{table}" VALUES({",".join("?" for _ in values)})', values)


def profile_projection(rows):
    values = rows["project_profile"]
    return sorted(row["architecture"] for row in values)


def test_capture_requires_transaction_and_includes_all_revisions(db):
    with pytest.raises(RuntimeError):
        capture(db, "p")
    begin(db, "p")
    insert(db, "node_text_revisions", suffix="old", revision=1)
    insert(db, "node_text_revisions", suffix="new", revision=2)
    snapshot = capture(db, "p")
    assert {row["revision"] for row in snapshot["rows"]["node_text_revisions"]} == {1, 2}
    assert snapshot["checkpoint"]["sequence"] == 2


def test_journal_replay_insert_update_delete_and_noop(db):
    begin(db, "p")
    origin = capture(db, "p")
    insert(db, "project_profile")
    db.execute("UPDATE project_profile SET architecture='changed'")
    db.execute("DELETE FROM project_profile")
    with pytest.raises(ValueError, match="scope changed"):
        replay(db, origin, profile_projection)
    baseline = capture(db, "p")
    assert replay(db, baseline, profile_projection)["liveScopeUnchanged"] is True


def test_unrelated_raw_transition_passes_and_input_is_unchanged(db):
    begin(db, "p")
    insert(db, "project_profile")
    origin = capture(db, "p")
    before = copy.deepcopy(origin)
    db.execute("UPDATE project_profile SET tenancy='another raw value'")
    evidence = replay(db, origin, profile_projection)
    assert evidence["liveScopeUnchanged"] is True
    assert origin == before
    assert set(evidence) == {"liveScopeUnchanged", "transitionCount", "sourceRowCount", "checkpoint"}


def test_relevant_aba_is_denied_at_intermediate_state(db):
    begin(db, "p")
    insert(db, "project_profile")
    origin = capture(db, "p")
    db.execute("UPDATE project_profile SET architecture='B'")
    db.execute("UPDATE project_profile SET architecture='architecture-x'")
    assert profile_projection(capture(db, "p")["rows"]) == profile_projection(origin["rows"])
    with pytest.raises(ValueError, match="scope changed"):
        replay(db, origin, profile_projection)


def test_rollback_has_no_events_and_deleting_latest_revision_reveals_old(db):
    begin(db, "p")
    insert(db, "node_text_revisions", suffix="older", revision=1)
    insert(db, "node_text_revisions", suffix="latest", revision=2)
    origin = capture(db, "p")
    db.execute("DELETE FROM node_text_revisions WHERE revision=2")
    with pytest.raises(ValueError, match="scope changed"):
        replay(db, origin,
               lambda rows: max(r["revision"] for r in rows["node_text_revisions"]))
    db.rollback()
    assert db.execute("SELECT count(*) FROM opora_context_events").fetchone()[0] == 0
    begin(db, "p")
    assert capture(db, "p")["checkpoint"]["sequence"] == 0


def test_project_move_updates_scope_and_rejects_bad_transition(db):
    begin(db, "p", "q")
    insert(db, "project_profile")
    p_origin, q_origin = capture(db, "p"), capture(db, "q")
    db.execute("UPDATE project_profile SET project_id='q'")
    assert replay(db, p_origin, lambda rows: None)["liveScopeUnchanged"]
    assert replay(db, q_origin, lambda rows: None)["liveScopeUnchanged"]
    db.rollback()
    begin(db, "p")
    bad = capture(db, "p")
    with pytest.raises(ValueError, match="bounds"):
        replay(db, bad, lambda rows: None, limit=257)


def test_primary_key_move_and_exact_before_match(db):
    begin(db, "p")
    insert(db, "workspace_graph_authority")
    origin = capture(db, "p")
    db.execute("UPDATE workspace_graph_authority SET workspace_id='moved'")
    assert replay(db, origin, lambda rows: None)["transitionCount"] == 1

    before = capture(db, "p")
    db.execute("UPDATE workspace_graph_authority SET digest='new-digest'")
    forged = copy.deepcopy(before)
    forged["rows"]["workspace_graph_authority"][0]["digest"] = "forged"
    with pytest.raises(ValueError, match="before-row"):
        replay(db, forged, lambda rows: None)


def test_missing_bad_baseline_and_current_state_mismatch_fail(db):
    begin(db, "p")
    baseline = capture(db, "p")
    with pytest.raises(ValueError):
        capture(db, "missing")
    malformed = copy.deepcopy(baseline)
    malformed["checkpoint"]["coverageId"] = "bad"
    with pytest.raises(ValueError):
        replay(db, malformed, profile_projection)
    stale_raw = copy.deepcopy(baseline)
    stale_raw["rows"]["project_profile"].append({
        "project_id": "p", "architecture": "architecture-x", "tenancy": "forged",
    })
    stale_raw["rows"]["project_profile"].append({
        "project_id": "p", "architecture": "architecture-x", "tenancy": "forged",
    })
    with pytest.raises(ValueError, match="duplicate"):
        replay(db, stale_raw, profile_projection)
    stale_raw["rows"]["project_profile"].pop()
    with pytest.raises(ValueError, match="raw state"):
        replay(db, stale_raw, profile_projection)


def test_non_ascii_raw_event_replays_without_reconstructing_payload_bytes(db):
    begin(db, "p")
    insert(db, "project_profile")
    origin = capture(db, "p")
    value = chr(382) + "lu" + chr(357) + "ou" + chr(269) + "k" + chr(253) + " k" + chr(367) + chr(328)
    db.execute("UPDATE project_profile SET tenancy=?", (value,))
    assert replay(db, origin, profile_projection)["transitionCount"] == 1


def test_snapshot_bounds_are_checked_before_fetch(db):
    for index in range(MAX_ROWS + 1):
        insert(db, "node_text_revisions", suffix=str(index))
    db.commit()
    begin(db, "p")
    with pytest.raises(ValueError, match="bounds"):
        capture(db, "p")


def test_replay_enforces_snapshot_byte_bound_after_each_transition(db, monkeypatch):
    begin(db, "p")
    insert(db, "project_profile")
    origin = capture(db, "p")
    original_size = len(json.dumps(origin, ensure_ascii=True, separators=(",", ":")).encode())
    db.execute("UPDATE project_profile SET tenancy=?", ("x" * 1000,))
    monkeypatch.setattr(opora_context_snapshot, "MAX_BYTES", original_size)
    with pytest.raises(ValueError, match="byte bound"):
        replay(db, origin, profile_projection)


def test_null_primary_key_and_duplicate_snapshot_rows_rejected(db):
    begin(db, "p")
    insert(db, "node_text_revisions")
    db.execute("UPDATE node_text_revisions SET node_id=NULL")
    with pytest.raises(ValueError, match="primary key"):
        capture(db, "p")
