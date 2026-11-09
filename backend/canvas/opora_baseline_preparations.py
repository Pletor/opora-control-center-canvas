"""Immutable baseline review intent; only the existing human endpoint accepts it."""
import json
from urllib.parse import urlencode

from backend.canvas.operation_receipts import Receipt
from backend.canvas.opora_change_validation import subject
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.payload_errors import NextStep

KIND = "opora_changeset_routes.baseline"


def read(service, project, workspace, identifier):
    service.view(project, workspace)
    with service.reading(project):
        row = service.db_for(project).execute(
            "SELECT status,response FROM canvas_operation_receipts WHERE project_id=? AND workspace_id=? "
            "AND operation_kind=? AND operation_id=?", (project, workspace, KIND, identifier)).fetchone()
        if row is None or row[0] != "complete":
            raise NextStep("Stored baseline preparation is unavailable.", code="baseline_preparation_missing",
                           hint="Read the exact scoped preparation before human review.")
        return json.loads(row[1])


def prepare(service, project, workspace, session, data, request_id):
    payload = {"project": project, "workspace": workspace, **data}
    by = {"kind": "agent", "name": session["worker_name"]}
    receipt = Receipt({**payload, "operationId": request_id}, KIND, by)
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        replay = receipt.replay(db)
        if replay is not None:
            return replay
        current = OporaChangesets(service).context(project, workspace)
        if (current["readOnly"] or current["acceptedHead"] is not None or data["expectedAcceptedHead"] is not None
                or not current["documents"] or current["graphDigest"] != data["expectedGraphDigest"]
                or current["specificationsVersion"] != data["expectedSpecificationsVersion"]):
            raise NextStep("Baseline preparation requires the exact current unaccepted specifications.",
                           code="baseline_preparation_conflict", hint="Read native changeset context and prepare a new intent.")
        subject(payload)
        result = {"operationId": request_id, "payload": payload, "documents": current["documents"], "by": by}
        query = {"screen": "canvas", "environment": "hub", "project": project, "workspace": workspace,
                 "ohBaseline": request_id}
        response = {"state": "awaiting_human", "verified": True, "reviewUrl": "/?" + urlencode(query), "result": result}
        with db:
            receipt.begin(db)
            receipt.complete(db, response)
        if read(service, project, workspace, request_id) != response:
            raise NextStep("Baseline preparation readback differs.", code="operation_incomplete", hint="Read the existing receipt.")
        return response
