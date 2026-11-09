"""Real token boundary and bounded simulated roles; no fabricated independent principals."""
import pytest

from backend.api.brain_opora.test_canvas_capability_routes import ORIGIN, SCOPE
from backend.api.brain_opora.test_canvas_capability_routes import setup as capability_setup
from backend.brain_opora.determinism import tokens


@pytest.fixture
def duel_setup(tmp_path):
    yield from capability_setup.__wrapped__(tmp_path)


def test_delegation_requires_owner_session_and_finite_roles(duel_setup):
    client, service, auth = duel_setup
    def post(body, headers=auth, status=200):
        response = client.post("/api/brief-vault", json={**SCOPE, **body}, headers=headers)
        assert response.status_code == status, response.text
        return response.json()
    opening = {"op": "duel-open", "subject": {"kind": "project", "id": "draft"},
               "scopeNodeId": "", "incumbent": {"text": "A"}, "challenger": {"text": "B"}, "delegatedRoles": True}
    before = service.view("draft", "draft")["digest"]
    post(opening, {"origin": ORIGIN, "X-Opora-Actor": "agent; name=heart"}, 401)
    client.get("/api/access/ui-session", headers={"origin": ORIGIN})
    post(opening, {"origin": ORIGIN, "X-Opora-Actor": "human"}, 401)
    opened = post(opening)
    fragment = opened["fragment"]
    body = {"op": "duel-turn", "fragmentId": fragment["id"], "expectedRevision": fragment["revision"],
            "side": "A", "kind": "claim", "text": "Evidence A", "delegateRole": "advocate_a"}
    _, other = tokens.issue_heart(service, "draft", "draft")
    post(body, {**auth, tokens.HEADER: other}, 400)
    for role in ("advocate_b", "judge_1", "human", "unknown", None, [], {}):
        post({**body, "delegateRole": role}, status=400)
    post({k: v for k, v in body.items() if k != "delegateRole"}, status=400)
    first = post(body)
    assert first["turn"]["by"] == "heart" and first["turn"]["delegateRole"] == "advocate_a"
    assert first["turn"]["principalSessionId"] == opened["duel"]["delegation"]["sessionId"]
    score = {"op": "duel-score", "fragmentId": fragment["id"], "expectedRevision": first["fragment"]["revision"],
             "turnId": first["turn"]["id"], "strength": 7, "supports": "A", "delegateRole": "judge_1"}
    post({**score, "delegateRole": "advocate_a"}, status=400)
    scored = post(score)
    assert scored["score"]["judge"] == "heart"
    score["expectedRevision"] = scored["fragment"]["revision"]
    post(score, status=409)
    second = post({**score, "delegateRole": "judge_2"})
    assert len(second["duel"]["scores"]) == 2
    post({"op": "duel-decide", "fragmentId": fragment["id"], "expectedRevision": second["fragment"]["revision"]},
         {**auth, tokens.HEADER: other}, 400)
    assert service.view("draft", "draft")["digest"] == before
