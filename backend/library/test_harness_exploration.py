"""Allocation gate against native-shaped SQLite fixtures, not production evidence."""
import json

import pytest

from backend.library import harness_exploration as gate
from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import payload
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414

ADMIT, CURRENT = gate.admit, gate.current


def projection(db):
    # Independent PR: learning tables are optional in production and absent on main.
    db.executescript("""
      CREATE TABLE IF NOT EXISTS harness_learning_runs(project_id,workspace_id,execution_id,node_id,
        assignment_digest,accepted_revision,kit_digest,enrolled_at);
      CREATE TABLE IF NOT EXISTS harness_learning_outcomes(project_id,workspace_id,execution_id,tier,
        outcome,source_event,reason,at);
      CREATE TABLE IF NOT EXISTS harness_learning_sources(project_id,workspace_id,event_id,kind);
    """)


def baseline(db, index, *, node=None, workspace="draft", tier="verified", outcome="pass"):
    execution, card = "baseline-" + str(index), node or "baseline-card-" + str(index)
    event = db.execute("INSERT INTO opora_events(at,project_id,workspace_id,kind,node_id,execution_id,actor_kind,data)"
                       " VALUES(?,?,?,?,?,?,?,?)", ("now", "draft", workspace, "decision.resolved", card, execution,
                       "human", '{"decision":"close_card"}')).lastrowid
    row = db.execute("SELECT state FROM desktop_v3_state WHERE project_id='draft' AND workspace_id=?", (workspace,)).fetchone()
    from backend.editor.agent_memory.desktop_v3_state import default_state
    state = json.loads(row[0]) if row else default_state()
    state.setdefault("nodes", {})[card] = {"done": {"confirmed": True}}
    db.execute("INSERT INTO desktop_v3_state VALUES(?,?,?,?,?) ON CONFLICT(project_id,workspace_id) DO UPDATE SET state=excluded.state",
               ("draft", workspace, 1, json.dumps(state), "now"))
    db.execute("INSERT INTO harness_learning_runs VALUES(?,?,?,?,?,?,?,?)",
               ("draft", workspace, execution, card, "digest", "revision", "kit", "now"))
    db.execute("INSERT INTO harness_learning_outcomes VALUES(?,?,?,?,?,?,?,?)",
               ("draft", workspace, execution, tier, outcome, event, "human-closed-merged-run", "now"))
    db.execute("INSERT INTO harness_learning_sources VALUES(?,?,?,?)",
               ("draft", workspace, event, "decision.resolved"))
    db.execute("INSERT INTO opora_execution_pull_requests(project_id,workspace_id,execution_id,node_id,"
               "accepted_revision,repository,number,head_ref,head_sha,state,enrollment,merge_sha,"
               "awaiting_human_close,source,linked_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("draft", workspace, execution, card, "revision", "owner/repo", index, "feature", "a" * 40,
                "merged", "enrolled", "b" * 40, 0, "test-fixture", "human", "now", "now"))


@pytest.fixture
def allocation(setup, monkeypatch):
    monkeypatch.setattr(gate, "admit", ADMIT)
    monkeypatch.setattr(gate, "current", CURRENT)
    monkeypatch.setenv("OPORA_HARNESS_EXPLORATION", json.dumps({"project": "draft", "workspace": "draft", "environment": "nonproduction"}))
    projection(setup[1].db_for("draft"))
    return setup


def seed(canvas, count):
    with canvas.db_for("draft") as db:
        for i in range(1, count + 1):
            baseline(db, i)


def test_atomic_boundary_replay_and_restart_cannot_refund(allocation):
    verifier, canvas, authority, record, calls, _ = allocation
    seed(canvas, 18)
    with pytest.raises(ValueError, match="share exhausted"):
        verifier.verify(payload(record))
    assert not calls
    with canvas.db_for("draft") as db:
        baseline(db, 19)
    admitted = verifier.verify(payload(record))
    assert admitted["exploration"]["baselineCards"] == 19 and len(calls) == 1
    assert gate.snapshot(canvas.db_for("draft"), "draft", "draft")["remaining"] == 0
    assert verifier.verify(payload(record)) == admitted and len(calls) == 1
    from backend.canvas.test_opora_executions import claim
    from backend.library.harness_verifier import HarnessVerifier
    other = claim(authority, request="other", node="b")
    with pytest.raises(ValueError, match="share exhausted"):
        HarnessVerifier(canvas).verify(payload(other))
    assert len(calls) == 1


@pytest.mark.parametrize("config", [None, "{}", "[]", "{", '{"project":"draft","workspace":"draft","environment":"production"}',
    '{"project":"other","workspace":"draft","environment":"nonproduction"}'])
