"""Published library content with project-scoped structured lineage projections."""
from copy import deepcopy
from fastapi import HTTPException
from backend.flow import library, workflows
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import FlowNotFound, FlowConflict
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.canvas_capabilities.contracts import contract

CONTRACTS = {
    "library_routes.library_list": contract(optional=("owner",), output="Native shared library folders; lineage/counts scoped to this project"),
    "library_routes.flow_detail": contract(("workflow_id",), output="Full native published graph/versions with scoped structured lineage"),
    "library_routes.flow_brief": contract(("workflow_id",), ("version",), types={"version": "integer"}),
}


def _visible(db, project, identifier):
    row = workflows.workflow_of(db, workflow_id=identifier)
    return row is not None and (row["project_id"] == project or
        (row["project_id"] is None and row["kind"] == "library_flow" and workflows.LIBRARY_OWNER.fullmatch(row["owner_ref"] or "")))


def _source(db, project, value):
    return deepcopy(value) if value and _visible(db, project, value["workflowId"]) else None


def _meta(project, value):
    result = deepcopy(value)
    if result:
        for key in ("learnedFrom", "proposedBy"):
            if isinstance(result.get(key), dict) and result[key].get("project") not in (None, project):
                result.pop(key)
    return result


def _summary(db, project, item):
    result = deepcopy(item)
    result["derivedFrom"] = _source(db, project, result.get("derivedFrom"))
    if result.get("learnedFrom") and result["learnedFrom"].get("project") != project:
        result["learnedFrom"] = None
    derived = [row for row in library._derived(db, item["id"]) if _visible(db, project, row["workflowId"])]
    result["derivedCount"] = len(derived)
    if "derived" in result:
        result["derived"] = derived
        result["projects"] = sorted({row["projectId"] for row in derived if row["projectId"]})
    if "versions" in result:
        result["versions"] = [{**version, "derived_from": _source(db, project, version.get("derived_from")),
                                "meta": _meta(project, version.get("meta"))} for version in result["versions"]]
    return result


def read(service, project, capability, data):
    try:
        with service.registry_lock:
            db = service.db
            if capability == "library_routes.library_list":
                from backend.flow.library_operations import folder_digest
                part = data.get("owner", "human")
                # The native reader validates the actual owner enum.
                return {"owner": part, "lineageScope": project,
                        "folders": [{**folder, "revisionDigest": folder_digest(folder), "flows": [_summary(db, project, item) for item in folder["flows"]]}
                                    for folder in library.list_library(db, part)]}
            identifier = data["workflow_id"]
            if not _visible(db, project, identifier):
                raise GateError(403, "gate_scope", "Workflow belongs to another scope.", "Use own or published library workflow.")
            if capability == "library_routes.flow_detail":
                return {**_summary(db, project, library.flow_detail(db, identifier)), "lineageScope": project}
            if capability == "library_routes.flow_brief":
                version = data.get("version")
                if version is not None and version < 1:
                    raise FlowInvalid("version must be positive")
                return library.flow_brief(db, identifier, version)
    except FlowNotFound as error:
        raise HTTPException(404, str(error)) from error
    except FlowConflict as error:
        raise HTTPException(409, str(error)) from error
    except FlowInvalid as error:
        raise HTTPException(422, str(error)) from error
    raise RuntimeError("Unknown finite library read")
