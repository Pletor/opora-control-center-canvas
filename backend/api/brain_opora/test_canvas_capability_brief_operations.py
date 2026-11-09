"""Actual authenticated catalog dispatch and native review parity."""
from backend.api.brain_opora.test_canvas_capability_routes import SCOPE, call
from backend.api.brain_opora.test_canvas_capability_routes import setup as capability_setup
from backend.editor.brief_vault.brief_vault import OPS, BriefVault
from backend.editor.brief_vault.operation_review_contracts import ADAPTER_TESTS
from backend.editor.brief_vault.test_operation_reviews import seed

WRITE = "brief_vault_routes.brief_vault_write"
setup = capability_setup
READ = "brief_vault_review_routes.read"
DECIDE = "brief_vault_review_routes.decide"


def test_all_native_shapes_discovered_and_scoped_writes_replay(setup):
    client, service, auth = setup
    seed(service)
    description = client.get("/api/brain/canvas/capabilities/" + WRITE, params=SCOPE, headers=auth).json()
    assert description["implemented"]
    matrix = description["adapter"]["operations"]
    assert len(matrix) == 27 and {row["op"] for row in matrix} == set(OPS) == set(ADAPTER_TESTS)
    command = {"operation": {"op": "create", "scopeNodeId": "", "discipline": "be", "title": "Exact source", "text": "Literal text"}}
    response = call(client, auth, WRITE, command, "source")
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["verified"]
    fragment = saved["result"]["fragment"]
    assert BriefVault(service).fragment("draft", "draft", fragment["id"])["fragment"]["text"] == "Literal text"
    assert call(client, auth, WRITE, command, "source").json() == saved
    assert call(client, auth, WRITE, {"operation": {**command["operation"], "text": "Different"}}, "source").status_code == 409
    assert call(client, auth, WRITE, command, "other", scope={**SCOPE, "workspace": "main"}).status_code == 403
    assert call(client, auth, WRITE, {"operation": {**command["operation"], "actor": "human"}}, "spoof").status_code == 422
    deletion = call(client, auth, WRITE, {"operation": {"op": "delete", "fragmentId": fragment["id"], "expectedRevision": 1, "note": "Explicit review"}}, "delete")
    assert deletion.status_code == 200, deletion.text
    pending = deletion.json()["result"]
    fetched = call(client, auth, READ, {"identifier": "delete"})
    native = client.get("/api/brief-vault/reviews/delete", params=SCOPE, headers=auth)
    assert fetched.json()["result"] == native.json()
    preparation = call(client, auth, DECIDE, {"identifier": "delete", "digest": pending["digest"], "action": "accept"})
    assert preparation.status_code == 200, preparation.text
    assert preparation.json()["state"] == "awaiting_human"
    assert "vaultReview=delete" in preparation.json()["reviewUrl"]
    assert not BriefVault(service).fragment("draft", "draft", fragment["id"])["fragment"]["deleted"]
    assert call(client, auth, DECIDE, {"identifier": "delete", "digest": "wrong", "action": "accept"}).status_code == 409
