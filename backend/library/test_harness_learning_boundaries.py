"""Config version isolation, ambiguous attribution, immutable scope and additive storage."""
import copy
import sqlite3
import pytest

from backend.canvas.test_opora_changesets import accept
from backend.canvas.test_opora_execution_context import claimed
from backend.library.harness_learning_rates import rate, read
from backend.library.test_harness_kit import kit, propose_kit
from backend.library.test_harness_learning import cohorts, confirm, merged_link
from database.schema.harness_learning_schema import SCHEMA


def test_same_content_in_a_different_capability_config_is_another_cohort(learning_run, learning_plan):
    graphs, _, _ = learning_plan
    _, authority, _, record = learning_run
    authority.release(record["executionId"], {"project": "draft", "workspace": "draft", "token": record["token"], "epoch": record["epoch"]})
    updated = kit()
    updated["resources"][0]["requires"] = ["mcp:context7"]
    proposal, head = propose_kit(learning_plan, updated, {"steps": record["assignment"]["steps"]})
    accept(graphs.service, proposal, head)
    claimed(learning_plan, request="new-config")
    rows = cohorts(learning_run)
    assert len(rows) == 2 and len({row["digest"] for row in rows}) == 1
    assert len({row["versionDigest"] for row in rows}) == 2
    assert all(row["rate"]["unknown"] == 1 and row["tasks"] == 1 for row in rows)


def test_changed_accepted_target_does_not_attribute_old_merge_to_new_requirements(learning_run, learning_plan):
    graphs, _, _ = learning_plan
    merged_link(learning_run)
    proposal, head = propose_kit(learning_plan, kit("Different requirements"))
    accept(graphs.service, proposal, head)
    confirm(learning_run)
    assert cohorts(learning_run)[0]["rate"]["unknown"] == 1


def test_more_than_one_merged_execution_cannot_gain_an_arbitrary_verified_vote(learning_run):
    merged_link(learning_run)
    service, _, _, _ = learning_run
    db = service.db_for("draft")
    with db:
        columns = [row[1] for row in db.execute("PRAGMA table_info(opora_execution_pull_requests)")]
        values = list(db.execute("SELECT * FROM opora_execution_pull_requests").fetchone())
        values[columns.index("execution_id")] = "other-execution"
        db.execute("INSERT INTO opora_execution_pull_requests VALUES(" + ",".join("?" for _ in values) + ")", values)
    confirm(learning_run)
    assert cohorts(learning_run)[0]["rate"]["unknown"] == 1


def test_scope_lineage_catches_accepted_change_and_restore_before_human_closure(learning_run, learning_plan):
    graphs, _, _ = learning_plan
    _, _, _, record = learning_run
    merged_link(learning_run)
    proposal, head = propose_kit(learning_plan, kit("Temporary accepted change"))
    accept(graphs.service, proposal, head)
    restored, head = propose_kit(learning_plan, kit(), {"steps": record["assignment"]["steps"]})
    accept(graphs.service, restored, head)
    confirm(learning_run)
    assert cohorts(learning_run)[0]["rate"]["unknown"] == 1


def test_old_event_cannot_restore_success_after_a_newer_withdrawal(learning_run):
    from backend.library.harness_learning import project_event
    from database.repositories import opora_events

    merged_link(learning_run)
    confirm(learning_run)
    service, _, _, _ = learning_run
    db = service.db_for("draft")
    old = next(row for row in opora_events.page(db, "draft", None, 0, 500)[0] if row["kind"] == "decision.resolved")
    confirm(learning_run, now=False)
    with db:
        db.execute("DELETE FROM harness_learning_sources WHERE event_id=?", (old["id"],))
        project_event(db, old["id"], copy.deepcopy(old))
    assert cohorts(learning_run)[0]["rate"]["unknown"] == 1


def test_projection_schema_expands_idempotently_and_rolls_back_without_erasing_old_data():
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE original(value TEXT)")
        db.execute("INSERT INTO original VALUES('preserved')")
        db.executescript(SCHEMA)
        db.execute("INSERT INTO harness_learning_runs VALUES('p','w','e','n','a','r','k','now')")
        db.executescript(SCHEMA)
        assert db.execute("SELECT value FROM original").fetchone()[0] == "preserved"
        assert db.execute("SELECT COUNT(*) FROM harness_learning_runs").fetchone()[0] == 1
        # An old reader can keep using its table while additive projection data stays in place.
        db.execute("INSERT INTO original VALUES('old-reader')")
        assert db.execute("SELECT COUNT(*) FROM original").fetchone()[0] == 2
    finally:
        db.close()


def test_unknowns_and_small_samples_expose_uncertainty_and_never_become_zero_percent():
    assert rate(0, 0, 3)["percent"] is None
    assert rate(0, 0, 0)["coverage"] is None
    measured = rate(1, 1, 2)
    assert measured["percent"] == 50 and measured["coverage"] == 0.5
    assert measured["interval95"][0] < 10 and measured["interval95"][1] > 90


def test_bounded_read_exposes_truncation_and_no_fabricated_cost_or_runner(learning_run):
    service, _, _, _ = learning_run
    result = read(service.db_for("draft"), "draft", "draft", limit=1)
    assert result["limited"] is True and len(result["cohorts"]) == 1
    assert result["promotionAllowed"] is False
    row = result["cohorts"][0]
    assert all(row[key] is None for key in ("runner", "tokens", "cost", "meanDurationMs"))
    for limit in (0, 101, True):
        with pytest.raises(ValueError):
            read(service.db_for("draft"), "draft", "draft", limit=limit)
