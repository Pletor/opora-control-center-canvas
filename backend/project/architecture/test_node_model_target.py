"""Cíl z MODELu pro agenta (docs/studio.md §4a): vazba, bez vazby, scénář ignorován, ořez 0b, `contextVersion`."""

import copy
import json
import sqlite3
import threading
from contextlib import nullcontext
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.project.architecture import node_architecture as node_architecture_module
from backend.project.architecture.node_architecture import node_architecture
from backend.project.architecture.node_model_target import (
    SOURCE,
    domain_of,
    model_target,
    read_model_target,
)
from database.repositories.studio_models import StudioModelStore
from database.schema.studio_model_schema import SCHEMA as STUDIO_MODEL_SCHEMA

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}


def card(identifier, parent=None, **extra):
    return {"id": identifier, "parentId": parent, "kind": "node", "name": identifier, "purpose": "", "x": 0, "y": 0,
            **extra}


GRAPH = {"nodes": [card("app", kind="sector", site={"kind": "application", "environments": []}),
                   card("kontakt", "app", site={"kind": "page", "path": "/kontakt"}),
                   card("formular", "kontakt"),
                   card("api", "app"),
                   card("venku")],
         "edges": []}


def unit(identifier, kind="service", name=None, model=None, binding=None):
    return {"id": identifier, "type": kind, "name": name or identifier, "position": {"x": 0, "y": 0},
            "config": {"endpoint": "", **({"model": model} if model is not None else {})},
            **({"binding": {"nodeId": binding}} if binding else {})}


def link(identifier, source, target, kind="http-request", enabled=True):
    return {"id": identifier, "from": {"nodeId": source, "portId": "out"}, "to": {"nodeId": target, "portId": "in"},
            "type": kind, "enabled": enabled}


def studio(nodes, edges=(), incidents=None, domain="app", revision=4):
    return {"schema": "opora.studio-model/1", "domainId": domain, "revision": revision, "nodes": list(nodes),
            "edges": list(edges),
            **({"modelDefinition": {"version": "flow-model/1", "layer": "MODEL", "principle": "", "limitations": "",
                                    "incidents": incidents}} if incidents is not None else {})}


def test_bound_unit_gives_entered_targets_incidents_and_links():
    model = studio(
        [unit("svc", name="Service", model={"capacity": 2500, "concurrency": 20, "replicas": 2, "telemetryRate": 0.01},
              binding="api"),
         unit("db", "postgresql", "PostgreSQL"), unit("gw", "api-gateway", "Brána")],
        [link("e2", "svc", "db", "sql-query"), link("e1", "gw", "svc"), link("e3", "svc", "db", "event", enabled=False)],
        incidents=[{"tick": 5, "kind": "crash", "nodeIds": ["svc"]}, {"tick": 6, "kind": "slow", "nodeIds": ["db", "svc"]},
                   {"tick": 7, "kind": "restore", "nodeIds": ["svc"]}, {"tick": 8, "kind": "crash", "nodeIds": ["svc"]},
                   {"tick": 9, "kind": "crash", "nodeIds": ["db"]}])
    assert model_target(model, "api") == {
        "source": SOURCE, "domain": "app", "revision": 4, "type": "service", "name": "Service",
        # telemetryRate 0.01 je výchozí hodnota, kterou frontend uloží při vzniku Service: není zadaná.
        "targets": {"capacity": 2500, "concurrency": 20, "replicas": 2},
        "mustSurvive": ["crash", "slow"],
        "links": [{"from": "Brána", "type": "http-request"}, {"to": "PostgreSQL", "type": "sql-query"}]}


def test_changed_creation_default_counts_as_entered_and_empty_parts_are_left_out():
    deployment = unit("k8s", "kubernetes-deployment", model={"crashAfterTicks": 3}, binding="api")
    assert model_target(studio([deployment]), "api") == {"source": SOURCE, "domain": "app", "revision": 4,
                                                         "type": "kubernetes-deployment", "name": "k8s"}
    deployment["config"]["model"]["crashAfterTicks"] = 5
    assert model_target(studio([deployment]), "api")["targets"] == {"crashAfterTicks": 5}


def test_without_binding_there_is_no_target_and_first_bound_unit_by_id_wins():
    assert model_target(studio([unit("svc")]), "api") is None
    assert model_target(studio([]), "api") is None
    both = studio([unit("z", name="Zadní", binding="api"), unit("a", name="Přední", binding="api")])
    assert model_target(both, "api")["name"] == "Přední"


