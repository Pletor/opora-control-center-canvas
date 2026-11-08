"""Office feedback opens a research branch; native tickets remain delivery authority."""
import hashlib
import json

from backend.brain_opora.determinism import ticket
from backend.editor.research import model, service as research
from database.repositories.gate_sessions import GateSessionStore


def branch_id(project, workspace, ticket_id, feedback_id):
    key = json.dumps([project, workspace, ticket_id, feedback_id])
    return "rc_ticket_" + hashlib.sha256(key.encode()).hexdigest()[:32]


def origin(service, project, workspace, ticket_id, feedback_id):
    for value in (project, workspace, ticket_id, feedback_id):
        model.identifier(value)
    found = ticket.get(service, project, ticket_id)
    if found["workspaceId"] != workspace:
        model.fail("Ticket belongs to another workspace.", 403, "gate_scope")
    feedback = next((f for f in found["feedback"] if f["feedbackId"] == feedback_id), None)
    if feedback is None:
        model.fail("Feedback does not belong to this ticket.", 404, "feedback_not_found")
    with service.reading(project):
        db = service.db_for(project)
        session = GateSessionStore(db).get(feedback["sessionId"])
        execution_id = found["machine"]["executionId"]
        if execution_id:
            execution = db.execute("SELECT workspace_id,node_id FROM opora_executions WHERE project_id=? AND id=?",
                                   (project, execution_id)).fetchone()
            if not execution or tuple(execution) != (workspace, found["machine"]["cardId"]):
                model.fail("Ticket execution does not belong to this task and workspace.", 409, "research_origin")
    if not session or session["project_id"] != project or session["workspace_id"] != workspace:
        model.fail("Feedback session does not belong to this scope.", 409, "research_origin")
    return found, feedback


def provenance(project, workspace, found, feedback):
    return {"project": project, "workspace": workspace, "ticketId": found["ticketId"],
            "feedbackId": feedback["feedbackId"], "sessionId": feedback["sessionId"],
            **{key: found["machine"][key] for key in ("cardId", "cardVersion", "executionId")},
            "problem": feedback["text"], "createdAt": feedback["createdAt"]}


def open_branch(service, payload, actor, agent=""):
    if actor not in ("human", "agent"):
        model.fail("Research bridge requires human or heart authority.", 403, "research_writer")
    model.shape(payload, {"project", "workspace", "ticketId", "feedbackId"})
    project, workspace = payload["project"], payload["workspace"]
    with service.graph_lock_for(project):
        found, feedback = origin(service, **_origin_args(payload))
        ident = branch_id(project, workspace, found["ticketId"], feedback["feedbackId"])
        # OP-6FF3AC: retry returns the original immutable origin, even after task archival.
        try:
            prior = research.detail(service, project, workspace, ident, 1)["card"]
        except model.GateError as error:
            if error.code != "research_not_found":
                raise
        else:
            try:
                stored = json.loads(prior["content"])
            except (ValueError, TypeError):
                model.fail("Branch identity already occupied.", 409, "research_conflict")
            if not isinstance(stored, dict) or stored.get("ticketOrigin") != provenance(project, workspace, found, feedback):
                model.fail("Branch identity already occupied.", 409, "research_conflict")
            return {"card": prior, "origin": stored["ticketOrigin"], "workspace": workspace}
        task = found["machine"]["cardId"]
        graph = service.view(project, workspace)["graph"]
        if not task or not any(node["id"] == task for node in graph["nodes"]):
            model.fail("Ticket task is absent from this workspace.", 409, "research_origin")
        source = provenance(project, workspace, found, feedback)
        refs = {key: [] for key in model.REFS}
        refs.update(nodeIds=[task], ticketIds=[found["ticketId"]], sessionIds=[feedback["sessionId"]])
        op = {"op": "card", "id": ident, "expectedRevision": 0, "kind": "question",
              "title": "Problém z Kanceláře", "summary": "Ověřit vrácený problém před pokračováním úkolu.",
              "topicPath": ["Kancelář", task], "content": json.dumps({"ticketOrigin": source}, ensure_ascii=False),
              "status": "open", "verification": {"status": "unverified", "method": "", "at": ""},
              "sources": [], "refs": refs}
        result = research.apply(service, {"project": project, "workspace": workspace,
                                          "key": ident, "operations": [op]}, actor, agent)
        return {"card": result["cards"][0], "origin": source, "workspace": workspace}


def _origin_args(payload):
    return {"project": payload["project"], "workspace": payload["workspace"],
            "ticket_id": payload["ticketId"], "feedback_id": payload["feedbackId"]}


def answer(service, payload, actor, agent=""):
    if actor not in ("human", "agent"):
        model.fail("Research bridge requires human or heart authority.", 403, "research_writer")
    model.shape(payload, {"project", "workspace", "ticketId", "feedbackId", "cardId", "revision", "text"})
    if type(payload["revision"]) is not int or payload["revision"] < 1:
        model.fail("Answer must pin a positive research revision.")
    model.text(payload["text"], "text", 10000, False)
    project, workspace = payload["project"], payload["workspace"]
    with service.graph_lock_for(project), service.lock_for(project):
        found, feedback = origin(service, **_origin_args(payload))
        ident = branch_id(project, workspace, found["ticketId"], feedback["feedbackId"])
        branch = research.detail(service, project, workspace, ident, 1)["card"]
        try:
            source = json.loads(branch["content"])["ticketOrigin"]
        except (ValueError, TypeError, KeyError):
            model.fail("Invalid branch origin.", 409, "research_origin")
        if source != provenance(project, workspace, found, feedback):
            model.fail("Branch origin no longer matches the ticket.", 409, "research_origin")
        card = research.detail(service, project, workspace, payload["cardId"], payload["revision"])["card"]
        text = payload["text"].strip() + "\n\n" + json.dumps({"researchAnswer": {
            "cardId": card["id"], "revision": card["revision"], "branchId": ident,
            "branchRevision": 1, "origin": source}}, ensure_ascii=False, sort_keys=True)
        if feedback["answer"] is not None:
            if feedback["answer"] != {"text": text}:
                model.fail("Feedback already has a different answer.", 409, "feedback_answered")
            return {"feedback": feedback, "ticket": {"ticketId": found["ticketId"], "status": found["status"]},
                    "sessionId": source["sessionId"], "replayed": True}
        edges = research.detail(service, project, workspace, card["id"])["edges"]
        if not any(e["fromId"] == card["id"] and e["toId"] == ident and e["relation"] == "resolves"
                   and not e["archived"] and e["resolved"].strip() and e["missing"].strip() for e in edges):
            model.fail("Answer requires a resolves edge stating what is resolved and what remains missing.",
                       409, "research_reference")
        if found["sessionId"] != source["sessionId"]:
            model.fail("Original session no longer holds the ticket.", 409, "research_holder_changed")
        result = ticket.answer(service, {"project_id": project, "workspace_id": workspace, "role": "heart"},
                               {"ticketId": found["ticketId"], "feedbackId": feedback["feedbackId"], "text": text})
        return {**result, "sessionId": source["sessionId"], "replayed": False}
