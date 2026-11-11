"""F3: stavba plátna 3 z plátna 2 – čistý přírůstek, idempotence a návrh grafu srdce přes skutečnou aplikaci."""
import pytest

from backend.api.editor.test_opora_execution_routes import (
    client as client,  # noqa: PLC0414 - sdílená fixture aplikace s grafem a přijatým základem
)
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas import plan_from_page, plan_reality
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_canvas_plan import HEADERS, SCOPE
from backend.canvas.test_opora_graph_proposals import accept

FLOWS = {
    "el-form": {"nodes": [{"id": "vystup-1", "notes": "Odeslaná poptávka"}, {"id": "data-1", "notes": "CRM"},
                          {"id": "data-2", "notes": "E-mail obchodníkovi"}]},
    "el-crm": {"nodes": [{"id": "vystup-1", "notes": "Uložený kontakt"}]},
}


def node(identifier, parent, kind="node", **extra):
    return {"id": identifier, "parentId": parent, "kind": kind, "name": identifier, "purpose": "", "x": 0, "y": 0} | extra


PLANE = [
    node("dom", None, "sector", name="Web", site={"kind": "application", "environments": []}),
    node("home", "dom", name="Domů", site={"kind": "page", "path": "/", "goal": "Získat poptávku.", "sections": [
        {"id": "hero", "role": "content", "name": "Úvod", "intent": ""},
        {"id": "pata", "role": "footer", "name": "Pata", "intent": ""}]}),
    node("el-form", "home", name="Formulář", purpose="Sebere poptávku.", element={"kind": "form"},
         card={"section": "hero", "status": "ready"}),
    node("el-crm", "home", name="CRM", element={"kind": "storage"}),
    node("prazdna", "dom", name="Prázdná", site={"kind": "page", "path": "/prazdna"}),
]
PLANE_EDGES = [{"id": "r1", "source": "el-form", "target": "el-crm", "port": "next", "relation": "requires"}]


def plans(graph):
    """`page_plan.read` bez služby: logika stránky z grafu (milník Realizace = karta ready)."""
    out = []
    for page in plan_from_page.pages_for(graph, "dom"):
        logic = [{"id": item["id"], "kind": item["element"]["kind"], "name": item["name"], "purpose": item["purpose"],
                  "section": (item.get("card") or {}).get("section"),
                  "milestone": "Realizace" if (item.get("card") or {}).get("status") == "ready" else "Návrh"}
                 for item in graph["nodes"] if item.get("parentId") == page["id"] and "element" in item]
        out.append((page, {"page": {"goal": page["site"].get("goal")}, "sections": page["site"].get("sections") or [],
                           "logic": logic}))
    return out


def test_addition_from_domain_shapes_process_areas_cards_and_links():
    graph = {"nodes": PLANE, "edges": PLANE_EDGES}
    result = plan_from_page.addition(graph, plans(graph), FLOWS)
    nodes = {item["ref"]: item for item in result["plan"]["nodes"]}
    assert nodes["p0"] == {"ref": "p0", "kind": "sector", "name": "Plán práce: Domů", "purpose": "Získat poptávku.",
                           "parent": "@dom"}
    assert [nodes[f"p0-m{i}"]["name"] for i in range(3)] == ["Návrh", "Realizace", "Ověření"]
    form = next(item for item in nodes.values() if item["name"] == "Formulář")
    assert form["parent"] == form["memberOf"] == "p0-m1"
    assert form["spec"] == {"goal": "Sebere poptávku.", "acceptance": "- Odeslaná poptávka"}
    edges = {(e["from"], e["to"], e.get("relation"), e.get("port")) for e in result["plan"]["edges"]}
    assert ("p0", "@home", "evidences", None) in edges and ("e0", "@el-form", "evidences", None) in edges
    assert {("p0-m0", "p0-m1", None, "flow"), ("p0-m1", "p0-m2", None, "flow")} <= edges
    assert ("e0", "e1", "uses", None) in edges and ("e0", "e1", "requires", None) in edges  # dataTo CRM + vazba prvků
    assert result["counts"] == {"areas": 3, "cards": 2, "edges": 7}
    assert result["unmatched"] == [{"elementId": "el-form", "name": "Formulář", "dataTo": "E-mail obchodníkovi"}]
    assert result["skipped"] == {"pages": [{"pageId": "prazdna", "name": "Prázdná"}],
                                 "boxes": [{"pageId": "home", "id": "pata", "name": "Pata"}]}