def test_links_stop_at_five():
    nodes = [unit("svc", binding="api"), *(unit(f"n{i}") for i in range(7))]
    edges = [link(f"e{i}", "svc", f"n{i}") for i in range(7)]
    assert [item["to"] for item in model_target(studio(nodes, edges), "api")["links"]] == ["n0", "n1", "n2", "n3", "n4"]


def test_domain_is_the_application_of_the_card():
    assert domain_of(GRAPH, "formular") == "app"
    assert domain_of(GRAPH, "app") == "app"
    assert domain_of(GRAPH, "venku") is None
    assert domain_of(GRAPH, "chybi") is None


def fake_service(models):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(STUDIO_MODEL_SCHEMA)
    for model in models:
        StudioModelStore(db, "p").put(model["domainId"], model["revision"], model, "2026-10-28T00:00:00")
    return SimpleNamespace(db_for=lambda project: db, reading=lambda project: nullcontext(),
                           lock_for=lambda project: threading.RLock())


def test_reads_the_model_of_the_card_domain_and_never_a_scenario():
    bound = unit("svc", model={"capacity": 900}, binding="formular")
    scenario = studio([unit("svc", model={"capacity": 1}, binding="formular")], domain="scenario:web")
    service = fake_service([scenario])
    assert read_model_target(service, "p", GRAPH, "formular") is None  # jen scénář: karta cíl nedostane
    service = fake_service([scenario, studio([bound])])
    assert read_model_target(service, "p", GRAPH, "formular")["targets"] == {"capacity": 900}
    assert read_model_target(service, "p", GRAPH, "venku") is None  # mimo aplikaci
    assert read_model_target(service, "p", GRAPH, "api") is None  # v doméně, ale bez vazby


TARGET = {"source": SOURCE, "domain": "app", "revision": 4, "type": "service", "name": "Service",
          "targets": {"capacity": 2500}, "mustSurvive": ["crash"], "links": [{"to": "PostgreSQL", "type": "sql-query"}]}


def test_architecture_carries_the_model_and_a_card_outside_a_page_gets_only_the_model():
    with_page = node_architecture(GRAPH, "formular", model=TARGET)
    assert with_page == {"page": {"path": "/kontakt"}, "model": TARGET}
    assert node_architecture(GRAPH, "api", model=TARGET) == {"model": TARGET}
    assert node_architecture(GRAPH, "api") is None
    assert node_architecture(GRAPH, "formular") == {"page": {"path": "/kontakt"}}


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def test_cut_stage_0b_takes_links_then_the_whole_model_right_after_holes(monkeypatch):
    graph = copy.deepcopy(GRAPH)
    graph["nodes"][2]["card"] = {"states": ["hotovo"]}  # state.no-error = díra karty
    graph["edges"] = [{"id": "e1", "source": "formular", "target": "api", "carries": "command"}]
    target = copy.deepcopy(TARGET)
    monkeypatch.setattr(node_architecture_module, "LIMIT_BYTES", 10 ** 6)
    full = node_architecture(graph, "formular", model=target)
    assert full["holes"] and full["model"]["links"] and full["out"]
    expected = copy.deepcopy(full)
    for cut in (lambda r: r.pop("holes"), lambda r: r["model"].pop("links"), lambda r: r.pop("model"),
                lambda r: r.pop("out")):
        cut(expected)
        stage = {**copy.deepcopy(expected), "truncated": True}
        monkeypatch.setattr(node_architecture_module, "LIMIT_BYTES", size(stage))
        assert node_architecture(graph, "formular", model=target) == stage
    assert target == TARGET  # ořez nesahá na předaný cíl


def test_saved_model_does_not_change_the_context_version(tmp_path):
    """Cíl z MODELu leží mimo `specification`: uložení modelu domény `contextVersion` karty nemění."""
    def brief(client):
        return client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "formular"}).json()

    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        view = client.get("/api/view", params=SCOPE).json()
        saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": GRAPH, "digest": view["digest"]})
        assert saved.status_code == 200, saved.text
        before = brief(client)
        put = client.put("/api/studio/model", params={"project": "draft", "domain": "app"}, headers=HEADERS,
                         json=studio([unit("svc", model={"capacity": 900}, binding="formular")], revision=0))
        assert put.status_code == 200, put.text
        after = brief(client)
        assert after["contextVersion"] == before["contextVersion"]
        assert after["specification"] == before["specification"]
        graph = client.get("/api/view", params=SCOPE).json()["graph"]
        target = read_model_target(client.app.state.service, "draft", graph, "formular")
        assert target == {"source": SOURCE, "domain": "app", "revision": 1, "type": "service", "name": "svc",
                          "targets": {"capacity": 900}}
