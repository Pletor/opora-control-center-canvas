from backend.flow.catalogs.data_flow import FLOW_TYPES
from backend.flow.conftest import edge, node
from backend.flow.graph_check import graph_errors
from backend.flow.node_types import NODE_TYPES, catalog


def sub(eid, source, target, kind):
    return edge(eid, source, target, kind, kind, kind)


def rag():
    """Ingest a dotaz z kontraktu (image8): rámce jako notes, krok jako skupina."""
    nodes = [node("t", "trigger.manual"), node("load", "infra.storage"),
             node("vs", "ai.vectorStore", params={"mode": "insert"}), node("emb", "ai.embedding"),
             node("doc", "ai.documentLoader"), node("split", "ai.textSplitter"),
             node("chat", "trigger.chat"), node("agent", "ai.agent", notes="Odpoví z báze", notesInFlow=True,
                                                 inputSchema={"type": "object"}, example=[{"json": {"q": "?"}}],
                                                 onError="errorOutput", retry={"maxTries": 3, "waitMs": 1000},
                                                 params={"prompt": "={{ $('chat').item.json.chatInput }}"}),
             node("model", "ai.model"), node("mem", "ai.memory"), node("kb", "ai.vectorStore",
                                                                       params={"mode": "retrieveAsTool"}),
             node("qemb", "ai.embedding"), node("reply", "transform.set", mode="once"), node("fail", "flow.stopError")]
    edges = [edge("1", "t", "load"), edge("2", "load", "vs"), sub("3", "emb", "vs", "embedding"),
             sub("4", "doc", "vs", "document"), sub("5", "split", "doc", "textSplitter"),
             edge("6", "chat", "agent"), sub("7", "model", "agent", "model"), sub("8", "mem", "agent", "memory"),
             edge("9", "kb", "agent", "tool", "tool", "tool"), sub("10", "qemb", "kb", "embedding"),
             edge("11", "agent", "reply"), edge("12", "agent", "fail", "error")]
    notes = [{"id": "n1", "content": "# Ingest", "x": 0, "y": 0, "width": 800, "height": 400, "color": 2}]
    groups = [{"id": "g1", "name": "Dotaz", "description": "Agent s nástroji", "nodeIds": [
        "agent", "model", "mem", "kb", "qemb", "reply"], "outputSchema": {"type": "object"}}]
    return {"nodes": nodes, "edges": edges, "notes": notes, "groups": groups}


def test_catalog_has_contract_types_and_dynamic_ports():
    assert catalog("library_flow") is FLOW_TYPES and catalog("heart") is NODE_TYPES
    assert len(FLOW_TYPES) >= 22 and {"ai.agent", "flow.if", "human.approval"} <= FLOW_TYPES.keys()
    vs = FLOW_TYPES["ai.vectorStore"]
    assert {p.name for p in vs.ports_for({"mode": "insert"})} == {"main", "embedding", "document"}
    assert [p.kind for p in vs.ports_for({"mode": "retrieveAsTool"}) if p.direction == "out"] == ["tool"]
    agent = FLOW_TYPES["ai.agent"]
    assert "outputParser" not in {p.name for p in agent.ports}
    assert "outputParser" in {p.name for p in agent.ports_for({"hasOutputParser": True})}
    model = next(p for p in agent.ports if p.name == "model")
    assert model.required and model.cardinality == "one"
    switch = FLOW_TYPES["flow.switch"].ports_for({"rules": [{"output": "vip"}, {}], "fallback": "extra"})
    assert [p.name for p in switch if p.direction == "out"] == ["vip", "1", "fallback"]


def test_rag_graph_is_valid():
    assert graph_errors(rag(), FLOW_TYPES, "library_flow") == []


def test_port_rules():
    graph = rag()
    graph["edges"] = [e for e in graph["edges"] if e["id"] != "7"]  # agent bez modelu
    graph["edges"].append(sub("13", "emb", "agent", "embedding"))  # agent embedding nemá
    graph["edges"].append(sub("14", "mem", "kb", "memory"))
    errors = graph_errors(graph, FLOW_TYPES, "library_flow")
    assert "Uzel agent: povinný port model není připojený." in errors
    assert any("uzel agent nemá in port 'embedding'" in e for e in errors)
    assert any("uzel kb nemá in port 'memory'" in e for e in errors)
    two = rag()
    two["nodes"].append(node("model2", "ai.model"))
    two["edges"].append(sub("13", "model2", "agent", "model"))
    two["groups"][0]["nodeIds"].append("model2")
    assert any("nese jen jednu hranu" in e for e in graph_errors(two, FLOW_TYPES, "library_flow"))
    no_error_port = rag()
    no_error_port["nodes"][7] = {**no_error_port["nodes"][7], "onError": "stop"}
    assert any("nemá out port 'error'" in e for e in graph_errors(no_error_port, FLOW_TYPES, "library_flow"))


def test_node_fields_notes_and_refs():
    graph = rag()
    graph["nodes"][7] = {**graph["nodes"][7], "mode": "batch", "retry": {"maxTries": 0},
                         "params": {"prompt": "{{ $('nikdo').item.json.x }}"}}
    graph["notes"].append({"id": "n2", "x": 0, "y": 0, "width": 0, "height": 10})
    errors = graph_errors(graph, FLOW_TYPES, "library_flow")
    assert "Uzel agent: mode je perItem nebo once." in errors
    assert any("retry" in e for e in errors)
    assert "Uzel agent: odkaz $('nikdo') vede na neexistující uzel." in errors
    assert any(e.startswith("Poznámka n2:") for e in errors)


def test_group_rules():
    def errors(*groups):
        return graph_errors({**rag(), "groups": list(groups)}, FLOW_TYPES, "library_flow")
    assert any("spouštěč chat" in e for e in errors({"id": "g", "name": "G", "nodeIds": ["chat", "agent", "model"]}))
    split = errors({"id": "g", "name": "G", "nodeIds": ["agent", "reply"]})
    assert any("musí být ve stejné skupině" in e for e in split)
    assert any("netvoří souvislý řetězec" in e
               for e in errors({"id": "g", "name": "G", "nodeIds": ["load", "split"]}))
    two_exits = rag()
    two_exits["edges"].append(edge("13", "reply", "fail"))  # ze skupiny Dotaz vede ven agent i reply
    assert any("výstup vede jen z posledního" in e for e in graph_errors(two_exits, FLOW_TYPES, "library_flow"))
    twice = errors({"id": "a", "name": "A", "nodeIds": ["load", "vs", "emb", "doc", "split"]},
                   {"id": "b", "name": "", "description": "x" * 146, "nodeIds": ["load"]})
    assert "Uzel load je ve skupině a i b." in twice and "Skupina b nemá jméno." in twice
    assert any("do 145 znaků" in e for e in twice)


def test_other_kinds_ignore_library_fields():
    graph = {"nodes": [node("t", "trigger.manual", mode="x")], "edges": [], "groups": "nic"}
    assert graph_errors(graph) == []
