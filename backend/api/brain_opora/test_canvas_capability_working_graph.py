from copy import deepcopy

from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.canvas.test_canvas_plan import HEADERS
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import baseline


def install(service):
    view = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [node("a"), node("b")], "edges": []}, view["digest"])


def test_draft_graph_preserves_exact_identity_and_replays(setup):
    client, service, auth = setup
    view = service.view("draft", "draft")
    graph = {"nodes": [node("exact-comment", kind="comment", purpose="Retained text")], "edges": []}
    body = {"graph": graph, "digest": view["digest"], "expectedAcceptedHead": None}
    response = call(client, auth, "canvas_routes.graph", body, "graph")
    assert response.status_code == 200, response.text
    assert response.json()["verified"] and service.view("draft", "draft")["graph"] == graph
    assert call(client, auth, "canvas_routes.graph", body, "graph").json() == response.json()
    assert call(client, auth, "canvas_routes.graph", {**body, "undo": True}, "graph").status_code == 409


def test_native_remove_restore_recovery_scope_and_replay(setup):
    client, service, auth = setup
    install(service)
    view = deepcopy(service.view("draft", "draft"))
    preview = service.removals.preview("draft", "draft", "node", "a")
    body = {"kind": "node", "target": "a", "digest": preview["digest"], "confirmed": True}
    removed = call(client, auth, "canvas_routes.remove_item", body, "remove")
    assert removed.status_code == 200, removed.text
    recovery = removed.json()["result"]["recoveryId"]
    assert call(client, auth, "canvas_routes.remove_item", body, "remove").json() == removed.json()
    restore = {"recoveryId": recovery, "digest": service.view("draft", "draft")["digest"]}
    assert call(client, auth, "canvas_routes.restore_removed", restore, "foreign", {**SCOPE, "workspace": "main"}).status_code == 403
    restored = call(client, auth, "canvas_routes.restore_removed", restore, "restore")
    assert restored.status_code == 200 and restored.json()["verified"], restored.text
    assert service.view("draft", "draft")["graph"] == view["graph"]
    assert call(client, auth, "canvas_routes.restore_removed", restore, "restore").json() == restored.json()


def test_accepted_removal_real_human_review_and_no_agent_impersonation(setup):
    client, service, auth = setup
    install(service)
    head = baseline(service)["id"]
    preview = service.removals.preview("draft", "draft", "node", "a")
    body = {"kind": "node", "target": "a", "digest": preview["digest"], "confirmed": True}
    prepared = call(client, auth, "canvas_routes.remove_item", body, "review")
    assert prepared.status_code == 200 and not prepared.json()["applied"], prepared.text
    path = "/api/working-reviews/remove_item/review"
    read = client.get(path, params=SCOPE, headers=auth)
    assert read.status_code == 200 and read.json()["preparation"] == prepared.json(), read.text
    assert client.get(path, params={**SCOPE, "workspace": "main"}, headers=auth).status_code == 403
    assert call(client, auth, "working_review_routes.apply", {"operation": "remove_item", "identifier": "review"}).json() == prepared.json()
    denied = client.post(path + "/apply", json=SCOPE, headers=auth)
    assert denied.status_code in (403, 409), denied.text
    client.get("/api/access/ui-session")
    applied = client.post(path + "/apply", json=SCOPE, headers=HEADERS)
    assert applied.status_code == 200 and applied.json()["acceptedHead"] == head, applied.text
    assert client.post(path + "/apply", json=SCOPE, headers=HEADERS).json() == applied.json()
    assert [n["id"] for n in service.view("draft", "draft")["graph"]["nodes"]] == ["b"]


def test_full_graph_pending_candidate_keeps_accepted_and_working_unchanged(setup):
    client, service, auth = setup
    install(service)
    head = baseline(service)["id"]
    view = deepcopy(service.view("draft", "draft"))
    graph = deepcopy(view["graph"])
    graph["nodes"][0]["name"] = "Reviewed title"
    body = {"graph": graph, "digest": view["digest"], "expectedAcceptedHead": head}
    proposed = call(client, auth, "canvas_routes.graph", body, "candidate")
    assert proposed.status_code == 200, proposed.text
    result = proposed.json()
    assert not result["applied"] and result["proposal"]["schemaVersion"] == 4
    assert "ohGraph=" + result["proposal"]["id"] in result["url"]
    assert service.view("draft", "draft")["graph"] == view["graph"]
    assert call(client, auth, "canvas_routes.graph", body, "candidate").json() == result
    assert call(client, auth, "canvas_routes.graph", {**body, "expectedAcceptedHead": None}, "draft-denied").status_code == 409
