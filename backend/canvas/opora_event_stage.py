"""Per-card stage and gate after a write: emit `stage.changed` / `gate.changed` only on change.

Deterministic: reads the card's facts from the same connection (inside the writer's transaction,
so it sees the change), applies the agent-state card rule (`opora_agent_state_cards.card_stage`)
and compares with the last emitted value in `opora_event_card_state`. Claim readiness is not
recomputed here (it needs the full assignment); a card without execution facts is `plan`.
Contract: docs/oporahub-events.md, "stage.changed".
"""
import time

from backend.canvas import opora_agent_state_cards as card_stages
from backend.canvas import opora_agent_state_reviews as reviews
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests, public
from database.repositories.opora_executions import Executions


def confirmed_nodes(db, project, workspace, nodes):
    """Z karet `nodes` ty, které mají na plátně prostoru potvrzené uzavření (`done.confirmed`); jedno čtení stavu.
    Používá i milník vstupní brány (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5)."""
    wanted = list(dict.fromkeys(nodes))
    if not wanted:
        return set()
    paths = [f'$.nodes."{node}".done.confirmed' for node in wanted]
    row = db.execute(f"SELECT {','.join('json_extract(state, ?)' for _ in paths)} FROM desktop_v3_state"
                     " WHERE project_id=? AND workspace_id=?", (*paths, project, workspace)).fetchone()
    return {node for node, value in zip(wanted, row or ()) if value}


def _done(db, project, workspace, node):
    return node in confirmed_nodes(db, project, workspace, [node])


def _latest(db, project, workspace, node, accepted=None, done=False):
    repo = Executions(db, project, workspace)
    records = repo.history(node)
    if not records:
        return None
    record = records[0]
    deadline = min(record["expiresAt"], record.get("budget", {}).get("runDeadlineAt", record["expiresAt"]))
    count = db.execute("SELECT COUNT(*) FROM opora_execution_results WHERE project_id=? AND workspace_id=?"
                       " AND execution_id=?", (project, workspace, record["executionId"])).fetchone()[0]
    latest = {"id": record["executionId"], "state": record["state"], "acceptedRevision": record["acceptedRevision"],
              "deadline": deadline, "results": count}
    if count and accepted is not None and not done:
        # Stejný výřez karty jako agent-state; běh v1 bez canvasu rozhodne hlava (`slice_changed`).
        from backend.canvas.opora_executions import OporaExecutions
        latest["staleEvidence"] = OporaExecutions(None).slice_changed(repo, record, accepted)
    return latest


def _link(db, project, workspace, node):
    """The card's link chosen exactly as agent-state `cards[]` does (open wins, else the last by executionId)."""
    rows = [row for row in ExecutionPullRequests(db, project, workspace).listing() if row["node_id"] == node]
    chosen = None
    for row in sorted(rows, key=lambda item: (item["execution_id"], item["state"])):
        if chosen is None or row["state"] == "open" or chosen["state"] != "open":
            chosen = row
    return chosen


def gate_summary(gate):
    """`{status, rule}` of one review gate: the rule is the agent-state priority reason, else the first reason."""
    if gate is None:
        return None
    from backend.canvas import opora_agent_state_review_gates as review_gates
    status, reasons = gate["reviewGate"]["status"], gate["reviewGate"]["reasons"]
    rule = review_gates.stage_reason([gate], status, None) if status in ("blocked", "pending") else None
    return {"status": status, "rule": rule or (reasons[0] if reasons else None)}


def _gate(db, project, workspace, row, now):
    if row is None or row["state"] != "open":
        return None
    config = reviews.config()
    if not config["enabled"]:
        return None
    from backend.canvas.opora_review_gate import gate
    from database.repositories.opora_review_evidence import ReviewEvidenceRepository
    from database.repositories.opora_review_jobs import ReviewJobs
    try:
        evidence = ReviewEvidenceRepository(db, project, workspace).list(100)
    except ValueError:
        evidence = None
    return gate(ReviewJobs(db, project, workspace), row, evidence, config, now)


def compute(db, project, workspace, node, now=None):
    """`(entry, gate)` for one card: the agent-state stage entry and the review gate summary (or None)."""
    now = time.time() if now is None else now
    accepted = ChangesetRepository(db, project, workspace).head()
    row = _link(db, project, workspace, node)
    gate = _gate(db, project, workspace, row, now)
    link = None if row is None else public(row)
    card = {"nodeId": node, "doneConfirmed": _done(db, project, workspace, node)}
    latest = _latest(db, project, workspace, node, accepted, card["doneConfirmed"])
    entry = card_stages.card_stage(card, accepted, latest, None, link, gate, now)
    return entry, gate_summary(gate)


def refresh_card(db, project, workspace, node, *, actor):
    """Emit the card's changed stage/gate; returns the emitted kinds. Isolated in a savepoint."""
    from backend.canvas.opora_events import emit_event, stamp
    db.execute("SAVEPOINT opora_event_stage")
    try:
        entry, gate = compute(db, project, workspace, node)
        previous = db.execute("SELECT stage,health,reason,gate_status,gate_rule FROM opora_event_card_state"
                              " WHERE project_id=? AND workspace_id=? AND node_id=?",
                              (project, workspace, node)).fetchone()
        emitted = []
        before = tuple(previous[:3]) if previous else None
        if before != (entry["stage"], entry["health"], entry["reason"]):
            emit_event(db, project_id=project, workspace_id=workspace, kind="stage.changed", node_id=node,
                       execution_id=entry["executionId"], stage=entry["stage"], health=entry["health"], actor=actor,
                       data={"reason": entry["reason"], "previous": None if before is None else
                             {"stage": before[0], "health": before[1], "reason": before[2]}})
            emitted.append("stage.changed")
        old_gate = None if previous is None or previous[3] is None else {"status": previous[3], "rule": previous[4]}
        if gate != old_gate:
            emit_event(db, project_id=project, workspace_id=workspace, kind="gate.changed", node_id=node,
                       execution_id=entry["executionId"], actor=actor,
                       data={"gate": gate, "previous": old_gate})
            emitted.append("gate.changed")
        if emitted:
            db.execute("INSERT INTO opora_event_card_state VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(project_id,"
                       "workspace_id,node_id) DO UPDATE SET stage=excluded.stage,health=excluded.health,"
                       "reason=excluded.reason,gate_status=excluded.gate_status,gate_rule=excluded.gate_rule,"
                       "updated_at=excluded.updated_at",
                       (project, workspace, node, entry["stage"], entry["health"], entry["reason"],
                        gate and gate["status"], gate and gate["rule"], stamp()))
        db.execute("RELEASE opora_event_stage")
        return emitted
    except Exception:  # noqa: BLE001 - a derived stage must never undo the change that triggered it
        db.execute("ROLLBACK TO opora_event_stage")
        db.execute("RELEASE opora_event_stage")
        return []


def node_of_execution(db, project, workspace, execution_id):
    row = db.execute("SELECT node_id FROM opora_executions WHERE id=? AND project_id=? AND workspace_id=?",
                     (execution_id, project, workspace)).fetchone()
    return row[0] if row else None


def nodes_of_pull_request(db, project, workspace, number):
    rows = db.execute("SELECT DISTINCT node_id FROM opora_execution_pull_requests WHERE project_id=? AND"
                      " workspace_id=? AND number=?", (project, workspace, number)).fetchall()
    return sorted(row[0] for row in rows)

