"""Exact native workflow review; projection only, never another approval record."""
import hashlib
import json
from urllib.parse import urlencode

from backend.flow import interpreter, workflows
from backend.flow.graph_check import FlowInvalid
from backend.brain_opora.determinism.gate_payloads import GateError

OPERATIONS = {"version_candidate", "version_activate", "version_approve", "version_reject", "version_rollback", "approval_decision"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def observe(db, operation, identifier, project=None):
    if operation not in OPERATIONS:
        raise FlowInvalid("Unknown native workflow review operation.")
    node_run = None
    if operation == "approval_decision":
        row = db.execute("SELECT * FROM flow_node_runs WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise workflows.FlowNotFound("Approval node run does not exist.")
        node_run = dict(row)
        workflow = workflows.workflow_of(db, run_id=row["run_id"])
        run = interpreter.get_run(db, row["run_id"])
        selected = workflows.get_version(db, run["workflow_version_id"])
    elif operation == "version_rollback":
        workflow = workflows.workflow_of(db, workflow_id=identifier)
        selected = None
    else:
        workflow = workflows.workflow_of(db, version_id=identifier)
        selected = workflows.get_version(db, identifier) if workflow else None
    if workflow is None:
        raise workflows.FlowNotFound("Workflow does not exist.")
    shared = workflow["project_id"] is None and workflow["kind"] == "library_flow" and workflows.LIBRARY_OWNER.fullmatch(workflow["owner_ref"] or "")
    if project is not None and workflow["project_id"] != project and not shared:
        raise GateError(403, "gate_scope", "Workflow belongs to another project.", "Use the authenticated project.")
    versions = workflows.list_versions(db, workflow["id"])
    active = next((v for v in versions if v["status"] == "active"), None)
    if operation == "version_rollback" and active:
        rejected = {json.loads(r[0])["version_id"] for r in db.execute("SELECT payload FROM flow_log_events WHERE type='version.rejected'")}
        selected = next((v for v in sorted(versions, key=lambda v: -v["n"]) if v["status"] == "retired" and v["n"] < active["n"] and v["id"] not in rejected), None)
    result = {"operation": operation, "identifier": identifier, "workflow": dict(workflow), "selected": selected, "active": active, "nodeRun": node_run}
    result["digest"] = digest(result)
    if project is not None:
        from backend.brain_opora.canvas_capabilities.library_reads import _meta, _source
        for key in ("selected", "active"):
            if result[key]:
                value = result[key]
                result[key] = {**value, "meta": _meta(project, value.get("meta")), "derived_from": _source(db, project, value.get("derived_from"))}
    return result


def check(db, operation, identifier, expected):
    if expected is not None and observe(db, operation, identifier)["digest"] != expected:
        raise workflows.FlowConflict("Workflow changed since review. Refresh and review the current version.", "flow_review_stale")


def owned(db, project, **ids):
    row = workflows.workflow_of(db, **ids)
    if row is None:
        raise workflows.FlowNotFound("Workflow does not exist.")
    part = workflows.library_part(db, **ids)
    if row["project_id"] != project and not part:
        raise GateError(403, "gate_scope", "Workflow belongs to another project.", "Use own project or published Library workflow.")
    return dict(row), part


def prepared(project, workspace, result):
    url = "/?" + urlencode({"project": project, "workspace": workspace, "screen": "canvas", "environment": "project",
                            "projectView": "library", "flowReview": result["identifier"], "flowOperation": result["operation"]})
    return {"state": "awaiting_human", "applied": False, "result": result, "url": url}


