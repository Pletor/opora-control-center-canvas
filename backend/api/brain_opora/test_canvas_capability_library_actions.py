"""Actual scoped Heart capability and human Library review lifecycle."""
from urllib.parse import urlparse, parse_qs

from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.canvas.test_canvas_plan import HEADERS
from backend.flow import library
from backend.flow.library_operations import folder_digest


def test_native_agent_folder_and_persisted_human_review_http(setup):
    client, service, auth = setup
    data = {"owner": "agent", "slug": "cap-agent", "title": "Agent folder"}
    direct = call(client, auth, "library_routes.folder_create", data, "agent-folder")
    assert direct.status_code == 200, direct.text
    assert direct.json()["applied"] and direct.json()["result"]["status"] == "applied"
    assert call(client, auth, "library_routes.folder_create", data, "agent-folder").json() == direct.json()
    direct_decision = call(client, auth, "library_review_routes.decide",
                           {"identifier": direct.json()["result"]["id"], "action": "reject"}).json()
    assert direct_decision["state"] == "applied" and direct_decision["applied"]
    assert direct_decision["result"] == direct.json()["result"]
    human = {**data, "owner": "human", "slug": "cap-human", "title": "Human folder"}
    created = call(client, auth, "library_routes.folder_create", human, "human-folder")
    assert created.status_code == 200, created.text
    result = created.json()
    assert result["state"] == "awaiting_human" and not result["applied"]
    identifier = result["result"]["id"]
    assert parse_qs(urlparse(result["url"]).query)["libraryReview"] == [identifier]
    path = "/api/library/reviews/" + identifier
    assert client.get(path, params=SCOPE, headers={"X-Opora-Actor": "agent; name=unverified"}).status_code == 401
    assert client.get(path, params=SCOPE, headers=auth).json() == result["result"]
    assert client.get(path, params={**SCOPE, "workspace": "foreign"}, headers=auth).status_code == 403
    assert client.post(path + "/accept", headers=auth, json=SCOPE).status_code == 403
    prepared = call(client, auth, "library_review_routes.decide", {"identifier": identifier, "action": "accept"})
    assert prepared.status_code == 200 and not prepared.json()["applied"]
    before = library.list_library(service.db, "human")
    assert all(folder["slug"] != "cap-human" for folder in before)
    accepted = client.post(path + "/accept", headers=HEADERS, json=SCOPE)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert client.post(path + "/accept", headers=HEADERS, json=SCOPE).json() == accepted.json()
    assert any(folder["slug"] == "cap-human" for folder in library.list_library(service.db, "human"))
    assert call(client, auth, "library_review_routes.review", {"identifier": identifier}).json()["result"] == accepted.json()
    for action in ("accept", "reject"):
        observed = call(client, auth, "library_review_routes.decide", {"identifier": identifier, "action": action}).json()
        assert observed["state"] == "accepted" and observed["applied"]
        assert observed["result"] == accepted.json()
    assert call(client, auth, "library_routes.folder_create", human, "human-folder").json()["result"] == accepted.json()
    assert sum(folder["slug"] == "cap-human" for folder in library.list_library(service.db, "human")) == 1


def test_human_cas_conflict_reject_and_changed_request(setup):
    client, service, auth = setup
    folder = library.list_library(service.db, "human")[0]
    data = {"folder_id": folder["id"], "expectedFolderDigest": folder_digest(folder), "title": "Prepared title"}
    response = call(client, auth, "library_routes.folder_update", data, "folder-update")
    assert response.status_code == 200, response.text
    identifier = response.json()["result"]["id"]
    assert call(client, auth, "library_routes.folder_update", {**data, "title": "Different"}, "folder-update").status_code == 409
    library.update_folder(service.db, folder["id"], "Concurrent title")
    path = "/api/library/reviews/" + identifier
    stale = client.post(path + "/accept", headers=HEADERS, json=SCOPE)
    assert stale.status_code == 409 and stale.json()["code"] == "library_review_stale"
    rejected = client.post(path + "/reject", headers=HEADERS, json=SCOPE)
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert library.get_folder(service.db, folder["id"])["title"] == "Concurrent title"
    for action in ("accept", "reject"):
        observed = call(client, auth, "library_review_routes.decide", {"identifier": identifier, "action": action}).json()
        assert observed["state"] == "rejected" and not observed["applied"]
        assert observed["result"] == rejected.json()
    assert call(client, auth, "library_routes.folder_update", data, "folder-update").json()["result"] == rejected.json()
    assert library.get_folder(service.db, folder["id"])["title"] == "Concurrent title"


def test_agent_folder_two_sessions_cas_stale_delete_and_replay(setup):
    client, service, auth = setup
    from backend.brain_opora.determinism import tokens
    _, other_token = tokens.issue_heart(service, "draft", "draft")
    other = {**auth, tokens.HEADER: other_token}
    created = call(client, auth, "library_routes.folder_create", {"owner": "agent", "slug": "cas-folder", "title": "Before"}, "cas-create").json()["result"]["result"]
    listing = call(client, auth, "library_routes.library_list", {"owner": "agent"}).json()["result"]["folders"]
    folder = next(item for item in listing if item["id"] == created["id"])
    data = {"folder_id": folder["id"], "expectedFolderDigest": folder["revisionDigest"], "title": "First session"}
    first = call(client, auth, "library_routes.folder_update", data, "first-update")
    assert first.status_code == 200, first.text
    conflict = call(client, other, "library_routes.folder_update", {**data, "title": "Second session"}, "second-update")
    assert conflict.status_code == 409 and conflict.json()["code"] == "library_folder_conflict"
    stale_delete = call(client, other, "library_routes.folder_delete", {key: data[key] for key in ("folder_id", "expectedFolderDigest")}, "stale-delete")
    assert stale_delete.status_code == 409 and stale_delete.json()["code"] == "library_folder_conflict"
    assert call(client, auth, "library_routes.folder_update", data, "first-update").json() == first.json()
    assert library.get_folder(service.db, folder["id"])["title"] == "First session"
