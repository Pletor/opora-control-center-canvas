"""Per-step checkpoints of a running execution (A/B protokol M4, docs/oporahub-plan-steps.md).

`POST /api/oporahub/executions/{id}/steps` records one step as soon as it is finished, with the same
credential, epoch and authority checks as the final result. A crash after two of four steps then
keeps those two: the step read model (`opora_step_results.reports`) counts checkpoints like
`stepResults`, so agent-state shows them and the next execution of the card starts at the first
unfinished step. Same `requestId` + same content returns the same checkpoint; never a card mutation.
"""
import json
import time
import uuid

from backend.canvas.canvas_service import now
from backend.canvas.graph import digest
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_step_results import (
    emit_step_started,
    reports,
    step_items,
    summary,
    validate_step_results,
)

FIELDS = {"token", "epoch", "requestId", "stepId", "status", "evidence"}


def checkpoint(executions, identifier, payload):
    """Validate, authenticate and store one step checkpoint; returns the (replayed) checkpoint."""
    project, workspace = validate(payload, FIELDS)
    item = {key: payload[key] for key in ("stepId", "status", "evidence")}
    try:
        encoded = json.dumps(item, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Step checkpoint must be bounded JSON.") from exc
    if len(encoded) > 16_000:
        raise ValueError("Step checkpoint exceeds 16000 characters.")
    fingerprint = digest(item)
    with executions.transaction(project, workspace) as repo:
        record = repo.read(identifier)
        executions.authenticate(record, payload["token"], payload["epoch"])
        prior = repo.step(identifier, payload["requestId"])
        if prior:
            if prior[0] != fingerprint:
                raise ValueError("Step request identity was already used for different content.")
            return prior[1]
        executions.active(repo, record)
        validate_step_results({"stepResults": [item]}, record["assignment"].get("steps"))
        stored = {"checkpointId": uuid.uuid4().hex, "executionId": identifier, "requestId": payload["requestId"],
                  **item, "acceptedRevision": record["acceptedRevision"], "epoch": record["epoch"],
                  "verification": "agent-reported; not independently verified", "createdAt": now()}
        executions.lease_valid(repo, record)
        from backend.canvas.opora_execution_budget_runtime import check
        check(repo.db, repo.scope, record, time.time())
        already = reported_pairs(repo, identifier)
        repo.insert_step(identifier, payload["requestId"], fingerprint, stored)
        if (item["stepId"], item["status"]) not in already and item["status"] in ("done", "failed"):
            from backend.canvas.opora_events import emit_event
            emit_event(repo.db, project_id=project, workspace_id=workspace, kind="step." + item["status"],
                       node_id=record["nodeId"], execution_id=identifier, step_id=item["stepId"], actor=None,
                       data={"status": item["status"], "checkpoint": True})
            if item["status"] == "done":
                emit_step_started(repo.db, record)  # the next unfinished step, if any
        return stored


def reported_pairs(repo, identifier):
    """`{(stepId, status)}` already announced by this execution's checkpoints (no duplicate events)."""
    return {(entry["stepId"], entry["status"]) for entry in repo.steps(identifier)}


def assignment_progress(db, record):
    """Live progress of the steps pinned in this execution, over every execution of the card.

    Not part of the immutable assignment or its digest: `{total, done, current, steps: [{id, status,
    executionId}]}` so a new run continues from `current` instead of step one."""
    steps = (record.get("assignment") or {}).get("steps") or []
    found = reports(db, record["project"], record["workspace"], record["nodeId"], steps)
    value = summary(steps, {key: item["status"] for key, item in found.items()})
    return {**value, "steps": step_items(steps, found) if steps else []}
