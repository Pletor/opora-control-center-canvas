"""ETag/304 pro state, view, canvas-index a canvas-versions (karta P3, blok 2).

Druhý GET se stejným If-None-Match vrátí 304 bez těla; zápis, obnova verze i jiný projekt dají
jiný ETag a celé tělo. ETag je jen otisk identity obsahu, nic z obsahu z něj nejde vyčíst.
"""
import re

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.canvas_versions.test_canvas_versions import graph, restore, save
from backend.editor.node.test_removals import (
    HEADERS,
    ORIGIN,
    SCOPE,
    desktop_state,
    install_desktop_state,
    install_graph,
)

TAG = re.compile(r'^"[0-9a-f]{40}"$')
READS = [("/api/desktop-v3/state", {}), ("/api/view", {}), ("/api/canvas-index", {"q": ""}),
         ("/api/canvas-versions", {}), ("/api/canvas-versions/head", {})]


def tags(client, scope=SCOPE):
    out = {}
    for url, extra in READS:
        response = client.get(url, params={**scope, **extra})
        assert response.status_code == 200, (url, response.text)
        assert TAG.match(response.headers["etag"]), (url, response.headers.get("etag"))
        assert response.headers["cache-control"] == "no-store"
        out[url] = response.headers["etag"]
    return out


def conditional(client, url, tag, scope=SCOPE, **extra):
    return client.get(url, params={**scope, **extra}, headers={"If-None-Match": tag})


def test_unchanged_reads_answer_304_without_body(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a", "b"))
        first = tags(client)
        for url, extra in READS:
            response = conditional(client, url, first[url], **extra)
            assert response.status_code == 304, (url, response.text)
            assert response.content == b"" and response.headers["etag"] == first[url]
            # Seznam, slabý ETag i * odpovídají stejně (RFC 9110); cizí ETag ne.
            assert conditional(client, url, f'"x", W/{first[url]}', **extra).status_code == 304
            assert conditional(client, url, "*", **extra).status_code == 304
            assert conditional(client, url, '"' + "0" * 40 + '"', **extra).status_code == 200
        assert tags(client) == first


def test_state_write_changes_state_index_and_versions_tags(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        first = tags(client)
        install_desktop_state(client, desktop_state(nodes={"a": {"phase": "define", "criteria": [], "steps": []}}))
        second = tags(client)
        for url in ("/api/desktop-v3/state", "/api/canvas-index", "/api/canvas-versions", "/api/canvas-versions/head"):
            assert second[url] != first[url], url
            fresh = conditional(client, url, first[url], **dict(READS)[url])
            assert fresh.status_code == 200 and fresh.headers["etag"] == second[url]
        assert second["/api/view"] == first["/api/view"]  # graf se nezměnil
        assert client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]["a"]["phase"] == "define"


def test_graph_change_save_and_restore_give_new_tags_and_fresh_content(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        assert save(client).status_code == 200
        saved = tags(client)
        head = client.get("/api/canvas-versions/head", params=SCOPE).json()
        assert head["dirty"] is False and head == {key: client.get("/api/canvas-versions", params=SCOPE).json()[key]
                                                   for key in ("currentToken", "dirty")}
        install_graph(client, graph("a", "b"))
        changed = tags(client)
        assert all(changed[url] != saved[url] for url in ("/api/view", "/api/canvas-versions", "/api/canvas-versions/head"))
        assert client.get("/api/canvas-versions/head", params=SCOPE).json()["dirty"] is True
        version = client.get("/api/canvas-versions", params=SCOPE).json()["versions"][0]
        assert restore(client, version["id"]).status_code == 200
        restored = tags(client)
        assert restored["/api/view"] != changed["/api/view"]
        assert [n["id"] for n in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]] == ["a"]
        assert conditional(client, "/api/view", changed["/api/view"]).status_code == 200
        listed = client.get("/api/canvas-versions", params=SCOPE).json()
        assert listed["dirty"] is False and len(listed["versions"]) == 2  # automatická verze „před obnovením“


def test_index_tag_depends_on_query_and_limit(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a", "b"))
        base = client.get("/api/canvas-index", params={**SCOPE, "q": "a"})
        other = client.get("/api/canvas-index", params={**SCOPE, "q": "b"})
        limited = client.get("/api/canvas-index", params={**SCOPE, "q": "a", "limit": 1})
        assert len({base.headers["etag"], other.headers["etag"], limited.headers["etag"]}) == 3
        assert conditional(client, "/api/canvas-index", base.headers["etag"], q="b").status_code == 200


def test_projects_with_the_same_revision_never_share_a_tag(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        one = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jedna", "confirmed": True}).json()["id"]
        two = client.post("/api/empty-project", headers=HEADERS, json={"name": "Dvě", "confirmed": True}).json()["id"]
        first, second = tags(client, {"project": one, "workspace": "draft"}), tags(client, {"project": two, "workspace": "draft"})
        for url, extra in READS:
            assert first[url] != second[url], url
            cross = conditional(client, url, first[url], {"project": two, "workspace": "draft"}, **extra)
            assert cross.status_code == 200, url
