"""Plan-step facts for process sync and agent-state `cards[]` (docs/oporahub-plan-steps.md).

`card_plan` is the readiness input of one card: accepted plan steps with their progress,
whether the card acceptance is evidenced against the current accepted spec, and `blockedBy`.
`blockedBy` comes from the card DAG (night contract §2); `require_ready` is the same rule
enforced by the claim endpoint (409 `plan_steps_missing` / `blocked_by_predecessor`). `attach` adds
the `steps` summary (with per-step `items`, aggregated over all runs) and the single definition
of done `dod` (opora_card_done) to each agent-state card entry.
"""
from backend.canvas import opora_card_done as card_done
from backend.canvas.opora_step_results import progress_detail, with_after_merge

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


def card_plan(db, project, workspace, node, accepted_document, blocked, link=None):
    """Readiness input of one card; with a merged `link` also `afterMerge` (steps and acceptance added after the
    merge, opora_card_done.after_merge_facts) and those steps as `after_merge` in `stepItems`."""
    summary, evidence, items = progress_detail(db, project, workspace, node, accepted_document)
    late = card_done.after_merge_facts(db, project, workspace, node, accepted_document, link) if items else None
    if late and late["steps"] and summary["done"] + len(late["steps"]) >= summary["total"]:
        summary, items = with_after_merge(summary, items, {item["id"] for item in late["steps"]})
    return {"steps": summary, "stepItems": items, "acceptanceEvidence": evidence, "afterMerge": late,
            "blockedBy": sorted(blocked.get(node) or [])}


def dod(card, linked, gates, local=None):
    """`cards[].dod`: one boolean per requirement of the single definition of done (keys = opora_card_done
    REQUIREMENTS) + `gate` kind (`review` / `external` / `local`), `done` and `missing` in contract order; while
    the journey gate is missing also `blockingJourneys` [{journeyId, applicationId, name, reason}]; requirements
    met by the merge (added after it) also `afterMerge` + `afterMergeEvidence` (docs/oporahub-plan-steps.md).
    `local` = None (project with GitHub) or `{nodeId: checks passed}` (docs/lokalni-slouceni.md)."""
    link = card_done.link_for(linked, card.get("nodeId"))
    gate = (gates or {}).get(link["executionId"]) if link else None
    checks = None if local is None else local.get(card.get("nodeId"), True)
    state = card_done.card_done_state(card_done.facts(card, link, gate, closed=card.get("doneConfirmed") is True,
                                                      external=gates is None, local_checks=checks))
    return {**{name: name not in state["missing"] for name in card_done.REQUIREMENTS},
            "gate": state["gate"], "done": state["done"], "missing": state["missing"],
            **({"blockingJourneys": state["blockingJourneys"]} if "blockingJourneys" in state else {}),
            **({key: state[key] for key in ("afterMerge", "afterMergeEvidence")} if "afterMerge" in state else {})}


def attach(entries, cards, linked=None, gates=None, local=None):
    """Agent-state `cards[]` entries gain `steps: {total, done, current, items}` and `dod`."""
    empty = {"total": 0, "done": 0, "current": None}
    result = []
    for entry in entries:
        card = cards.get(entry["nodeId"], {})
        result.append({**entry, "steps": {**card.get("steps", empty), "items": card.get("stepItems", [])},
                       "dod": dod({**card, "nodeId": entry["nodeId"]}, linked, gates, local)})
    return result
