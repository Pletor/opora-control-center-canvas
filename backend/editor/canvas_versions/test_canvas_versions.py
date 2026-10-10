"""Uložené verze plátna (docs/verze-platna.md): seznam, dirty, uložení a obnovení grafu i stavu."""

import re

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.canvas_versions.canvas_versions import LIST_SQL, SAME_CONTENT_SQL, SNAPSHOT_SQL, _summary
from backend.editor.node.test_removals import (
    HEADERS,
    ORIGIN,
    SCOPE,
    desktop_state,
    install_desktop_state,
    install_graph,
    node,
    state_node,
)

AUTHOR = "Místní uživatel"


def graph(*ids):
    return {"nodes": [node(key) for key in ids], "edges": []}


def versions(client, **scope):
    response = client.get("/api/canvas-versions", params=scope or SCOPE)
    assert response.status_code == 200, response.text
    return response.json()


def digest(client):
    return client.get("/api/view", params=SCOPE).json()["digest"]


def save(client, author=AUTHOR, value=None):
    return client.post(
        "/api/canvas-versions", headers=HEADERS,
        json={**SCOPE, "digest": digest(client) if value is None else value, "author": author},
    )


def restore(client, version_id, author=AUTHOR, value=None):
    return client.post(
        "/api/canvas-versions/restore", headers=HEADERS,
        json={**SCOPE, "versionId": version_id, "digest": digest(client) if value is None else value,
              "author": author, "expectedToken": versions(client)["currentToken"]},
    )


def current_state(client):
    return client.get("/api/desktop-v3/state", params=SCOPE).json()


