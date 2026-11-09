"""Pinned review preparation; only an authenticated human can create the native decision review."""
import json
from datetime import UTC, datetime

from backend.editor.research import decisions, model
from backend.editor.research import service as research


def read(service, project, workspace, identifier):
    service.view(project, workspace)
    model.identifier(identifier)
    row = service.db_for(project).execute(
        "SELECT payload FROM research_review_proposals WHERE project_id=? AND workspace_id=? AND id=?",
        (project, workspace, identifier)).fetchone()
    if row is None:
        model.fail("Review proposal does not exist in this scope.", 404, "research_review_proposal_missing")
    return json.loads(row[0])


def listing(service, project, workspace, decision_id):
    service.view(project, workspace)
    model.identifier(decision_id)
    rows = service.db_for(project).execute(
        "SELECT payload FROM research_review_proposals WHERE project_id=? AND workspace_id=? AND decision_id=? ORDER BY rowid",
        (project, workspace, decision_id))
    return {"items": [json.loads(row[0]) for row in rows]}


def current_sources(service, project, workspace, snapshot):
    for card in [snapshot["decision"], snapshot["problem"], *snapshot["evidence"]]:
        current = research.detail(service, project, workspace, card["id"])["card"]
        if current != card or current["archived"]:
            model.fail("A proposal source changed. Prepare a new review and inspect the changes.", 409, "research_review_proposal_stale")


def prepare(service, project, workspace, payload, request_id, actor, name):
    if actor not in ("agent", "human"):
        model.fail("Review preparation requires scoped authority.", 403)
    model.text(request_id, "requestId", 160, False)
    request = decisions.encoded({"review": payload, "by": {"kind": actor, "name": name}})
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        prior = db.execute("SELECT request_json,payload FROM research_review_proposals WHERE project_id=? AND workspace_id=? AND request_id=?",
                           (project, workspace, request_id)).fetchone()
        if prior:
            if prior[0] != request:
                model.fail("Request ID already belongs to another review preparation.", 409, "operation_conflict")
            return json.loads(prior[1])
        if service.view(project, workspace)["readOnly"]:
            model.fail("Cannot prepare a review in a read-only workspace.", 409)
        snapshot = decisions.validated_snapshot(service, project, workspace, payload)
        current_sources(service, project, workspace, snapshot)
        identifier = "rp_" + decisions.digest([project, workspace, request_id])[:32]
        result = {"id": identifier, "project": project, "workspace": workspace, "status": "pending",
                  "by": {"kind": actor, "name": name}, "createdAt": datetime.now(UTC).isoformat(),
                  "review": payload, "snapshot": snapshot, "digest": decisions.digest(snapshot), "result": None}
        with db:
            db.execute("INSERT INTO research_review_proposals VALUES(?,?,?,?,?,?,?)",
                       (project, workspace, identifier, request_id, request, payload["decisionId"], decisions.encoded(result)))
        return read(service, project, workspace, identifier)


def decide(service, project, workspace, identifier, digest, action, actor):
    if actor != "human":
        model.fail("A human must review or reject this preparation.", 403, "research_review_human")
    if action not in ("accept", "reject"):
        model.fail("Unknown review proposal action.")
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        with db:
            db.execute("BEGIN IMMEDIATE")
            proposal = read(service, project, workspace, identifier)
            if digest != proposal["digest"]:
                model.fail("Review the exact prepared content.", 409, "research_review_proposal_stale")
            status = "accepted" if action == "accept" else "rejected"
            if proposal["status"] == status:
                return proposal
            if proposal["status"] != "pending":
                model.fail("This review preparation already has a human decision.", 409)
            if service.view(project, workspace)["readOnly"]:
                model.fail("Cannot decide in a read-only workspace.", 409)
            result = None
            if action == "accept":
                current_sources(service, project, workspace, proposal["snapshot"])
                actual = decisions.validated_snapshot(service, project, workspace, proposal["review"])
                if actual != proposal["snapshot"]:
                    model.fail("Review preimage differs from its immutable preparation.", 409)
                result = decisions.persist_review(service, project, workspace, actual)
            proposal = {**proposal, "status": status, "result": result, "decidedAt": datetime.now(UTC).isoformat(), "decidedBy": "human"}
            db.execute("UPDATE research_review_proposals SET payload=? WHERE project_id=? AND workspace_id=? AND id=?",
                       (decisions.encoded(proposal), project, workspace, identifier))
            return proposal
