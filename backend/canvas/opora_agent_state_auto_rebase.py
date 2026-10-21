"""Optional seam to server-side auto-rebase (docs/oporahub-auto-rebase.md, "Stav pro agenty").

With auto-rebase enabled, the `proposal` stage counts only stale proposals the loop has not
settled (redundant ones and those whose conflict was resolved are settled), reports open
conflicts as `waiting/auto_rebase_conflicts` with a `proposal.resolve_conflict` action and the
`auto_rebase` gap disappears. Disabled (`OPORA_AUTO_REBASE=0`) returns None: previous rules stay.
Read-only: plain SELECTs, no transaction."""
from backend.canvas import opora_agent_state_rules as rules
from backend.canvas import opora_auto_rebase as auto
from database.repositories.opora_auto_rebase import AutoRebaseStore

VERB = "proposal.resolve_conflict"


def read(canvas, project, workspace):
    if not auto.enabled():
        return None
    store = AutoRebaseStore(canvas.db_for(project), project, workspace)
    resolved = {item["proposalId"] for item in store.conflicts("resolved", limit=10000)}
    return {"open": store.conflicts("open"), "settled": store.redundant() | resolved}


def proposal_stage(pending, rebasing):
    if rebasing is None:
        return rules.proposal_stage(pending)
    unsettled = [item for item in pending if item["stale"] and item["id"] not in rebasing["settled"]]
    if rebasing["open"]:
        return rules.stage("proposal", len(rebasing["open"]), "waiting", "auto_rebase_conflicts")
    if unsettled:
        return rules.stage("proposal", len(unsettled), "waiting", "stale_proposals")
    return rules.stage("proposal", len(pending), "ok", "proposals_current" if pending else "no_pending_proposals")


def actions(project, workspace, rebasing):
    if rebasing is None:
        return []
    return [{"id": rules.stable_id("act_", VERB, item["id"], item["acceptedHead"]), "verb": VERB, "method": "POST",
             "path": f"/api/oporahub/auto-rebase/conflicts/{item['id']}/resolve", "targetId": item["id"],
             "preconditions": {"project": project, "workspace": workspace, "expectedAcceptedHead": item["acceptedHead"],
                               "proposalKind": item["proposalKind"], "proposalId": item["proposalId"]},
             "status": "ready"} for item in sorted(rebasing["open"], key=lambda value: value["id"])]


def gaps(values, rebasing):
    return [gap for gap in values if rebasing is None or gap[0] != "auto_rebase"]
