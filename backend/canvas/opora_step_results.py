"""Runtime step progress: `stepResults` in execution results and the per-card read model.

Progress is not part of the spec (night contract §1). An execution result may carry
`stepResults: [{stepId, status: done|failed|skipped, evidence: {checks?, commits?, notes}}]`;
it is validated against the steps pinned in that execution's assignment and stored inside
the idempotent result receipt (same requestId → same receipt). The read model per card is
derived from those receipts over every execution of the card: a report counts only while
its pinned step definition still equals the accepted one; a step reported `done` by any run
stays done (a later failed/skipped run does not undo it), otherwise the newest report wins.
docs/oporahub-plan-steps.md.
"""
import re

from backend.canvas.graph import digest
from backend.canvas.opora_plan_steps import ordered, steps_of, topological
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_executions import Executions

STATUSES = ("done", "failed", "skipped")
EVIDENCE = {"checks", "commits", "notes"}
SHA = re.compile(r"[a-f0-9]{7,40}")


def _list(value, limit, item_ok, label):
    if not isinstance(value, list) or len(value) > limit or not all(item_ok(item) for item in value):
        raise ValueError(f"stepResults: {label} je pole nejvýše {limit} platných položek.")


def validate_step_results(result, pinned_steps):
    """Validate optional `result.stepResults` against the steps pinned in the assignment."""
    if "stepResults" not in result:
        return []
    items, known = result["stepResults"], {item["id"] for item in pinned_steps or []}
    if not isinstance(items, list) or len(items) > max(len(known), 0):
        raise ValueError("stepResults je pole nejvýše jedné položky na krok přiřazeného plánu.")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"stepId", "status", "evidence"}:
            raise ValueError("Položka stepResults vyžaduje stepId, status a evidence.")
        if item["stepId"] not in known or item["stepId"] in seen:
            raise ValueError("stepResults odkazuje na krok mimo přiřazený plán nebo se opakuje.")
        seen.add(item["stepId"])
        if item["status"] not in STATUSES:
            raise ValueError("Stav kroku je done, failed nebo skipped.")
        evidence = item["evidence"]
        if not isinstance(evidence, dict) or "notes" not in evidence or not set(evidence) <= EVIDENCE:
            raise ValueError("evidence kroku vyžaduje notes (volitelně checks, commits).")
        if not isinstance(evidence["notes"], str) or len(evidence["notes"]) > 4000 or "\0" in evidence["notes"]:
            raise ValueError("notes kroku je text do 4000 znaků.")
        if "checks" in evidence:
            _list(evidence["checks"], 50, lambda value: isinstance(value, str) and 0 < len(value) <= 500, "checks")
        if "commits" in evidence:
            _list(evidence["commits"], 50, lambda value: isinstance(value, str) and SHA.fullmatch(value), "commits")
    return items


def emit_step_events(db, record, items):
    """`step.done` / `step.failed` into the events outbox, in the result transaction."""
    from backend.canvas.opora_events import emit_event

    for item in items:
        if item["status"] in ("done", "failed"):
            emit_event(db, project_id=record["project"], workspace_id=record["workspace"],
                       kind="step." + item["status"], node_id=record["nodeId"], execution_id=record["executionId"],
                       step_id=item["stepId"], actor=None, data={"status": item["status"]})


def emit_step_started(db, record):
    """`step.started` for the first not-done pinned step when a claim starts an execution."""
    from backend.canvas.opora_events import emit_event

    steps = record["assignment"].get("steps") or []
    if not steps:
        return
    document = {"fields": {"steps": steps}}
    current = progress(db, record["project"], record["workspace"], record["nodeId"], document)[0]["current"]
    if current is not None:
        emit_event(db, project_id=record["project"], workspace_id=record["workspace"], kind="step.started",
                   node_id=record["nodeId"], execution_id=record["executionId"], step_id=current, actor=None,
                   data={"epoch": record["epoch"]})


