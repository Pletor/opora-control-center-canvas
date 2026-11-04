from backend.flow.catalogs.page_intent import INTENT_TYPES
from backend.flow.conftest import edge, node
from backend.flow.graph_check import graph_errors
from backend.flow.node_types import NODE_TYPES, NodeType, Port


def test_linear_graph_is_valid():
    graph = {"nodes": [node("t", "trigger.manual"), node("e", "debug.echo")], "edges": [edge("1", "t", "e")]}
    assert graph_errors(graph) == []


def test_unknown_type_duplicate_node_and_missing_port():
    graph = {"nodes": [node("t", "trigger.manual"), node("t", "debug.echo"), node("x", "nope")],
             "edges": [edge("1", "t", "ghost"), edge("2", "t", "t", source_port="approved")]}
    errors = graph_errors(graph)
    assert any("dvakrát" in e for e in errors)
    assert any("neznámý typ" in e for e in errors)
    assert any("neexistující uzel" in e for e in errors)
    assert any("nemá out port 'approved'" in e for e in errors)


def test_edge_kind_must_match_port_kinds_and_cardinality():
    registry = {**NODE_TYPES,
                "agent": NodeType("agent", 1, (Port("main", "in"), Port("model", "in", "model", "one")), None),
                "model": NodeType("model", 1, (Port("model", "out", "model"),), None)}
    nodes = [node("a", "agent"), node("m1", "model"), node("m2", "model"), node("e", "debug.echo")]
    ok = {"nodes": nodes, "edges": [edge("1", "m1", "a", "model", "model", "model")]}
    assert graph_errors(ok, registry) == []
    wrong_kind = {"nodes": nodes, "edges": [edge("1", "m1", "a", "model", "model", "main")]}
    assert any("je main, ale port m1.model je model" in e for e in graph_errors(wrong_kind, registry))
    two = {"nodes": nodes, "edges": [edge("1", "m1", "a", "model", "model", "model"),
                                     edge("2", "m2", "a", "model", "model", "model")]}
    assert any("jen jednu hranu" in e for e in graph_errors(two, registry))
    unknown = {"nodes": nodes, "edges": [edge("1", "e", "a", kind="laser")]}
    assert any("neznámý kind" in e for e in graph_errors(unknown, registry))


def test_page_intent_needs_entry_done_and_matching_edge_kinds():
    nodes = [node("in", "intent.entry"), node("d", "intent.data"), node("ok", "intent.done")]
    good = {"nodes": nodes, "edges": [edge("1", "in", "d"), edge("2", "d", "ok"),
                                      edge("3", "in", "ok", "data", "data", "data")]}
    assert graph_errors(good, INTENT_TYPES, "page_intent") == []
    main_to_data = {"nodes": nodes, "edges": [edge("1", "in", "d", "main", "data", "main")]}
    assert any("port d.data je data" in e for e in graph_errors(main_to_data, INTENT_TYPES, "page_intent"))
    data_to_main = {"nodes": nodes, "edges": [edge("1", "in", "d", "data", "main", "data")]}
    assert any("port d.main je main" in e for e in graph_errors(data_to_main, INTENT_TYPES, "page_intent"))
    lonely = {"nodes": [node("d", "intent.data")], "edges": []}
    assert graph_errors(lonely, INTENT_TYPES, "page_intent") == [
        "Záměr stránky potřebuje aspoň jeden uzel intent.entry.",
        "Záměr stránky potřebuje aspoň jeden uzel intent.done."]
    assert graph_errors(lonely, INTENT_TYPES) == []  # pravidlo platí jen pro kind page_intent
    no_done = {"nodes": nodes[:2], "edges": [edge("1", "in", "d")]}  # s hranami (dřív je kind hrany přepsal)
    assert graph_errors(no_done, INTENT_TYPES, "page_intent") == ["Záměr stránky potřebuje aspoň jeden uzel intent.done."]


def test_cases_of_a_library_flow_are_checked():
    from backend.flow.node_types import catalog
    from backend.flow.test_simulate import BAD_CASE, DOWN_CASE, OK_CASE, bmi_graph

    def errors(*cases):
        return graph_errors(bmi_graph(cases), catalog("library_flow"), "library_flow")

    assert errors(OK_CASE, BAD_CASE, DOWN_CASE) == []
    assert errors(OK_CASE, OK_CASE) == ["Případ 'ok' nemá jedinečné neprázdné id."]
    assert errors({**OK_CASE, "id": " "}) == ["Případ ' ' nemá jedinečné neprázdné id."]
    assert errors({**OK_CASE, "start": "nope"}) == ["Případ ok: start 'nope' není uzel grafu."]
    assert errors({**OK_CASE, "name": ""}) == ["Případ ok nemá jméno."]
    assert errors({k: v for k, v in OK_CASE.items() if k != "input"}) \
        == ["Případ ok: chybí input (data na startu, klidně {})."]
    assert "Případ ok: env je" in errors({**OK_CASE, "env": {"tables": {"t": ["ne objekt"]}}})[0]
    assert errors({**OK_CASE, "env": {"services": {"ghost": {}}}}) == ["Případ ok: služba 'ghost' není uzel grafu."]
    assert errors({**OK_CASE, "expect": {"path": ["form", "ghost"]}}) \
        == ["Případ ok: expect.path vede přes neexistující uzel 'ghost'."]
    assert "expect.rows" in errors({**OK_CASE, "expect": {"rows": {"t": 1}}})[0]
    assert "expect.notify" in errors({**OK_CASE, "expect": {"notify": 5}})[0]
    assert graph_errors({**bmi_graph(), "cases": "x"}, catalog("library_flow"), "library_flow") \
        == ["cases musí být seznam."]
