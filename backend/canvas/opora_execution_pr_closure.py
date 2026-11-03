"""Merge write-back: reconciliation facts close the execution loop exactly once.

Reads only the immutable reconciliation observations of each linked binding. Never
touches spec fields (goal/non_goals/acceptance) or card closure; a merge sets the `awaitingHumanClose`
marker (the name stays) and the server closes the card itself once the definition of done is met
(opora_card_auto_close, run by the same PR loop). `write_back` is shared with the local merge
(docs/lokalni-slouceni.md)."""
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_events import emit_event, refresh
from backend.canvas.opora_executions import OporaExecutions
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_executions import Executions
from database.repositories.opora_reconciliation import ReconciliationRepository


def _event_content(row, observation, **extra):
    return {"executionId": row["execution_id"], "cardId": row["node_id"], "acceptedRevision": row["accepted_revision"],
            "repository": row["repository"], "number": row["number"], "bindingId": row["binding_id"],
            "observationId": observation["id"], "createdAt": stamp(), **extra}


def _finish_execution(executions, execution_id):
    """A merged PR finishes a still-running execution: its lease is released (existing state)."""
    try:
        record = executions.read(execution_id)
    except ValueError:
        return
    if record["state"] == "running":
        OporaExecutions.finish(executions, record, "released")


def merge_events(db, project, workspace, row, merge_sha, merged_at):
    """Merge and its plan write-back are one act here; the close decision opens with them (the server resolves it).

    A local merge (docs/lokalni-slouceni.md) has no PR number and says `source: "local"` in the data."""
    local = row["source"] == "local"
    extra = {"source": "local", "commit": merge_sha} if local else {}
    for kind, data in (("merge.done", {"mergeSha": merge_sha, "mergedAt": merged_at}),
                       ("writeback.done", {"mergeSha": merge_sha, "planWrittenBack": True}),
                       ("decision.created", {"decision": "close_card", "mergeSha": merge_sha})):
        emit_event(db, project_id=project, workspace_id=workspace, kind=kind, node_id=row["node_id"],
                   execution_id=row["execution_id"], pr_number=None if local else row["number"],
                   data={"repository": row["repository"], **extra, **data})
    from backend.brain_opora.determinism.ticket_lifecycle import safe_follow
    safe_follow(db, project, row["execution_id"])  # ticket exekuce: sloučeno = verified → closed


def write_back(db, project, workspace, row, key, content, merge_sha, merged_at, head_sha):
    """The one merge write-back (`planWrittenBack`) of a merged GitHub PR and of a local merge alike.

    Records `execution.merged` once per `key`, marks the link merged and awaiting the close decision,
    finishes a still-running execution and emits the merge events. Caller holds the locks and the
    transaction. Returns True when the merge is new."""
    links = ExecutionPullRequests(db, project, workspace)
    merged = links.event(key, row["execution_id"], "execution.merged", content, stamp())
    links.update(row["execution_id"], state="merged", merge_sha=merge_sha, merged_at=merged_at, head_sha=head_sha,
                 awaiting_human_close=1, attention=None, updated_at=stamp())
    _finish_execution(Executions(db, project, workspace), row["execution_id"])
    if merged:
        merge_events(db, project, workspace, row, merge_sha, merged_at)
    return merged


def close_loop(db, project, workspace):
    """Caller holds graph -> project locks and BEGIN IMMEDIATE. Returns emitted event kinds."""
    links = ExecutionPullRequests(db, project, workspace)
    recon = ReconciliationRepository(db, project, workspace)
    emitted = []
    for row in links.unresolved():
        if not row["binding_id"]:
            continue
        observation = recon.latest_record("observation", row["binding_id"])
        if observation is None or observation["data"]["pr"]["number"] != row["number"]:
            continue
        pr = observation["data"]["pr"]
        if pr["state"] == "merged":
            key = f"execution.merged:{row['execution_id']}:{pr['mergeCommitSha']}"
            content = _event_content(row, observation, mergeSha=pr["mergeCommitSha"], mergedAt=pr["mergedAt"],
                                     prNumber=row["number"])
            if write_back(db, project, workspace, row, key, content, pr["mergeCommitSha"], pr["mergedAt"], pr["headSha"]):
                emitted.append("execution.merged")
        elif pr["state"] == "closed-unmerged" and row["state"] == "open":
            # Close -> reopen -> close is a new fact: key on the observation that first saw this closure.
            key = f"execution.pr_closed:{row['execution_id']}:{observation['id']}"
            if links.event(key, row["execution_id"], "execution.pr_closed",
                           _event_content(row, observation, prNumber=row["number"], headSha=pr["headSha"]), stamp()):
                emitted.append("execution.pr_closed")
            links.update(row["execution_id"], state="closed", head_sha=pr["headSha"],
                         attention="pr-closed-unmerged", updated_at=stamp())
            refresh(db, project, workspace, row["node_id"])
        elif pr["state"] == "open" and (row["state"] == "closed" or row["head_sha"] != pr["headSha"]):
            links.update(row["execution_id"], state="open", head_sha=pr["headSha"], attention=None, updated_at=stamp())
            refresh(db, project, workspace, row["node_id"])
    return emitted
