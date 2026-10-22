"""Plan-step facts for process sync and agent-state `cards[]` (docs/oporahub-plan-steps.md).

`card_plan` is the readiness input of one card: accepted plan steps with their progress,
whether the card acceptance is evidenced against the current accepted spec, and `blockedBy`.
`blockedBy` comes from the card DAG module (night contract §2) when it is installed; until
then it reads as empty. `attach` adds the `steps` summary to each agent-state card entry.
"""
from backend.canvas.opora_step_results import progress


def blocked_by(canvas, project, workspace):
    """`{nodeId: [predecessor nodeId, ...]}` from `opora_card_dag.blocked_by`, else {}."""
    try:
        from backend.canvas.opora_card_dag import blocked_by as source
    except ImportError:
        return {}
    return source(canvas, project, workspace) or {}


def card_plan(db, project, workspace, node, accepted_document, blocked):
    summary, evidence = progress(db, project, workspace, node, accepted_document)
    return {"steps": summary, "acceptanceEvidence": evidence, "blockedBy": sorted(blocked.get(node) or [])}


def attach(entries, cards):
    """Agent-state `cards[]` entries gain `steps: {total, done, current}` from the process card."""
    empty = {"total": 0, "done": 0, "current": None}
    return [{**entry, "steps": cards.get(entry["nodeId"], {}).get("steps", empty)} for entry in entries]
