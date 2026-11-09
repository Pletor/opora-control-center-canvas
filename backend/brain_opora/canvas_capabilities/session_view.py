"""Private persisted navigation intent. A saved intent is not an applied browser camera."""
import json
import math

from backend.canvas.operation_receipts import Receipt
from backend.canvas.payload_errors import InvalidPayload, NextStep


def read(service, project, workspace, session):
    with service.reading(project):
        row = service.db_for(project).execute("SELECT revision,state FROM canvas_session_views WHERE "
            "project_id=? AND workspace_id=? AND session_id=?", (project, workspace, session["id"])).fetchone()
        revision = row[0] if row else 0
        view = json.loads(row[1]) if row else {"selection": [], "viewport": None, "filter": ""}
        from backend.brain_opora.canvas_capabilities.view_attachments import status
        observed = status(service, project, workspace, session["id"], revision, view)
    return {"sessionId": session["id"], "revision": revision, "view": view, **observed}


def update(service, project, workspace, session, data, request_id):
    revision, view = data["expectedRevision"], data["view"]
    required = {"selection", "viewport", "filter"}
    if (type(revision) is not int or revision < 0 or not isinstance(view, dict)
            or required - view.keys() or view.keys() - required - {"structureCollapsed"}):
        raise InvalidPayload("Expected nonnegative revision and selection,viewport,filter view.")
    if "structureCollapsed" in view:
        groups = view["structureCollapsed"]
        if (not isinstance(groups, list) or any(not isinstance(group, str) or group not in {"sectors", "nodes", "areas"} for group in groups)
                or len(groups) != len(set(groups))):
            raise InvalidPayload("structureCollapsed must contain unique sectors,nodes,areas groups.")
    selected = view["selection"]
    if not isinstance(selected, list) or len(selected) > 1000 or any(not isinstance(n, str) for n in selected) or len(set(selected)) != len(selected):
        raise InvalidPayload("Selection must contain unique node identifiers.")
    if not isinstance(view["filter"], str) or len(view["filter"]) > 1000:
        raise InvalidPayload("Filter must be text up to 1000 characters.")
    camera = view["viewport"]
    if camera is not None and (not isinstance(camera, dict) or set(camera) != {"x", "y", "zoom"}
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in camera.values())
        or not 0.01 <= camera["zoom"] <= 10):
        raise InvalidPayload("Viewport must contain finite x,y and zoom in 0.01..10.")
    payload = {"project": project, "workspace": workspace, "operationId": request_id, **data}
    receipt = Receipt(payload, "session-view:" + session["id"], {"sessionId": session["id"]})
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        with db:
            db.execute("BEGIN IMMEDIATE")
            prior = receipt.replay(db)
            if prior is not None:
                return prior
            actual = read(service, project, workspace, session)
            if actual["revision"] != revision:
                raise NextStep("Session view revision changed.", code="session_view_conflict", hint="Read this session view again.")
            known = {n["id"] for n in service.view(project, workspace)["graph"]["nodes"]}
            if not set(selected) <= known:
                raise InvalidPayload("Selected node must belong to this scoped live Canvas.")
            db.execute("INSERT INTO canvas_session_views VALUES(?,?,?,?,?) ON CONFLICT(project_id,workspace_id,session_id) "
                       "DO UPDATE SET revision=excluded.revision,state=excluded.state",
                       (project, workspace, session["id"], revision + 1, json.dumps(view)))
            saved = read(service, project, workspace, session)
            if saved["revision"] != revision + 1 or saved["view"] != view:
                raise RuntimeError("Session intent readback mismatch.")
            receipt.begin(db)
            receipt.complete(db, saved)
            return saved
