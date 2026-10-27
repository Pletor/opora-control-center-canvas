"""Technický model Studia: tvar `opora.studio-model/1`, limity, binding na graf a optimistická revize."""

import sqlite3
import threading
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from backend.project.studio.studio_model import (
    MAX_EDGES,
    MAX_NODES,
    StudioModelConflict,
    StudioModelInvalid,
    read_model,
    validate_model,
    write_model,
)
from database.schema.studio_model_schema import SCHEMA as STUDIO_MODEL_SCHEMA


def node(id_, **extra):
    return {"id": id_, "type": "service", "name": "Služba", "position": {"x": 0, "y": 1.5}, "config": {}, **extra}


def edge(id_, source="a", target="b", **extra):
    return {"id": id_, "from": {"nodeId": source, "portId": "http-out"}, "to": {"nodeId": target, "portId": "http-in"},
            "type": "http-request", "enabled": True, **extra}


def model(nodes=None, edges=None, revision=0, domain="web"):
    return {"schema": "opora.studio-model/1", "domainId": domain, "revision": revision,
            "nodes": [node("a"), node("b")] if nodes is None else nodes,
            "edges": [edge("e")] if edges is None else edges}


def make_service(graph_nodes=("card",)):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(STUDIO_MODEL_SCHEMA)
    reads = []

    def view(project, wid):
        reads.append(project)
        return {"graph": {"nodes": [{"id": item} for item in graph_nodes], "edges": []}}

    service = SimpleNamespace(project_hub=SimpleNamespace(settings=lambda project: {"project": {"sourceKind": "git"}}),
                              view=view, db_for=lambda project: db, reading=lambda project: nullcontext(),
                              lock_for=lambda project: threading.RLock())
    return service, reads


def test_valid_model_returns_its_bindings():
    assert validate_model(model(), "web") == set()
    bound = model(nodes=[node("a", binding={"nodeId": "card"}), node("b")])
    assert validate_model(bound, "web") == {"card"}


@pytest.mark.parametrize(("change", "message"), [
    (lambda m: m.update(schema="x"), "schema"),
    (lambda m: m.update(domainId="jina"), "domainId"),
    (lambda m: m.update(revision=-1), "revision"),
    (lambda m: m.update(revision=True), "revision"),
    (lambda m: m.update(nodes={}), "pole"),
    (lambda m: m["nodes"].append(node("a")), "duplicitní"),
    (lambda m: m["edges"].append(edge("e")), "duplicitní"),
    (lambda m: m["nodes"].append({"id": ""}), "nodes.id"),
    (lambda m: m["nodes"].append(7), "objekt"),
    (lambda m: m["nodes"][0].update(position={"x": float("nan"), "y": 0}), "position.x"),
    (lambda m: m["nodes"][0].update(config=[]), "config"),
    (lambda m: m["nodes"][0].update(name=""), "Název"),
    (lambda m: m["nodes"][0].update(binding={"nodeId": ""}), "binding"),
    (lambda m: m["edges"][0]["to"].update(nodeId="nikdo"), "neexistující"),
    (lambda m: m["edges"][0].update(type="soap"), "datový typ"),
    (lambda m: m["edges"][0].update(enabled="ano"), "enabled"),
    (lambda m: m["edges"][0].update(condition="x" * 2001), "condition"),
])
def test_invalid_shapes_are_rejected(change, message):
    body = model()
    change(body)
    with pytest.raises(StudioModelInvalid, match=message):
        validate_model(body, "web")


def test_limits_on_nodes_and_edges():
    with pytest.raises(StudioModelInvalid, match="limit"):
        validate_model(model(nodes=[node(f"n{i}") for i in range(MAX_NODES + 1)], edges=[]), "web")
    with pytest.raises(StudioModelInvalid, match="limit"):
        validate_model(model(edges=[edge(f"e{i}") for i in range(MAX_EDGES + 1)]), "web")


def test_missing_model_reads_as_empty_revision_zero():
    service, reads = make_service()
    assert read_model(service, "p1", "web") == {"schema": "opora.studio-model/1", "domainId": "web", "revision": 0,
                                              "nodes": [], "edges": [], "updatedAt": None}
    assert reads == []


def test_write_bumps_revision_and_conflicting_revision_is_rejected():
    service, reads = make_service()
    saved = write_model(service, "p1", "web", {**model(), "updatedAt": "klient"})
    assert saved["revision"] == 1 and saved["updatedAt"] != "klient"
    assert reads == []  # bez binding se graf nečte
    assert read_model(service, "p1", "web") == saved
    with pytest.raises(StudioModelConflict, match="revize 1"):
        write_model(service, "p1", "web", model(revision=0))
    assert write_model(service, "p1", "web", model(revision=1, edges=[]))["revision"] == 2
    assert read_model(service, "p1", "web")["edges"] == []
    assert read_model(service, "p1", "admin")["revision"] == 0


def test_binding_must_exist_in_project_graph():
    service, reads = make_service(graph_nodes=("card",))
    ok = write_model(service, "p1", "web", model(nodes=[node("a", binding={"nodeId": "card"}), node("b")]))
    assert ok["nodes"][0]["binding"] == {"nodeId": "card"} and reads == ["p1"]
    with pytest.raises(StudioModelInvalid, match="ghost"):
        write_model(service, "p1", "web", model(nodes=[node("a", binding={"nodeId": "ghost"}), node("b")], revision=1))
    assert read_model(service, "p1", "web")["revision"] == 1


def test_model_definition_is_stored_and_returned_unchanged():
    """MODEL část S5 (`modelDefinition`: plán incidentů, politika vazeb scénáře) se uloží a vrátí beze změny."""
    service, _ = make_service()
    definition = {"version": "flow-model/1", "layer": "MODEL", "principle": "", "limitations": "",
                  "connectionPolicy": "typed-ports/1", "incidents": [{"tick": 3, "kind": "crash", "nodeIds": ["a"]}]}
    saved = write_model(service, "p1", "web", {**model(), "modelDefinition": definition})
    assert saved["modelDefinition"] == definition
    assert read_model(service, "p1", "web")["modelDefinition"] == definition
