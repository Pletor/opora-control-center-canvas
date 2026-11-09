"""Real auth, immutable proposal replay, source CAS and atomic native review acceptance."""
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.api.brain_opora.test_canvas_capability_routes import SCOPE, call
from backend.api.brain_opora.test_canvas_capability_routes import setup as capability_setup
from backend.canvas.canvas_plan import apply_plan
from backend.editor.node.test_removals import HEADERS
from backend.editor.research import decisions, model
from backend.editor.research import service as research
from backend.editor.research.test_decision_tasks import setup as seed_review

setup = capability_setup
BASE = "/api/research/review-proposals"


def seed(service):
    apply_plan(service, {**SCOPE, "digest": service.view("draft", "draft")["digest"],
                        "plan": {"nodes": [{"ref": "seed", "kind": "node", "name": "Seed"}]}})
    return seed_review(service)


def prepare(client, auth, review, key="prepare"):
    response = client.post(BASE, headers=auth, json={**SCOPE, "review": review, "requestId": key})
    assert response.status_code == 200, response.text
    return response.json()


def decide(client, proposal, action="accept", headers=HEADERS):
    return client.post(f"{BASE}/{proposal['id']}/{action}", headers=headers, json={**SCOPE, "digest": proposal["digest"]})


def test_prepare_is_not_review_and_only_real_human_can_accept(setup):
    client, service, auth = setup
    review = seed(service)
    graph = service.view("draft", "draft")["graph"]
    proposal = prepare(client, auth, review)
    assert proposal["status"] == "pending" and proposal["result"] is None
    assert decisions.listing(service, "draft", "draft", "rc_decision")["reviews"] == []
    assert decide(client, proposal, headers=auth).status_code == 403
    assert decide(client, proposal, headers={"X-Opora-Actor": "human"}).status_code in (403, 428)
    assert client.get(f"{BASE}/{proposal['id']}", params={**SCOPE, "project": "foreign"}, headers=auth).status_code == 403
    accepted = decide(client, proposal)
    assert accepted.status_code == 200, accepted.text
    result = accepted.json()
    assert result["status"] == "accepted" and result["result"]["by"] == "human"
    assert result["result"] == decisions.read(service, "draft", "draft", result["result"]["id"])
    assert decide(client, proposal).json() == result
    assert decide(client, proposal, "reject").status_code == 409
    assert service.view("draft", "draft")["graph"] == graph


@pytest.mark.parametrize("changed", ["rc_decision", "rc_problem", "rc_fact"])
def test_source_preimages_stale_and_prepare_replay_remains_original(setup, changed):
    client, service, auth = setup
    review = seed(service)
    proposal = prepare(client, auth, review)
    original = research.detail(service, "draft", "draft", changed)["card"]
    update = {key: original[key] for key in model.CARD}
    research.apply(service, {**SCOPE, "key": "change", "operations": [
        {"op": "card", "id": changed, "expectedRevision": 1, **update, "content": "New source content"}]}, "human")
    assert prepare(client, auth, review) == proposal
    stale = decide(client, proposal)
    assert stale.status_code == 409 and stale.json()["code"] == "research_review_proposal_stale", stale.text
    assert decisions.listing(service, "draft", "draft", "rc_decision")["reviews"] == []
    rejected = decide(client, proposal, "reject")
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert decide(client, proposal).status_code == 409


def test_review_insert_failure_rolls_back_both_records(setup, monkeypatch):
    client, service, auth = setup
    proposal = prepare(client, auth, seed(service))
    original = decisions.persist_review
    def interrupted(*args):
        original(*args)
        model.fail("Injected failure after native review insert", 409)
    monkeypatch.setattr(decisions, "persist_review", interrupted)
    assert decide(client, proposal).status_code == 409
    assert decisions.listing(service, "draft", "draft", "rc_decision")["reviews"] == []
    assert client.get(f"{BASE}/{proposal['id']}", params=SCOPE, headers=auth).json()["status"] == "pending"
    monkeypatch.setattr(decisions, "persist_review", original)
    assert decide(client, proposal).status_code == 200


def test_key_conflict_source_scope_and_capability_preparation(setup):
    client, service, auth = setup
    review = seed(service)
    proposal = prepare(client, auth, review)
    conflict = client.post(BASE, headers=auth, json={**SCOPE, "review": {**review, "rationale": "Changed"}, "requestId": "prepare"})
    assert conflict.status_code == 409
    missing = client.post(BASE, headers=auth, json={**SCOPE, "review": {**review, "problemId": "foreign"}, "requestId": "other"})
    assert missing.status_code == 404
    capability = call(client, auth, "research_decision_routes.review", {"review": review}, "cap-review")
    assert capability.status_code == 200, capability.text
    assert capability.json()["result"]["snapshot"] == proposal["snapshot"]
    assert capability.json()["result"]["status"] == "pending"
    assert decisions.listing(service, "draft", "draft", "rc_decision")["reviews"] == []


def test_lifecycle_capabilities_pin_exact_review_without_deciding(setup):
    client, service, auth = setup
    review = seed(service)
    prefix = "research_review_proposal_routes."
    prepared = call(client, auth, prefix + "prepare", {"review": review}, "lifecycle")
    assert prepared.status_code == 200, prepared.text
    proposal = prepared.json()["result"]
    assert call(client, auth, prefix + "prepare", {"review": review}, "lifecycle").json() == prepared.json()
    readback = call(client, auth, prefix + "read", {"identifier": proposal["id"]})
    assert readback.json()["result"] == proposal
    listed = call(client, auth, prefix + "listing", {"decisionId": "rc_decision"})
    assert listed.json()["result"]["items"] == [proposal]
    data = {"identifier": proposal["id"], "digest": proposal["digest"], "action": "accept"}
    response = call(client, auth, prefix + "decide", data)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == "awaiting_human" and result["result"] == proposal
    query = parse_qs(urlsplit(result["reviewUrl"]).query)
    assert query["researchReview"] == [proposal["id"]] and query["researchDigest"] == [proposal["digest"]]
    assert query["researchCard"] == ["rc_decision"] and query["workspace"] == ["draft"]
    assert call(client, auth, prefix + "decide", {**data, "action": "reject"}).json()["state"] == "awaiting_human"
    assert call(client, auth, prefix + "decide", {**data, "digest": "wrong"}).status_code == 409
    assert call(client, auth, prefix + "decide", {**data, "action": "approve"}).status_code == 422
    assert decisions.listing(service, "draft", "draft", "rc_decision")["reviews"] == []
    assert decide(client, proposal).status_code == 200
    assert call(client, auth, prefix + "decide", data).status_code == 409
