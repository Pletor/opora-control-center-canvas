"""Merge write-back: reconciliation facts close the execution loop exactly once.

Reads only the immutable reconciliation observations of each linked binding. Never
touches spec fields (goal/non_goals/acceptance) or card closure; confirming a card as
done stays a human action, so a merge sets the `awaitingHumanClose` marker instead."""
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


def merge_events(db, project, workspace, row, pr):
    """Merge and its plan write-back are one act here; the human close decision opens with them."""
    for kind, data in (("merge.done", {"mergeSha": pr["mergeCommitSha"], "mergedAt": pr["mergedAt"]}),
                       ("writeback.done", {"mergeSha": pr["mergeCommitSha"], "planWrittenBack": True}),
                       ("decision.created", {"decision": "close_card", "mergeSha": pr["mergeCommitSha"]})):
        emit_event(db, project_id=project, workspace_id=workspace, kind=kind, node_id=row["node_id"],
                   execution_id=row["execution_id"], pr_number=row["number"], data={"repository": row["repository"], **data})


def close_loop(db, project, workspace):
    """Caller holds graph -> project locks and BEGIN IMMEDIATE. Returns emitted event kinds."""
    links = ExecutionPullRequests(db, project, workspace)
    recon = ReconciliationRepository(db, project, workspace)
    executions = Executions(db, project, workspace)
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
            merged = links.event(key, row["execution_id"], "execution.merged",
                                 _event_content(row, observation, mergeSha=pr["mergeCommitSha"], mergedAt=pr["mergedAt"],
                                                prNumber=row["number"]), stamp())
            if merged:
                emitted.append("execution.merged")
            links.update(row["execution_id"], state="merged", merge_sha=pr["mergeCommitSha"], merged_at=pr["mergedAt"],
                         head_sha=pr["headSha"], awaiting_human_close=1, attention=None, updated_at=stamp())
            _finish_execution(executions, row["execution_id"])
            if merged:
                merge_events(db, project, workspace, row, pr)
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
