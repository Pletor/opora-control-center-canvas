"""`order` srdce na stránkách sdílené architektury přes skutečnou aplikaci (docs/navrhy/2026-10-31-poradi-karty.md §4):
srdce zapíše do `/api/project-architecture` jen pole `order` (a jen při plné autonomii projektu), pak plán prostoru
převezme architekturu návrhem s `adoptArchitectureContext`. Jiný zápis srdce do architektury server odmítne; člověk
zapisuje beze změny."""
from backend.api.brain_opora.test_heart_plan import heart, plan
from backend.api.brain_opora.test_heart_steps import autonomy
from backend.brain_opora.heart import opora_heart
from backend.canvas.test_canvas_plan import HEADERS, SCOPE
from backend.canvas.test_project_architecture import domain, page

__all__ = ["heart"]
ARCH = "/api/project-architecture"
PROPOSALS = opora_heart.GRAPH_PROPOSALS
PROJECT = {"project": SCOPE["project"]}


def order(*flags):
    try:
        return opora_heart.run(opora_heart.parser().parse_args(["order", *flags]))
    except opora_heart.Failure as failure:
        return failure.payload


def human_write(client, graph, revision):
    """Zápis člověka s dokladem UI (jako `autonomy`); srdce pak zase běží bez cookies."""
    client.get("/api/access/ui-session", headers={**HEADERS, "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors"})
    response = client.post(ARCH, headers=HEADERS, json={**SCOPE, "expectedRevision": revision, "graph": graph})
    client.cookies.clear()
    return response


def human_architecture(client):
    """Člověk uloží doménu se dvěma stránkami (bez `order`)."""
    graph = {"nodes": [domain("app"), page("p_home", path="/"), page("p_faq", path="/faq")], "edges": []}
    response = human_write(client, graph, 0)
    assert response.status_code == 200, response.text
    return response.json()


def node_order(graph, node):
    return next(item for item in graph["nodes"] if item["id"] == node).get("order")


def write(call, graph, revision):
    try:
        return call("POST", ARCH, {**SCOPE, "expectedRevision": revision, "graph": graph})
    except opora_heart.Failure as failure:
        return failure.payload


def test_heart_orders_pages_in_the_architecture_and_adopts_them_into_the_plan(heart):
    client, call, tmp_path = heart
    human_architecture(client)
    refs = plan(tmp_path, opora_heart.PLAN_EXAMPLE)["refs"]
    autonomy(client, True)
    dry = order("--nodes", f"p_home=101,p_faq=102,{refs['mvp']}=201", "--dry-run")
    assert dry["architecture"] == {"revision": 1, "changes": [{"id": "p_home", "from": None, "to": 101},
                                                              {"id": "p_faq", "from": None, "to": 102}]}, dry
    assert call("GET", ARCH, query=PROJECT)["revision"] == 1  # dry-run nic neposlal
    done = order("--nodes", f"p_home=101,p_faq=102,{refs['mvp']}=201")
    assert done["accepted"] is True and done["proposalId"] and done["adoptArchitecture"] is True, done
    assert done["architecture"]["revision"] == 2 and done["changes"] == [{"id": refs["mvp"], "from": None, "to": 201}]
    stored = call("GET", ARCH, query=PROJECT)
    assert (stored["revision"], node_order(stored["graph"], "p_home"), node_order(stored["graph"], "p_faq")) == (2, 101, 102)
    context = call("GET", f"{PROPOSALS}/context", query=SCOPE)
    assert context["architectureContext"]["differs"] is False  # plán prostoru architekturu převzal
    assert node_order(context["acceptedGraph"], "p_home") == 101 and node_order(context["acceptedGraph"], refs["mvp"]) == 201


def test_heart_architecture_write_needs_full_autonomy(heart):
    client, call, _ = heart
    human_architecture(client)
    done = order("--nodes", "p_home=101")
    assert (done["status"], done["code"]) == (403, "heart_architecture_autonomy"), done
    assert call("GET", ARCH, query=PROJECT)["revision"] == 1


def test_heart_architecture_write_may_change_only_order(heart):
    client, call, _ = heart
    stored = human_architecture(client)
    autonomy(client, True)
    graph = stored["graph"]
    renamed = {**graph, "nodes": [{**node, "name": "Jinak"} if node["id"] == "p_faq" else node for node in graph["nodes"]]}
    dropped = {**graph, "nodes": graph["nodes"][:2]}
    for bad in (renamed, dropped, {**renamed, "nodes": [{**node, "order": 5} for node in renamed["nodes"]]}):
        refused = write(call, bad, 1)
        assert (refused["status"], refused["code"]) == (422, "heart_architecture_scope"), refused
    assert call("GET", ARCH, query=PROJECT)["revision"] == 1
    ordered = {**graph, "nodes": [{**node, "order": 101} if node["id"] == "p_faq" else node for node in graph["nodes"]]}
    assert write(call, ordered, 0)["status"] == 409  # souběžná změna: nic nepřepíše
    assert write(call, ordered, 1)["revision"] == 2


def test_human_architecture_write_is_unchanged(heart):
    client, _, _ = heart
    stored = human_architecture(client)
    graph = {**stored["graph"], "nodes": stored["graph"]["nodes"][:2]}
    response = human_write(client, graph, 1)
    assert response.status_code == 200 and response.json()["revision"] == 2, response.text
