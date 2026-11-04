import pytest

from backend.flow.catalogs.data_flow import FLOW_TYPES
from backend.flow.conftest import edge, node
from backend.flow.graph_check import graph_errors
from backend.flow.node_spec import INTENTS, LAYERS
from backend.flow.node_types import catalog


def check(nodes, edges):
    return graph_errors({"nodes": nodes, "edges": edges}, catalog("library_flow"), "library_flow")


def test_every_type_has_layer_and_guidance():
    for name, t in FLOW_TYPES.items():
        assert t.layer in LAYERS and t.use.startswith("Použij") and t.avoid.startswith("Nepoužívej"), name
        assert t.intents and set(t.intents) <= set(INTENTS), name
    assert not any(name.startswith("action.") for name in FLOW_TYPES)


def test_default_layers_and_ports():
    layers = {name: t.layer for name, t in FLOW_TYPES.items()}
    assert layers["fe.form"] == layers["fe.notify"] == "fe" and layers["ai.agent"] == "ai"
    assert layers["trigger.manual"] == layers["flow.if"] == layers["human.approval"] == "neutral"
    assert FLOW_TYPES["fe.click"].trigger and [p.direction for p in FLOW_TYPES["fe.click"].ports] == ["out"]
    assert [p.direction for p in FLOW_TYPES["fe.show"].ports] == ["in"]
    assert [p.name for p in FLOW_TYPES["be.validate"].ports if p.direction == "out"] == ["true", "false"]


def test_bmi_process_is_valid():
    nodes = [node("f", "fe.form"), node("e", "be.endpoint"), node("v", "be.validate"), node("w", "db.write"),
             node("r", "be.function"), node("n", "fe.notify")]
    edges = [{**edge("1", "f", "e"), "via": "http", "data": {"kind": "json", "example": {"height": 180}}},
             edge("2", "e", "v"), edge("3", "v", "w", "true"), {**edge("4", "w", "r"), "via": "sql"},
             {**edge("5", "r", "n"), "via": "http"}]
    assert check(nodes, edges) == []


@pytest.mark.parametrize("source,target,via,ok", [
    ("fe.click", "be.endpoint", "http", True), ("fe.click", "be.endpoint", "event", True),
    ("fe.click", "be.endpoint", "sql", False), ("be.function", "db.read", "sql", True),
    ("be.function", "db.read", "render", False), ("db.read", "be.function", "call", True),
    ("be.function", "infra.api", "http", True), ("be.function", "infra.api", "sql", False),
    ("fe.state", "infra.api", "http", True), ("fe.state", "infra.api", "call", False),
    ("be.function", "fe.show", "render", True), ("be.function", "fe.show", "sql", False),
    ("be.function", "be.function", "sql", True), ("trigger.manual", "db.read", "render", True),
    ("ai.agent", "fe.show", "sql", True), ("fe.click", "be.endpoint", None, True)])
def test_via_depends_on_layer_pair(source, target, via, ok):
    link = {**edge("1", "a", "b"), **({"via": via} if via else {})}
    errors = [e for e in check([node("a", source), node("b", target)], [link]) if e.startswith("Hrana")]
    assert (errors == []) is ok, errors


def test_fe_to_db_is_error_even_without_via():
    assert any("přímo" in e for e in check([node("a", "fe.state"), node("b", "db.read")], [edge("1", "a", "b")]))
    assert any("přímo" in e for e in check([node("a", "db.read"), node("b", "fe.show")], [edge("1", "a", "b")]))


def test_node_layer_overrides_type_default():
    link = {**edge("1", "a", "b"), "via": "sql"}
    assert check([node("a", "be.function"), node("b", "fe.state", layer="db")], [link]) == []
    assert check([node("a", "be.function"), node("b", "fe.state")], [link])
    assert check([node("a", "be.function", layer="fe"), node("b", "db.read")], [edge("1", "a", "b")])
    assert any("layer" in e for e in check([node("a", "be.function", layer="mars")], []))


def test_edge_data_shape_and_unknown_via():
    nodes = [node("a", "be.function"), node("b", "be.function")]
    assert check(nodes, [{**edge("1", "a", "b"), "data": {"kind": "table", "schema": {"type": "array"}}}]) == []
    assert check(nodes, [{**edge("1", "a", "b"), "data": {"kind": "blob"}}])
    assert check(nodes, [{**edge("1", "a", "b"), "data": {"kind": "json", "schema": "x"}}])
    assert check(nodes, [{**edge("1", "a", "b"), "via": "carrier-pigeon"}])


def test_custom_step_needs_layer_and_title_and_branches_become_ports():
    assert check([node("c", "custom.step")], []) == [
        "Uzel c: krok na míru (custom.step) musí mít vrstvu (layer).",
        "Uzel c: krok na míru (custom.step) musí mít neprázdný titulek (params.title)."]
    ok = node("c", "custom.step", layer="be", params={"title": "Spočítej BMI", "branches": ["ok", "chyba"]})
    assert check([ok, node("n", "fe.notify")], [edge("1", "c", "n", "chyba")]) == []
    assert any("nemá out port" in e for e in check([ok, node("n", "fe.notify")], [edge("1", "c", "n")]))
    assert check([node("c", "custom.step", layer="be", params={"title": "A", "branches": [1]})], []) == [
        "Uzel c: params.branches kroku na míru je seznam jmen větví."]
    assert [p.direction for p in FLOW_TYPES["custom.step"].ports] == ["in", "out"]
