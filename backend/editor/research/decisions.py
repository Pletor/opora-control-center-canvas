"""Immutable human review of a research path, pinned to complete evidence revisions."""
import hashlib
import json
from datetime import UTC, datetime

from backend.editor.research import model
from backend.editor.research import service as research


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def listing(service, project, workspace, decision_id):
    service.view(project, workspace)
    model.identifier(decision_id)
    with service.lock_for(project):
        rows = service.db_for(project).execute(
            "SELECT payload FROM research_decision_reviews WHERE project_id=? AND workspace_id=? AND decision_id=? ORDER BY decision_revision",
            (project, workspace, decision_id))
        return {"reviews": [json.loads(row[0]) for row in rows]}


def read(service, project, workspace, review_id):
    service.view(project, workspace)
    model.identifier(review_id)
    row = service.db_for(project).execute(
        "SELECT payload FROM research_decision_reviews WHERE project_id=? AND workspace_id=? AND id=?",
        (project, workspace, review_id)).fetchone()
    if row is None:
        model.fail("Decision review does not exist in this workspace.", 404, "research_review_missing")
    return json.loads(row[0])


def validated_snapshot(service, project, workspace, payload):
    model.shape(payload, {"decisionId", "decisionRevision", "problemId", "evidence", "rationale", "assumptions", "constraints"})
    if type(payload["decisionRevision"]) is not int or payload["decisionRevision"] < 1:
        model.fail("Decision revision must be a positive integer.")
    for key in ("rationale", "assumptions", "constraints"):
        model.text(payload[key], key, 8000, key != "rationale")
    evidence = payload["evidence"]
    if not isinstance(evidence, list) or not evidence:
        model.fail("Review requires pinned evidence.")
    decision = research.detail(service, project, workspace, payload["decisionId"])["card"]
    if decision["kind"] != "decision" or decision["revision"] != payload["decisionRevision"] or decision["archived"]:
        model.fail("Review the current unarchived decision revision.", 409)
    problem = research.detail(service, project, workspace, payload["problemId"])["card"]
    if problem["kind"] != "question":
        model.fail("The original problem must be a question card.")
    pinned, seen = [], set()
    for ref in evidence:
        model.shape(ref, {"id", "revision"})
        if type(ref["revision"]) is not int or ref["revision"] < 1:
            model.fail("Every evidence reference must pin a positive integer revision.")
        if ref["id"] in seen:
            model.fail("Duplicate evidence.")
        seen.add(ref["id"])
        item = research.detail(service, project, workspace, ref["id"], ref["revision"])["card"]
        if item["verification"]["status"] not in ("verified", "observed") or not item["sources"]:
            model.fail("Decision evidence must be verified or observed with source records.")
        # Keep contradictions in the immutable evidence, but never count them as support.
        # Older sources inherit the card's verification; explicit source status takes priority.
        supporting = [source for source in item["sources"]
                      if "verification" not in source
                      or source["verification"]["status"] in ("verified", "observed")]
        if not any(source.get("quote", "").strip() for source in supporting):
            model.fail("Decision evidence needs a concrete verified or observed source passage.")
        pinned.append(item)
    body = {"decision": decision, "problem": problem, "evidence": pinned,
            **{key: payload[key] for key in ("rationale", "assumptions", "constraints")}}
    return body


def persist_review(service, project, workspace, body):
    """Caller owns the SQL transaction; pending proposal acceptance can commit both records together."""
    rid = "rr_" + digest(body)[:32]
    db = service.db_for(project)
    prior = db.execute("SELECT payload FROM research_decision_reviews WHERE project_id=? AND workspace_id=? AND decision_id=? AND decision_revision=?",
                       (project, workspace, body["decision"]["id"], body["decision"]["revision"])).fetchone()
    if prior:
        value = json.loads(prior[0])
        if value["id"] != rid:
            model.fail("This decision revision already has a different review.", 409)
        return value
    result = {"id": rid, "project": project, "workspace": workspace, "by": "human",
              "reviewedAt": datetime.now(UTC).isoformat(), **body}
    db.execute("INSERT INTO research_decision_reviews VALUES(?,?,?,?,?,?)",
                   (project, workspace, rid, body["decision"]["id"], body["decision"]["revision"], encoded(result)))
    return result


def review(service, project, workspace, payload, actor):
    if actor != "human":
        model.fail("A human must explicitly review the decision path.", 403, "research_review_human")
    with service.graph_lock_for(project), service.lock_for(project), service.db_for(project):
        return persist_review(service, project, workspace, validated_snapshot(service, project, workspace, payload))
