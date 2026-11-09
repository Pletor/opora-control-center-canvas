"""Shared graphs stay complete; foreign project lineage is never an agent read side channel."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.brain_opora.determinism import tokens
from backend.flow import library, workflows
from backend.flow.test_simulate import bmi_graph, OK_CASE


def test_library_projection_retains_published_graph_but_filters_foreign_lineage(setup):
    client, service, auth = setup
    own = service.project_hub.empty_project({"name": "Own", "confirmed": True})["id"]
    foreign = service.project_hub.empty_project({"name": "Foreign", "confirmed": True})["id"]
    _, token = tokens.issue_heart(service, own, "draft")
    auth = {**auth, tokens.HEADER: token}
    scope = {"project": own, "workspace": "draft"}
    graph = bmi_graph([OK_CASE])
    # Native fixture creation/activation is isolated setup, never performed by a read adapter.
    with service.registry_lock:
        db = service.db
        folder = library.create_folder(db, "agent", "projection-test", "Shared")
        shared = library.create_flow(db, folder["id"], "published", "Published flow")
        version = workflows.create_draft(db, shared["id"], graph, meta={"note": "Published note",
            "learnedFrom": {"project": foreign, "card": "secret-card", "result": "success"},
            "proposedBy": {"role": "heart", "project": foreign}})
        workflows.activate(db, workflows.set_candidate(db, version["id"])["id"])
        own_copy = library.adopt(db, shared["id"], own, "own-node")
        foreign_copy = library.adopt(db, shared["id"], foreign, "secret-node")
        contributed = library.contribute(db, foreign_copy["id"], folder["id"], "published-copy", "Published copy")
        before = library.flow_detail(db, shared["id"])
    detail = call(client, auth, "library_routes.flow_detail", {"workflow_id": shared["id"]}, scope=scope)
    assert detail.status_code == 200, detail.text
    result = detail.json()["result"]
    assert result["lineageScope"] == own
    assert result["projects"] == [own] and result["derivedCount"] == 1
    assert [row["workflowId"] for row in result["derived"]] == [own_copy["id"]]
    assert result["versions"][0]["graph"] == graph
    assert result["versions"][0]["meta"] == {"note": "Published note"}
    assert result["learnedFrom"] is None
    for secret in (foreign, foreign_copy["id"], "secret-card", "secret-node"):
        assert secret not in detail.text
    listing = call(client, auth, "library_routes.library_list", {"owner": "agent"}, scope=scope)
    assert listing.status_code == 200
    rows = [item for folder in listing.json()["result"]["folders"] for item in folder["flows"]]
    assert next(item for item in rows if item["id"] == shared["id"])["derivedCount"] == 1
    assert next(item for item in rows if item["id"] == contributed["id"])["derivedFrom"] is None
    exported = call(client, auth, "library_routes.flow_detail", {"workflow_id": contributed["id"]}, scope=scope).json()["result"]
    assert exported["derivedFrom"] is None and exported["versions"][0]["derived_from"] is None
    for secret in (foreign, foreign_copy["id"], "secret-card", "secret-node"):
        assert secret not in listing.text
    brief = call(client, auth, "library_routes.flow_brief", {"workflow_id": shared["id"], "version": 1}, scope=scope)
    native = client.get("/api/library/flows/" + shared["id"] + "/brief", params={"version": 1})
    assert brief.status_code == 200 and brief.json()["result"] == native.json()
    assert call(client, auth, "library_routes.flow_detail", {"workflow_id": foreign_copy["id"]}, scope=scope).status_code == 403
    assert call(client, auth, "library_routes.library_list", {"owner": "unknown"}, scope=scope).status_code == 422
    assert call(client, auth, "library_routes.flow_brief", {"workflow_id": shared["id"], "version": True}, scope=scope).status_code == 422
    with service.registry_lock:
        assert library.flow_detail(service.db, shared["id"]) == before
