"""Accepted equipment preview bound to negotiated context, without execution authority."""
import re
from copy import deepcopy

from backend.canvas import opora_execution_handoff as handoff
from backend.canvas.graph import digest
from backend.canvas.opora_execution_context import collect
from backend.canvas.opora_execution_code_context import attach as attach_code_context
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from backend.library.harness_kit import kit_of_assignment


def preview(canvas, payload):
    project, workspace = validate(payload, {"nodeId", "expectedAcceptedHead", "expectedContextVersion"})
    for key, length in (("expectedAcceptedHead", 40), ("expectedContextVersion", 64)):
        if not isinstance(payload[key], str) or not re.fullmatch(rf"[a-f0-9]{{{length}}}", payload[key]):
            raise ValueError("Preflight requires exact negotiated context identities.")
    # Reuse capture and lock ordering; never create a claim, pin, epoch or worker.
    with OporaExecutions(canvas).transaction(project, workspace) as repo:
        assignment, pin = collect(canvas, repo.db, project, workspace, payload["nodeId"])
        if (assignment["acceptedRevision"] != payload["expectedAcceptedHead"]
                or assignment["contextVersion"] != payload["expectedContextVersion"]):
            raise ValueError("Accepted context changed; negotiate again before preparation.")
        assignment = handoff.attach(assignment, None, handoff.handoff_for(canvas, repo.db, project, workspace, payload["nodeId"]))
        # OP-B171BE.preflight: claim includes observed code and resume lineage; this pin remains in memory only.
        assignment = attach_code_context(canvas, repo, payload["nodeId"], assignment, pin)
        kit = kit_of_assignment(assignment, payload["nodeId"])
        return {"schema": "harness.preflight/1", "scope": {"project": project, "workspace": workspace,
                "nodeId": payload["nodeId"]}, "contextProtocolVersion": 2,
                "acceptedHead": assignment["acceptedRevision"], "contextVersion": assignment["contextVersion"],
                "assignmentDigest": digest(assignment), "kit": deepcopy(kit),
                "kitDigest": digest(kit) if kit is not None else None,
                "evidence": "accepted-context-preview", "executionAuthority": False,
                "runnerReadinessVerified": False, "permissionsGranted": False}