def test_rebuild_adds_only_the_difference_and_lists_orphans():
    built = [node("frame", "dom", "sector"), node("area", "frame", "area", name="Realizace", size={"w": 456, "h": 336}),
             node("card", "frame", memberOf="area"), node("lost", "frame", name="Ztracená")]
    links = [{"id": "x1", "source": "frame", "target": "home", "port": "next", "relation": "evidences"},
             {"id": "x2", "source": "card", "target": "el-form", "port": "next", "relation": "evidences"}]
    graph = {"nodes": PLANE + built, "edges": PLANE_EDGES + links}
    result = plan_from_page.addition(graph, plans(graph), FLOWS)
    refs = [item["ref"] for item in result["plan"]["nodes"]]
    assert refs == ["p0-m0", "p0-m2", "e1"]  # chybějící oblasti a karta CRM, nic dvakrát
    assert next(item for item in result["plan"]["nodes"] if item["ref"] == "e1")["parent"] == "p0-m0"
    assert result["existing"] == {"frames": 1, "areas": 1, "cards": 1}
    assert result["orphans"] == [{"nodeId": "lost", "name": "Ztracená"}]
    assert {(e["from"], e["to"], e.get("relation")) for e in result["plan"]["edges"]} >= {
        ("@card", "e1", "uses"), ("@card", "e1", "requires"), ("e1", "@el-crm", "evidences")}


def test_pages_for_refuses_other_nodes():
    with pytest.raises(GateError) as error:
        plan_from_page.pages_for({"nodes": PLANE, "edges": []}, "el-form")
    assert error.value.status == 404


@pytest.fixture
def plane(client, monkeypatch):
    view = client.get("/api/view", params=SCOPE).json()
    graph = {"nodes": [*view["graph"]["nodes"], *PLANE], "edges": [*view["graph"]["edges"], *PLANE_EDGES]}
    saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]})
    assert saved.status_code == 200, saved.text
    monkeypatch.setattr(plan_reality.library, "project_flow", lambda db, project, node: (
        {"versions": [{"status": "active", "graph": FLOWS[node]}]} if node in FLOWS else None))
    return client


def build(client, page="home"):
    return client.post(f"/api/page-plan/{page}/build-plan", headers=HEADERS, json=SCOPE)


def test_build_proposes_heart_graph_and_card_reads_its_element(plane):
    service = plane.app.state.service
    before = plane.get("/api/view", params=SCOPE).json()["graph"]
    response = build(plane)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["counts"] == {"areas": 3, "cards": 2, "edges": 7} and not result["proposal"]["reused"]
    assert plane.get("/api/view", params=SCOPE).json()["graph"] == before  # jen návrh, plátno beze změny
    assert build(plane).json()["proposal"] == {"id": result["proposal"]["id"], "reused": True}  # dvojí klik
    pending = build(plane, "dom")  # jiný rozsah nad čekajícím návrhem by po rebase zdvojil karty
    assert pending.status_code == 409 and result["proposal"]["id"] in pending.json()["error"]
    graphs = OporaGraphProposals(service)
    item = graphs.read(**SCOPE, record_id=result["proposal"]["id"])
    assert item["by"] == {"kind": "agent", "name": "heart"}
    accept(graphs, item)
    graph = plane.get("/api/view", params=SCOPE).json()["graph"]
    card = next(n for n in graph["nodes"] if n["name"] == "Formulář" and "element" not in n)
    assert plan_reality.element_of(card, graph["nodes"], graph["edges"])["id"] == "el-form"
    live = plane.get("/api/oporahub/live-card", params={**SCOPE, "nodeId": card["id"]}, headers=HEADERS).json()
    assert live["flow"]["elementId"] == "el-form" and live["flow"]["outputs"] == ["Odeslaná poptávka"]
    assert live["flow"]["pageId"] == "home"
    assert live["truths"]["vision"]["items"][0]["text"] == "- Odeslaná poptávka"  # kritéria = text spec.acceptance
    known = plan_reality.facts(service, SCOPE["project"], SCOPE["workspace"])
    flow = plan_reality.flow_of(service, SCOPE["project"], plan_reality.element_of(card, known["nodes"], known["edges"]))
    expected = plan_reality.expectations(card["id"], known["nodes"], [], flow)
    assert {"kind": "output", "name": "Odeslaná poptávka", "path": None, "line": None, "source": "flow.outputs"} in expected
    again = build(plane).json()
    assert again["proposal"] is None and again["counts"] == {"areas": 0, "cards": 0, "edges": 0}
    assert again["existing"] == {"frames": 1, "areas": 3, "cards": 2}


def test_build_needs_page_and_exact_body(plane):
    assert build(plane, "el-form").status_code == 404
    assert plane.post("/api/page-plan/home/build-plan", headers=HEADERS, json={**SCOPE, "x": 1}).status_code == 422
