"""Finite workflow/library reads resolve native ownership before ID-only access."""
from fastapi import HTTPException
from backend.flow import workflows, interpreter
from backend.flow.run_log import read_log
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import FlowConflict, FlowNotFound
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.canvas_capabilities.contracts import contract

CONTRACTS = {
    "flow_routes.workflow_list": contract(optional=("kind", "owner_ref")),
    "flow_routes.version_list": contract(("workflow_id",)),
    "flow_routes.run_list": contract(("workflow",), ("limit",), types={"limit": "integer"}),
    "flow_routes.run_detail": contract(("run_id",)),
    "flow_routes.run_log": contract(("run_id",), ("seq", "limit"), types={"seq": "integer", "limit": "integer"}),
}


def owner(db, project, **identifiers):
    found = workflows.workflow_of(db, **identifiers)
    if found is None or found["project_id"] != project:
        raise GateError(403, "gate_scope", "Workflow does not belong to this project or shared library.", "Use a scoped workflow.")


def read(service, project, capability, data):
    try:
        with service.registry_lock:
            db = service.db
            if "workflow_id" in data or "workflow" in data:
                owner(db, project, workflow_id=data.get("workflow_id", data.get("workflow")))
            if "run_id" in data:
                owner(db, project, run_id=data["run_id"])
            if capability == "flow_routes.workflow_list":
                if data.get("kind") not in (None, "heart", "page_intent", "library_flow"):
                    raise FlowInvalid("Unknown workflow kind.")
                return {"workflows": workflows.list_workflows(db, project, data.get("kind"), data.get("owner_ref"))}
            if capability == "flow_routes.version_list":
                return {"versions": workflows.list_versions(db, data["workflow_id"])}
            if capability == "flow_routes.run_list":
                limit = data.get("limit", 100)
                if not 1 <= limit <= 500:
                    raise FlowInvalid("limit must be 1..500")
                return {"runs": interpreter.list_runs(db, data["workflow"], limit)}
            if capability == "flow_routes.run_detail":
                return interpreter.get_run(db, data["run_id"])
            if capability == "flow_routes.run_log":
                seq, limit = data.get("seq", 0), data.get("limit", 500)
                if seq < 0 or not 1 <= limit <= 2000:
                    raise FlowInvalid("seq must be nonnegative and limit 1..2000")
                interpreter.get_run(db, data["run_id"])
                return {"events": read_log(db, data["run_id"], seq, limit)}
    except FlowNotFound as error:
        raise HTTPException(404, str(error)) from error
    except FlowConflict as error:
        raise HTTPException(409, str(error)) from error
    except FlowInvalid as error:
        raise HTTPException(422, str(error)) from error
    raise RuntimeError("Unknown finite flow read")
