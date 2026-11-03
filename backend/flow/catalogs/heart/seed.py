"""Srdce v1: sdílené workflow `kind=heart`, které věrně opakuje dřívější napevno zadrátovaný plánovač dávek (§3.2, §5).

Spouštěče → Jev → snímek → agent s modelem (Haiku + poradce Opus) a celým nástrojem `opora_heart.py`.
Stropy dávek jsou parametry agenta (6 za hodinu, 1 na projekt, spánek 15 min po limitu předplatného),
rozvrh karet je `trigger.schedule` po 600 s (dřív `CARD_POLL`).
"""

from backend.flow import workflows

NAME = "Srdce v1"


def _node(nid, type_, x, y, **params):
    return {"id": nid, "type": type_, "type_version": 1, "params": params, "position": {"x": x, "y": y}}


def _edge(eid, source, target, target_port="main", kind="main"):
    return {"id": eid, "source_node": source, "source_port": kind if kind != "main" else "main",
            "target_node": target, "target_port": target_port, "kind": kind, "label": ""}


GRAPH = {
    "nodes": [
        _node("udalost", "trigger.heart_event", 0, 0),
        _node("zprava", "trigger.human_message", 0, 160),
        _node("rozvrh", "trigger.schedule", 0, 320, interval_seconds=600),
        _node("jev", "decision.jev", 260, 80),
        _node("snimek", "context.snapshot", 520, 80),
        _node("srdce", "agent.claude", 780, 80, per_hour=6, per_project=1, rate_sleep_seconds=900),
        _node("model", "model.claude", 700, 280, model="haiku", advisor="opus"),
        _node("nastroj", "tool.opora_heart", 880, 280, subcommands=None),
    ],
    "edges": [
        _edge("udalost-jev", "udalost", "jev"),
        _edge("zprava-jev", "zprava", "jev"),
        _edge("jev-snimek", "jev", "snimek"),
        _edge("snimek-srdce", "snimek", "srdce"),
        _edge("model-srdce", "model", "srdce", "model", "model"),
        _edge("nastroj-srdce", "nastroj", "srdce", "tool", "tool"),
    ],
}


def ensure_active(db):
    """Sdílené workflow srdce s aktivní verzí; existující aktivní verzi nechá být (i upravenou). Vrací (workflow, verze)."""
    row = db.execute("SELECT id FROM flow_workflows WHERE kind='heart' AND project_id IS NULL AND name=? "
                     "ORDER BY created_at LIMIT 1", (NAME,)).fetchone()
    workflow_id = row["id"] if row else workflows.create_workflow(db, "heart", NAME)["id"]
    active = db.execute("SELECT id FROM flow_workflow_versions WHERE workflow_id=? AND status='active'",
                        (workflow_id,)).fetchone()
    if active:
        return workflow_id, active["id"]
    version = workflows.create_draft(db, workflow_id, GRAPH)
    workflows.set_candidate(db, version["id"])
    return workflow_id, workflows.activate(db, version["id"])["id"]
