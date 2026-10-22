"""Plan-step facts for process sync and agent-state `cards[]` (docs/oporahub-plan-steps.md).

`card_plan` is the readiness input of one card: accepted plan steps with their progress,
whether the card acceptance is evidenced against the current accepted spec, and `blockedBy`.
`blockedBy` comes from the card DAG (night contract §2); `require_ready` is the same rule
enforced by the claim endpoint (409 `plan_steps_missing` / `blocked_by_predecessor`). `attach` adds the `steps` summary to each agent-state card entry.
"""
from backend.canvas.opora_step_results import progress

REQUIRE_STEPS = True  # Product rule; only pre-plan-steps test suites switch it off (backend/conftest.py).


def blocked_by(canvas, project, workspace):
    """`{nodeId: [predecessor nodeId, ...]}` from the card DAG (opora_agent_state_dag, contract §2)."""
    from backend.canvas import opora_agent_state_dag as dag_state
    from backend.canvas import opora_agent_state_pulls as pulls

    return dag_state.facts(canvas, project, workspace, pulls.read(canvas, project, workspace))["blockedBy"]


class ClaimRefused(ValueError):
    """A claim of a card that is not ready; `code` is the 409 error code of the claim endpoint."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require_ready(canvas, project, workspace, node, captured):
    """Claim precondition: accepted spec with >=1 plan step and no unfinished predecessor."""
    if REQUIRE_STEPS and not captured.get("steps"):
        raise ClaimRefused("plan_steps_missing", "Card has no accepted plan steps; it is not ready to claim.")
    blockers = sorted(blocked_by(canvas, project, workspace).get(node) or [])
    if blockers:
        raise ClaimRefused("blocked_by_predecessor", "Card is blocked by unfinished predecessors: "
                           + ", ".join(blockers) + ".")


def card_plan(db, project, workspace, node, accepted_document, blocked):
    summary, evidence = progress(db, project, workspace, node, accepted_document)
    return {"steps": summary, "acceptanceEvidence": evidence, "blockedBy": sorted(blocked.get(node) or [])}


def attach(entries, cards):
    """Agent-state `cards[]` entries gain `steps: {total, done, current}` from the process card."""
    empty = {"total": 0, "done": 0, "current": None}
    return [{**entry, "steps": cards.get(entry["nodeId"], {}).get("steps", empty)} for entry in entries]
