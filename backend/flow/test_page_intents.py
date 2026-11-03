import json

import pytest

from backend.flow.conftest import edge, node
from backend.flow.graph_check import FlowInvalid
from backend.flow.page_intents import current_digest, intent_claims, owner_of, page_digest, pages_of, status
from backend.flow.workflows import approve, create_draft, create_workflow, set_candidate

DONE = node("ok", "intent.done", params={"claim": "formulář odešel e-mail", "check": "email"})
INTENT = {"nodes": [node("in", "intent.entry"), DONE], "edges": [edge("1", "in", "ok")]}
SITE = {"kind": "page", "path": "/kontakt", "goal": "Spojit se", "sections": [{"id": "form"}]}


def page(pid, **site):
    return {"id": pid, "site": {**SITE, **site}}


def candidate(db, wid, graph=INTENT):
    return set_candidate(db, create_draft(db, wid, graph)["id"])


@pytest.fixture
def project(db):
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    return db


def test_digest_covers_only_the_intent_fields_and_is_canonical():
    assert page_digest(SITE) == page_digest({"sections": [{"id": "form"}], "goal": "Spojit se", "path": "/kontakt",
                                             "kind": "page", "navLabel": "Kontakt", "seo": {"x": "y"}})
    assert page_digest(SITE) != page_digest({**SITE, "feel": "klidná"})
    graph = {"nodes": [page("a"), {"id": "b", "site": {"kind": "application"}}, {"id": "c"}]}
    assert [p["id"] for p in pages_of(graph)] == ["a"]
    assert current_digest(graph, "a") == page_digest(SITE) and current_digest(graph, "b") is None


def test_status_none_pending_approved_and_stale(project):
    db = project
    wid = create_workflow(db, "page_intent", "Záměr", project_id="p", owner_ref="opora:page:a")["id"]
    assert status(db, "p", [page("a"), page("b")]) == [
        {"pageId": "a", "state": "none", "workflowId": wid, "doneCount": 0},
        {"pageId": "b", "state": "none", "doneCount": 0}]
    v1 = candidate(db, wid)
    assert status(db, "p", [page("a")]) == [
        {"pageId": "a", "state": "pending", "workflowId": wid, "candidateN": 1, "doneCount": 1}]
    assert owner_of(db, v1["id"]) == ("p", "a")
    approve(db, v1["id"], "human", page_digest(SITE))
    logged = json.loads(db.execute("SELECT payload FROM flow_log_events WHERE type='version.approved'").fetchone()[0])
    assert logged["pageDigest"] == page_digest(SITE)
    assert status(db, "p", [page("a")])[0] == {"pageId": "a", "state": "approved", "workflowId": wid, "activeN": 1,
                                               "doneCount": 1}
    assert status(db, "p", [page("a", goal="Jiný cíl")])[0]["state"] == "stale"
    v2 = candidate(db, wid, {"nodes": [*INTENT["nodes"], node("ok2", "intent.done")], "edges": INTENT["edges"]})
    assert status(db, "p", [page("a", goal="Jiný cíl")])[0] == {
        "pageId": "a", "state": "pending", "workflowId": wid, "activeN": 1, "candidateN": v2["n"], "doneCount": 1}
    assert status(db, "jiny", [page("a")])[0]["state"] == "none"  # záměr patří jen svému projektu


def test_intent_claims_only_from_the_active_version_and_done_nodes(project):
    db = project
    wid = create_workflow(db, "page_intent", "Záměr", project_id="p", owner_ref="opora:page:a")["id"]
    v1 = candidate(db, wid)
    with pytest.raises(FlowInvalid, match="aktivní"):
        intent_claims(db, "p", v1["id"], ["ok"])
    approve(db, v1["id"], "human", None)
    assert intent_claims(db, "p", v1["id"], ["ok"]) == ["formulář odešel e-mail"]
    with pytest.raises(FlowInvalid, match="intent.done"):
        intent_claims(db, "p", v1["id"], ["in"])
    with pytest.raises(FlowInvalid, match="projektu"):
        intent_claims(db, "jiny", v1["id"], ["ok"])
    heart = create_workflow(db, "heart", "Srdce")
    assert owner_of(db, create_draft(db, heart["id"], {"nodes": [node("t", "trigger.manual")], "edges": []})["id"]) is None