def test_unknown_production_or_foreign_policy_never_launches(allocation, monkeypatch, config):
    verifier, canvas, _, record, calls, _ = allocation
    seed(canvas, 19)
    if config is None:
        monkeypatch.delenv("OPORA_HARNESS_EXPLORATION")
    else:
        monkeypatch.setenv("OPORA_HARNESS_EXPLORATION", config)
    with pytest.raises(ValueError, match="eligibility unavailable"):
        verifier.verify(payload(record))
    assert not calls


def test_self_reports_unknown_foreign_and_duplicate_cards_do_not_inflate_denominator(allocation):
    _, canvas, _, _, _, _ = allocation
    with canvas.db_for("draft") as db:
        baseline(db, 1)
        baseline(db, 2, node="baseline-card-1")
        baseline(db, 3, tier="reported")
        baseline(db, 4, outcome="unknown")
        baseline(db, 5, workspace="other")
        baseline(db, 6)
        db.execute("UPDATE opora_execution_pull_requests SET accepted_revision='different' WHERE number=6")
    result = gate.snapshot(canvas.db_for("draft"), "draft", "draft")
    assert result["baselineCards"] == 1 and result["remaining"] == 0


def test_current_experiment_card_cannot_also_supply_baseline_credit(allocation):
    _, canvas, _, record, calls, _ = allocation
    seed(canvas, 18)
    with canvas.db_for("draft") as db:
        baseline(db, 19, node=record["nodeId"])
    assert gate.snapshot(canvas.db_for("draft"), "draft", "draft")["eligible"]
    with canvas.db_for("draft") as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="share exhausted"):
            ADMIT(db, "draft", "draft", record["nodeId"])
    assert not calls


def test_reopen_withdraws_credit_and_policy_revocation_stops_current_authority(allocation, monkeypatch):
    verifier, canvas, _, record, calls, _ = allocation
    seed(canvas, 38)
    admitted = verifier.verify(payload(record))
    assert verifier._current(payload(record), admitted)
    with canvas.db_for("draft") as db:
        db.execute("UPDATE harness_learning_outcomes SET outcome='unknown' WHERE execution_id='baseline-1'")
    assert gate.snapshot(canvas.db_for("draft"), "draft", "draft")["remaining"] == 0
    assert verifier._current(payload(record), admitted)  # one spent still fits 37 baseline cards
    monkeypatch.delenv("OPORA_HARNESS_EXPLORATION")
    assert not verifier._current(payload(record), admitted)
    assert verifier.verify(payload(record)) == admitted and len(calls) == 1


def test_missing_learning_projection_and_missing_transaction_fail_closed(setup, monkeypatch):
    _, canvas, _, _, _, _ = setup
    monkeypatch.setenv("OPORA_HARNESS_EXPLORATION", json.dumps({"project": "draft", "workspace": "draft", "environment": "nonproduction"}))
    db = canvas.db_for("draft")
    # An empty or absent projection supplies no work credit on either standalone or composed builds.
    assert not gate.snapshot(db, "draft", "draft")["eligible"]
    with pytest.raises(RuntimeError, match="transaction"):
        ADMIT(db, "draft", "draft", "a")


@pytest.mark.parametrize("mutation", ["other-card", "other-execution", "agent", "external", "reopened", "pruned"])
def test_native_closure_binding_and_current_state_are_required(allocation, mutation):
    _, canvas, _, _, _, _ = allocation
    seed(canvas, 19)
    db = canvas.db_for("draft")
    assert gate.snapshot(db, "draft", "draft")["eligible"]
    with db:
        if mutation == "reopened":
            db.execute("UPDATE desktop_v3_state SET state=json_set(state, '$.nodes.baseline-card-1.done.confirmed', 0)")
        elif mutation == "pruned":
            db.execute("DELETE FROM opora_events WHERE execution_id='baseline-1'")
        else:
            column, value = {"other-card": ("node_id", "wrong"), "other-execution": ("execution_id", "wrong"),
                             "agent": ("actor_kind", "agent"), "external": ("source", "office")}[mutation]
            db.execute(f"UPDATE opora_events SET {column}=? WHERE execution_id='baseline-1'", (value,))
    assert gate.snapshot(db, "draft", "draft")["baselineCards"] == 18
    assert not gate.snapshot(db, "draft", "draft")["eligible"]


def test_withdrawal_below_spent_ratio_stops_running_authority_and_history_reports_it(allocation):
    verifier, canvas, _, record, _, _ = allocation
    seed(canvas, 19)
    admitted = verifier.verify(payload(record))
    assert verifier._current(payload(record), admitted)
    with canvas.db_for("draft") as db:
        db.execute("UPDATE desktop_v3_state SET state=json_set(state, '$.nodes.baseline-card-1.done.confirmed', 0)")
    assert not verifier._current(payload(record), admitted)
    from backend.library.harness_verifier_budget import read
    view = read(canvas, "draft", "draft")["exploration"]
    assert view["baselineCards"] == 18 and view["admitted"] == 1
    assert view["remaining"] == 0 and not view["eligible"] and not view["reservation"]