def test_empty_canvas_has_no_versions_and_is_clean(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        listed = versions(client)
        assert listed["versions"] == [] and listed["dirty"] is False and listed["currentToken"]


def test_non_empty_canvas_without_version_is_dirty_and_save_cleans_it(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a", "b"))
        assert versions(client)["dirty"] is True
        saved = save(client, author="  Jana  ")
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["dirty"] is False
        assert body["version"]["author"] == "Jana" and body["version"]["nodeCount"] == 2
        assert set(body["version"]) == {"id", "createdAt", "author", "nodeCount", "coverage", "unavailableAssets", "actor", "changedCardCount"}
        listed = versions(client)
        assert listed == {"versions": [body["version"]], "dirty": False, "currentToken": body["currentToken"]}


def test_graph_change_and_state_change_make_canvas_dirty(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        assert save(client).status_code == 200
        install_graph(client, graph("a", "b"))
        assert versions(client)["dirty"] is True
        assert save(client).status_code == 200
        assert versions(client)["dirty"] is False
        install_desktop_state(client, desktop_state(nodes={"a": state_node()}))
        assert versions(client)["dirty"] is True
        second = save(client).json()["version"]
        listed = versions(client)
        assert listed["dirty"] is False and listed["versions"][0] == second and len(listed["versions"]) == 3


def test_restore_returns_graph_and_state_and_saves_dirty_canvas_first(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a", "b"))
        old_state = desktop_state(nodes={"a": state_node(), "b": state_node()})
        install_desktop_state(client, old_state)
        version = save(client).json()["version"]
        # Po verzi: uzel b zmizí (krok zpět plátna), přibude c a stav se změní.
        view = client.get("/api/view", params=SCOPE).json()
        removed = client.post("/api/graph", headers=HEADERS, json={
            **SCOPE, "graph": graph("a"), "digest": view["digest"], "undo": True})
        assert removed.status_code == 200, removed.text
        install_graph(client, graph("a", "c"))
        revision = current_state(client)["revision"]
        changed = client.post("/api/desktop-v3/state", headers=HEADERS, json={
            **SCOPE, "expectedRevision": revision, "state": desktop_state(nodes={"c": state_node()})})
        assert changed.status_code == 200, changed.text
        assert versions(client)["dirty"] is True

        result = restore(client, version["id"], author="Jana")
        assert result.status_code == 200, result.text
        assert [n["id"] for n in result.json()["view"]["graph"]["nodes"]] == ["a", "b"]
        assert current_state(client)["state"] == old_state
        listed = versions(client)
        # Obnovené plátno přesně odpovídá obnovené verzi, takže je čisté.
        assert listed["dirty"] is False
        assert [item["author"] for item in listed["versions"]] == ["Jana (před obnovením)", AUTHOR]
        assert listed["versions"][0]["nodeCount"] == 2

        # Automatická verze vrátí stav před obnovením (c zpět, b pryč).
        back = restore(client, listed["versions"][0]["id"])
        assert back.status_code == 200, back.text
        assert [n["id"] for n in back.json()["view"]["graph"]["nodes"]] == ["a", "c"]
        assert current_state(client)["state"] == desktop_state(nodes={"c": state_node()})


def test_restore_of_clean_canvas_adds_no_automatic_version(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        first = save(client).json()["version"]
        install_graph(client, graph("a", "b"))
        assert save(client).status_code == 200
        assert restore(client, first["id"]).status_code == 200
        assert len(versions(client)["versions"]) == 2


def test_wrong_digest_unknown_version_and_bad_payload_are_rejected(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        stale = save(client, value="0" * 64)
        assert stale.status_code == 409 and "změnilo" in stale.json()["error"]
        version = save(client).json()["version"]
        refused = restore(client, version["id"], value="0" * 64)
        assert refused.status_code == 409 and "změnilo" in refused.json()["error"]
        unknown = restore(client, "f" * 32)
        assert unknown.status_code == 409 and unknown.json()["error"] == "Verze plátna neexistuje."
        malformed = restore(client, "../x")
        assert malformed.status_code == 409 and malformed.json()["error"] == "Neplatná verze plátna."
        for author in ("", "   ", "x" * 121, 5):
            response = save(client, author=author)
            assert response.status_code == 409 and "Autor verze" in response.json()["error"]
        extra = client.post("/api/canvas-versions", headers=HEADERS,
                            json={**SCOPE, "digest": digest(client), "author": AUTHOR, "x": 1})
        assert extra.status_code == 409
        assert len(versions(client)["versions"]) == 1


def test_version_from_other_workspace_is_unknown(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        version = save(client).json()["version"]
        db = app.state.service.db_for("draft")
        db.execute("UPDATE canvas_versions SET workspace_id='other' WHERE id=?", (version["id"],))
        db.commit()
        response = restore(client, version["id"])
        assert response.status_code == 409 and response.json()["error"] == "Verze plátna neexistuje."
        assert versions(client)["versions"] == []


def test_main_is_read_only(tmp_path, monkeypatch):
    app = create_app(tmp_path / "data")
    service = app.state.service
    service.register_repository("p", "Project", str(tmp_path / "repo"), "fixture://p", "main")
    service.db.commit()

    def fake_git(_root, *args, **_kwargs):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("branch", "--show-current"):
            return "main"
        return None

    monkeypatch.setattr("backend.canvas.canvas_service.git", fake_git)
    scope = {"project": "p", "workspace": "main"}
    with TestClient(app, base_url=ORIGIN) as client:
        view = client.get("/api/view", params=scope).json()
        listed = versions(client, **scope)
        assert listed["versions"] == [] and listed["dirty"] is False and listed["currentToken"]
        saved = client.post("/api/canvas-versions", headers=HEADERS,
                            json={**scope, "digest": view["digest"], "author": AUTHOR})
        assert saved.status_code == 409 and "Main je pouze pro čtení" in saved.json()["error"]
        restored = client.post("/api/canvas-versions/restore", headers=HEADERS,
                               json={**scope, "versionId": "f" * 32, "digest": view["digest"], "author": AUTHOR,
                                     "expectedToken": listed["currentToken"]})
        assert restored.status_code == 409 and "Main je pouze pro čtení" in restored.json()["error"]


def _raw_columns(sql):
    """Sloupce verze, které dotaz na canvas_versions vrací do Pythonu (mimo json_* / typeof v SQL)."""
    select = sql[sql.upper().index("SELECT") + 6:sql.index("FROM canvas_versions")]
    previous = None
    while previous != select:
        previous, select = select, re.sub(r"(json_\w+|typeof|count)\([^()]*\)", "", select)
    return set(re.findall(r"\b(?:graph|state|snapshot)\b|\*", select))


def test_list_reads_metadata_in_sql_and_matches_full_row_summary(tmp_path):
    from backend.editor.canvas_versions.test_version_content import seed

    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        db = app.state.service.db_for("draft")
        install_graph(client, graph("a"))
        assert save(client).status_code == 200
        # Chybějící příloha i obrázek kresby = dvě nedostupná aktiva ve snímku.
        install_desktop_state(client, desktop_state(nodes={"a": state_node(materials=[{
            "id": "m", "kind": "upload", "path": "20261005-101010-12345678.png", "caption": "x"}])}))
        seed(db, "drawings", {"scene": {"elements": [
            {"id": "i", "type": "image", "fileId": "gone", "x": 0, "y": 0, "width": 1, "height": 1}]}})
        install_graph(client, graph("a", "b"))
        assert save(client, author="Agent").status_code == 200
        db.execute("INSERT INTO canvas_versions(id,project_id,workspace_id,author,created_at,graph,state,graph_digest,state_digest)"
                   " VALUES(?,?,?,?,?,?,?,?,?)", ("0" * 32, "draft", "draft", "Starý", "2026-01-01T00:00:00+00:00",
                                                  '{"nodes":[{"id":"x"}],"edges":[]}', "{}", "g", "s"))
        db.commit()
        statements = []
        db.set_trace_callback(statements.append)
        listed = versions(client)["versions"]
        db.set_trace_callback(None)

        rows = db.execute("SELECT * FROM canvas_versions ORDER BY created_at DESC,rowid DESC").fetchall()
        assert listed == [_summary(row) for row in rows]
        assert [item["unavailableAssets"] for item in listed] == [2, 0, 0]
        assert [item["coverage"] for item in listed] == ["full", "full", "legacy-partial"]
        assert [item["nodeCount"] for item in listed] == [2, 1, 1]
        version_reads = [sql for sql in statements if "FROM canvas_versions" in sql]
        assert any("json_each(snapshot" in sql for sql in version_reads)
        assert all(_raw_columns(sql) == set() for sql in version_reads), version_reads

        # Řádek verze se nemění: druhý výpis už snímky neparsuje, výsledek je stejný.
        statements.clear()
        db.set_trace_callback(statements.append)
        assert versions(client)["versions"] == listed
        db.set_trace_callback(None)
        assert not any("json_each" in sql or "json_extract" in sql for sql in statements)


def test_raw_column_detector_flags_blob_reads():
    assert _raw_columns("SELECT * FROM canvas_versions") == {"*"}
    assert _raw_columns("SELECT id,graph,snapshot FROM canvas_versions") == {"graph", "snapshot"}
    assert _raw_columns(LIST_SQL) == set() and _raw_columns(SNAPSHOT_SQL) == set()


def test_dirty_lookup_uses_content_digest_index(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN):
        db = app.state.service.db_for("draft")
        plan = " ".join(row["detail"] for row in db.execute("EXPLAIN QUERY PLAN " + SAME_CONTENT_SQL, ("draft", "draft", "x")))
        assert "canvas_versions_content" in plan, plan
