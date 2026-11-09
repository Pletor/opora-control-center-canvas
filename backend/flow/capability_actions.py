"""Native writes with scoped receipts; interrupted external execution is never repeated blindly."""
import json
import uuid

from backend.flow.inputs import CandidateIn, CanvasLogIn, RunIn
from backend.flow.review import owned, prepared
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.canvas.payload_errors import NextStep
from backend.canvas.operation_receipts import Receipt
from backend.flow import interpreter, review, workflows
from backend.flow.canvas_log import log_canvas


def write(service, project, workspace, session, operation, data, request_id):
    with service.graph_lock_for(project), service.lock_for(project):
        receipt = Receipt({"project": project, "workspace": workspace, **data, "operationId": request_id},
                          "flow_routes." + operation, {"kind": "agent", "name": session["worker_name"]})
        db = service.db_for(project)
        replay = receipt.replay(db)
        if replay is not None:
            return replay
        return _write(service, project, workspace, session, operation, data, request_id, receipt)


def _write(service, project, workspace, session, operation, data, request_id, receipt):
    native_id = uuid.uuid5(uuid.NAMESPACE_URL, json.dumps([project, workspace, session["worker_name"], operation, request_id])).hex
    is_log = operation == "canvas_log_create"
    run_operation = operation in ("run_manual", "run_advance")
    ids = {key: data[key] for key in ("workflow_id", "version_id", "run_id") if key in data}
    body = (CanvasLogIn.model_validate({**data, "project": project}) if is_log else
            RunIn.model_validate(data) if operation == "run_manual" else
            CandidateIn.model_validate(data) if operation == "version_candidate" else None)

    def snapshot():
        with service.registry_lock:
            db = service.db
            if is_log:
                return [dict(row) for row in db.execute("SELECT * FROM flow_log_events WHERE json_extract(payload,'$.project')=? AND run_id IS NULL ORDER BY seq", (project,))]
            workflow, _ = owned(db, project, **ids)
            if run_operation:
                runs = interpreter.list_runs(db, workflow["id"], 1000000)
                return [interpreter.get_run(db, item["id"]) for item in runs]
            return workflows.list_versions(db, workflow["id"])

    # Shared human Library remains human-owned. Preparation makes no transition.
    if not is_log:
        with service.registry_lock:
            _, part = owned(service.db, project, **ids)
            if part == "human" and not run_operation:
                identifier = data.get("version_id", data.get("workflow_id"))
                review.check(service.db, operation, identifier, data.get("expectedReviewDigest"))
                response = prepared(project, workspace, review.observe(service.db, operation, identifier, project))
                db = service.db_for(project)
                with db:
                    receipt.begin(db, {"review": response["result"]})
                    receipt.complete(db, response)
                return response

    def action():
        if is_log:
            return log_canvas(service, project, body.canvas, body.kind, body.payload, "heart")
        with service.registry_lock:
            db = service.db
            owned(db, project, **ids)
            identifier = data.get("version_id", data.get("workflow_id"))
            if not run_operation:
                review.check(db, operation, identifier, data.get("expectedReviewDigest"))
            if operation == "version_candidate":
                if body.eval_run_id:
                    workflow, _ = owned(db, project, run_id=body.eval_run_id)
                    target, _ = owned(db, project, version_id=identifier)
                    if workflow["id"] != target["id"]:
                        raise workflows.FlowConflict("Evaluation run belongs to another workflow.")
                return workflows.set_candidate(db, identifier, body.eval_run_id)
            if operation == "version_activate":
                return workflows.activate(db, identifier)
            if operation == "version_rollback":
                return workflows.rollback(db, identifier)
            if operation == "run_manual":
                return interpreter.start_run(db, identifier, {"source": "manual", "payload": body.payload, "node_id": body.node_id}, run_id=native_id)
            if operation == "run_advance":
                return interpreter.advance(db, data["run_id"])
        raise RuntimeError("Unknown finite flow mutation")

    def verify(before, after, result):
        key = "seq" if is_log else "id"
        found = next((item for item in after if item[key] == result[key]), None)
        valid = found == result
        if is_log and found:
            payload = {**body.payload, "project": project, "author": "heart"}
            valid = found["type"] == body.kind and found["canvas"] == body.canvas and json.loads(found["payload"]) == payload
            if valid and body.kind.endswith(".failed"):
                expected = {"seq": result["seq"], "canvas": body.canvas, "kind": body.kind, "payload": body.payload}
                events = service.db_for(project).execute("SELECT data FROM opora_events WHERE project_id=? AND kind='canvas.failed' AND json_extract(data,'$.seq')=?", (project, result["seq"])).fetchall()
                valid = len(events) == 1 and json.loads(events[0][0]) == expected
        if not valid:
            raise NextStep("Native workflow readback differs from the write.", code="operation_incomplete", hint="Inspect the native version/run/log before retrying; no automatic duplicate execution.")

    return run(service, project, workspace, session, "flow_routes." + operation, data, request_id,
               snapshot=snapshot, action=action, verify=verify)
