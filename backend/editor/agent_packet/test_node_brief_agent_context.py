"""node-brief nese `card.fetch` a `card.fill` z knihovny (`docs/zive-zobrazeni-a-knihovna.md` §5) jen když jsou,
v `node` a mimo `specification`: přidání ani změna `contextVersion` nemění."""

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_packet.test_node_brief import GRAPH, HEADERS, ORIGIN, SCOPE, brief


def save(client, card):
    nodes = [{**item, "card": card} if item["id"] == "focus" and card else item for item in GRAPH["nodes"]]
    view = client.get("/api/view", params=SCOPE).json()
    saved = client.post("/api/graph", headers=HEADERS,
                        json={**SCOPE, "graph": {"nodes": nodes, "edges": GRAPH["edges"]}, "digest": view["digest"]})
    assert saved.status_code == 200, saved.text
    return brief(client).json()


def own(data):
    return next(item for item in data["specification"]["graph"]["nodes"] if item["id"] == "focus")


def test_fetch_and_fill_appear_only_when_set_and_keep_the_context_version(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        plain = save(client, {"layer": "frontend"})
        assert "fetch" not in plain["node"] and "fill" not in plain["node"]
        fetch = {"files": ["docs/pravidla-struktury.md"], "docs": ["https://example.org/forms"]}
        context = save(client, {"layer": "frontend", "fetch": fetch, "fill": ["sourceRef", "spec.acceptance"]})
        assert context["node"]["fetch"] == fetch
        assert context["node"]["fill"] == ["sourceRef", "spec.acceptance"]
        assert "fetch" not in own(context) and "fill" not in own(context)
        assert context["contextVersion"] == plain["contextVersion"]
        assert save(client, {"layer": "frontend", "fill": ["text"]})["contextVersion"] == plain["contextVersion"]


def test_bad_fill_is_refused_by_the_graph_save(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        nodes = [{**item, "card": {"fill": ["name"]}} if item["id"] == "focus" else item for item in GRAPH["nodes"]]
        view = client.get("/api/view", params=SCOPE).json()
        saved = client.post("/api/graph", headers=HEADERS,
                            json={**SCOPE, "graph": {"nodes": nodes, "edges": GRAPH["edges"]}, "digest": view["digest"]})
        assert saved.status_code >= 400