def _same(pinned, current):
    return pinned is not None and digest(pinned) in (digest(current), digest(redact_deep(current)))


def reports(db, project, workspace, node, steps):
    """`{stepId: {status, executionId}}` for the accepted `steps`, aggregated over all executions.

    Only reports whose pinned definition equals the accepted one count. `done` sticks: the newest
    valid `done` report wins; a step never reported done takes its newest valid report."""
    repo, current, found = Executions(db, project, workspace), {item["id"]: item for item in steps}, {}
    for record in repo.history(node):  # newest execution first
        pinned = {item["id"]: item for item in (record.get("assignment") or {}).get("steps", [])}
        for receipt in reversed(repo.receipts(record["executionId"])):
            for item in (receipt.get("result") or {}).get("stepResults", []):
                step = item.get("stepId")
                if step not in current or not _same(pinned.get(step), current[step]):
                    continue
                if step not in found or (item.get("status") == "done" and found[step]["status"] != "done"):
                    found[step] = {"status": item.get("status"), "executionId": record["executionId"]}
    return found


def statuses(db, project, workspace, node, steps):
    """`{stepId: status}` for the accepted `steps` (see `reports`)."""
    return {key: value["status"] for key, value in reports(db, project, workspace, node, steps).items()}


def step_items(steps, found):
    """Per-step progress in topological order: `[{id, status, executionId}]`; `status` is
    done/failed/skipped from `reports`, else `current` (the summary's current step) or `waiting`."""
    current = summary(steps, {key: value["status"] for key, value in found.items()})["current"]
    order = topological(steps) or [item["id"] for item in ordered(steps)]
    return [{"id": step, "status": found[step]["status"] if step in found else "current" if step == current else "waiting",
             "executionId": found[step]["executionId"] if step in found else None} for step in order]


def summary(steps, found):
    """`{total, done, current}`: `current` is the first step (topological) not yet done."""
    done = {key for key, value in found.items() if value == "done"}
    for step in topological(steps) or [item["id"] for item in ordered(steps)]:
        if step not in done:
            return {"total": len(steps), "done": len(done), "current": step}
    return {"total": len(steps), "done": len(done), "current": None}


def acceptance_evidence(db, project, workspace, node, document):
    """True when the newest reported execution of the card ran on its current accepted spec."""
    repo = Executions(db, project, workspace)
    for record in repo.history(node):
        if not repo.receipts(record["executionId"]):
            continue
        pinned = next((item for item in (record.get("assignment") or {}).get("documents", [])
                       if item.get("nodeId") == node), None)
        return document is not None and pinned is not None and _same(pinned, document)
    return False


def progress(db, project, workspace, node, document):
    """Read model for one card: `{total, done, current}` plus `acceptanceEvidence`."""
    value, evidence, _ = progress_detail(db, project, workspace, node, document)
    return value, evidence


def progress_detail(db, project, workspace, node, document):
    """`progress` plus the per-step items (`step_items`) from one read of the receipts."""
    steps = steps_of((document or {}).get("fields"))
    if not steps:
        return {"total": 0, "done": 0, "current": None}, acceptance_evidence(db, project, workspace, node, document), []
    found = reports(db, project, workspace, node, steps)
    value = summary(steps, {key: item["status"] for key, item in found.items()})
    return value, acceptance_evidence(db, project, workspace, node, document), step_items(steps, found)


def plan_view(service, project, workspace, node, result):
    """Node-spec API: add `plan: {working, accepted, acceptedHead}` steps to a read/write result."""
    working = steps_of(result.get("fields"))
    with service.reading(project):
        repo = ChangesetRepository(service.db_for(project), project, workspace)
        head = repo.head()
        documents = repo.read(head)["documents"] if head else []
    document = next((item for item in documents if item["nodeId"] == node), None)
    accepted = steps_of(document["fields"]) if document else None
    return {**result, "plan": {"working": working, "accepted": accepted, "acceptedHead": head,
                               "workingDiffers": accepted is None or accepted != working}}
