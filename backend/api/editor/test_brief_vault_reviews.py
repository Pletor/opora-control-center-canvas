"""Real factory routes enforce human session, scoped token reads and immutable CAS."""
from backend.api.brain_opora.test_canvas_capability_routes import SCOPE
from backend.api.brain_opora.test_canvas_capability_routes import setup as capability_setup
from backend.brain_opora.determinism import gate, tokens
from backend.editor.brief_vault import operation_reviews as ops
from backend.editor.brief_vault.test_operation_reviews import seed
from backend.editor.node.test_removals import HEADERS

setup = capability_setup


def test_exact_intent_read_and_real_human_decision(setup):
    client, service, auth = setup
    seed(service)
    session = gate.authenticate(service, auth[tokens.HEADER], "draft", ("heart",))
    operation = {"op": "create", "title": "Original", "text": "Exact source", "scopeNodeId": "", "discipline": "be"}
    fragment = ops.invoke(service, "draft", "draft", session, operation, "create")["result"]["fragment"]
    pending = ops.invoke(service, "draft", "draft", session,
        {"op": "delete", "fragmentId": fragment["id"], "expectedRevision": 1, "note": "Reviewed removal"}, "delete")
    base = "/api/brief-vault/reviews/delete"
    read = client.get(base, params=SCOPE, headers=auth)
    assert read.status_code == 200, read.text
    assert read.json()["operation"]["fragmentId"] == fragment["id"]
    body = {**SCOPE, "digest": pending["result"]["digest"]}
    assert client.post(base + "/accept", headers=auth, json=body).status_code == 403
    assert client.get(base, params={**SCOPE, "project": "foreign"}, headers=auth).status_code == 403
    assert client.get(base, params={**SCOPE, "workspace": "foreign"}, headers=auth).status_code == 403
    assert client.post(base + "/accept", headers={"X-Opora-Actor": "human"}, json=body).status_code in (403, 428)
    result = client.post(base + "/accept", headers=HEADERS, json=body)
    assert result.status_code == 200, result.text
    assert result.json()["result"]["fragment"]["deleted"]
    assert client.post(base + "/accept", headers=HEADERS, json=body).json() == result.json()
    assert client.post(base + "/reject", headers=HEADERS, json=body).status_code == 409
    assert client.get(base, params=SCOPE, headers=auth).json()["decision"]["response"] == result.json()
    client.cookies.clear()
    assert client.get(base, params=SCOPE).status_code in (401, 403, 428)
