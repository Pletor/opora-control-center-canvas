"""Native workflow history/run reads enforce ownership independently of project gates."""
from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.api.flow.test_flow_routes import GRAPH
from backend.brain_opora.determinism import tokens
from backend.flow import workflows, interpreter, library


def test_flow_read_adapters_have_exact_native_content_and_foreign_ids_fail(setup):
    client, service, auth = setup
    project = service.project_hub.empty_project({"name": "Own", "confirmed": True})["id"]
    foreign = service.project_hub.empty_project({"name": "Foreign", "confirmed": True})["id"]
    _, token = tokens.issue_heart(service, project, "draft")
    auth = {**auth, tokens.HEADER: token}
    scope = {"project": project, "workspace": "draft"}
    with service.registry_lock:
        own = workflows.create_workflow(service.db, "heart", "Own workflow", project)
        other = workflows.create_workflow(service.db, "heart", "Hidden", foreign)
        version = workflows.create_draft(service.db, own["id"], GRAPH)
        run = interpreter.start_run(service.db, version["id"])
    cases = {
        "workflow_list": ("/api/flow/workflows", {}),
        "version_list": ("/api/flow/workflows/" + own["id"] + "/versions", {"workflow_id": own["id"]}),
        "run_list": ("/api/flow/runs", {"workflow": own["id"]}),
        "run_detail": ("/api/flow/runs/" + run["id"], {"run_id": run["id"]}),
        "run_log": ("/api/flow/runs/" + run["id"] + "/log", {"run_id": run["id"]}),
    }
    for name, (path, data) in cases.items():
        response = call(client, auth, "flow_routes." + name, data, scope=scope)
        native = client.get(path, params={"project": project, **data})
        assert response.status_code == native.status_code == 200, response.text
        assert response.json()["result"] == native.json()
        assert "Hidden" not in response.text
    assert call(client, auth, "flow_routes.version_list", {"workflow_id": other["id"]}, scope=scope).status_code == 403
    assert call(client, auth, "flow_routes.run_list", {}, scope=scope).status_code == 422
    assert call(client, auth, "flow_routes.run_list", {"workflow": own["id"], "limit": 501}, scope=scope).status_code == 422


def test_shared_library_lineage_not_exposed_by_legacy_token_read(setup):
    client, service, auth = setup
    with service.registry_lock:
        folder = library.create_folder(service.db, "agent", "safe-test", "Shared")
        flow = library.create_flow(service.db, folder["id"], "source", "Shared source")
    path = "/api/library/flows/" + flow["id"]
    assert client.get(path).status_code == 200
    response = client.get(path, headers=auth, params={"project": "draft"})
    assert response.status_code == 403 and response.json()["code"] == "gate_scope"


def test_flow_inspection_reuses_native_models_and_has_no_writes(setup):
    client, service, auth = setup
    before = service.view("draft", "draft")["digest"]
    from backend.flow.test_simulate import bmi_graph, OK_CASE
    cases = {
        "node_type_list": ("/api/flow/node-types", {"kind": "heart"}),
        "node_port_list": ("/api/flow/node-ports", {"kind": "heart", "type": "trigger.manual", "params": {}}),
        "graph_check": ("/api/flow/graph-check", {"kind": "heart", "graph": GRAPH}),
        "simulate_case": ("/api/flow/simulate", {"graph": bmi_graph([OK_CASE]), "caseId": "ok"}),
    }
    for name, (path, data) in cases.items():
        native = client.get(path, params=data) if name == "node_type_list" else client.post(path, json=data, headers=auth)
        response = call(client, auth, "flow_routes." + name, data)
        assert response.status_code == native.status_code
        if response.status_code == 200:
            assert response.json()["result"] == native.json()
        else:
            assert response.status_code == 422
    assert call(client, auth, "flow_routes.node_type_list", {"kind": "not-a-kind"}).status_code == 422
    assert call(client, auth, "flow_routes.node_port_list", {"type": "not-a-type"}).status_code == 404
    assert service.view("draft", "draft")["digest"] == before
