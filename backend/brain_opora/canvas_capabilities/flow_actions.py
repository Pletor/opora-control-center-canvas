"""Finite native workflow transitions, scoped observations and real human review."""
from fastapi import HTTPException
from pydantic import ValidationError

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.flow import page_intents, review, workflows
from backend.flow.review import owned, prepared
from backend.flow.graph_check import FlowInvalid
from backend.flow.stalls import list_stalls
from backend.project.architecture.work_status import architecture_graph

CONTRACTS = {
    "flow_routes.review": contract(("operation", "identifier"), output="Exact scoped native version/run, active version and review digest"),
    "flow_routes.page_intent_list": contract(),
    "flow_routes.stalls": contract(),
    "flow_routes.version_candidate": contract(("version_id",), ("eval_run_id",), effect="draft", replay=True),
    "flow_routes.version_activate": contract(("version_id", "expectedReviewDigest"), effect="draft", replay=True),
    "flow_routes.version_rollback": contract(("workflow_id", "expectedReviewDigest"), effect="draft", replay=True),
    "flow_routes.version_approve": contract(("version_id",), effect="human-decision"),
    "flow_routes.version_reject": contract(("version_id",), ("reason",), effect="human-decision"),
    "flow_routes.approval_decision": contract(("node_run_id",), ("decision",), effect="human-decision"),
    "flow_routes.run_manual": contract(("version_id",), ("payload", "node_id"), effect="draft", replay=True),
    "flow_routes.run_advance": contract(("run_id",), effect="draft", replay=True),
    "flow_routes.canvas_log_create": contract(("canvas", "kind"), ("payload",), effect="draft", replay=True),
}
for _item in CONTRACTS.values():
    _item["test"] = "backend/api/brain_opora/test_canvas_capability_flow_actions.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    operation = capability.split(".")[1]
    try:
        if operation == "page_intent_list":
            graph = architecture_graph(service, project)
            with service.registry_lock:
                return {"state": "read", "result": {"pages": page_intents.status(service.db, project, page_intents.pages_of(graph))}}
        with service.registry_lock:
            db = service.db
            if operation == "stalls":
                visible = [row for row in list_stalls(db) if workflows.project_of(db, run_id=row["run_id"]) == project]
                return {"state": "read", "result": {"stalls": visible}}
            if operation == "review":
                return {"state": "read", "result": review.observe(db, data["operation"], data["identifier"], project)}
            if operation in ("version_approve", "version_reject", "approval_decision"):
                result = review.observe(db, operation, data.get("version_id", data.get("node_run_id")), project)
                if data.get("decision") not in (None, "approved", "rejected"):
                    raise FlowInvalid("Decision is approved or rejected.")
                return prepared(project, workspace, result)
        from backend.flow.capability_actions import write
        return write(service, project, workspace, session, operation, data, request_id)
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_url=False, include_context=False)) from error
    except workflows.FlowNotFound as error:
        raise HTTPException(404, str(error)) from error
    except workflows.FlowConflict as error:
        raise HTTPException(409, {"code": error.code, "error": str(error)}) from error
    except FlowInvalid as error:
        raise HTTPException(422, str(error)) from error
