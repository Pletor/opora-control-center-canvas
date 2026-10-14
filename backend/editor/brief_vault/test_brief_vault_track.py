"""Dvě stopy schránky (docs/navrh-schranka-zadani.md, „Dvě stopy a levé menu“): kořen nese stopu vždy,
dítě ji dědí, `set-track` přeřadí podstrom novou revizí se stejným textem, filtr stromu nechá cestu
ke kořeni, stará databáze dostane sloupec a její fragmenty jsou „nezařazené“, node-brief nese
`effectiveTrack` a uložená verze plátna stopu nese (starší verze zůstanou platné)."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.brief_vault.brief_vault_model import MAX_DEPTH, effective_tracks, latest_rows
from backend.editor.brief_vault.brief_vault_tree import tree_of
from backend.editor.node.test_removals import HEADERS, ORIGIN, SCOPE, install_graph, node
from database.schema import project_schema
from database.schema.project_schema import add_column, ensure_brief_fragment_columns, ensure_canvas_version_columns

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=track-1"}
TEXT = "3.1 Tabulky\nřádky.\n\n3.2 Obrazovka\nseznam."


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector"), node("c1", "s1")], "edges": []})
        client.app_state = app.state
        yield client


def post(client, expect=200, headers=AGENT, **body):
    response = client.post("/api/brief-vault", headers=headers, json={**SCOPE, **body})
    assert response.status_code == expect, response.text
    return response.json()


def tree(client, **params):
    response = client.get("/api/brief-vault", params={**SCOPE, **params})
    assert response.status_code == 200, response.text
    return response.json()["roots"]


def nodes(roots):
    found, stack = {}, list(roots)
    while stack:
        item = stack.pop()
        found[item["id"]] = item
        stack.extend(item["children"])
    return found


def split_root(client, track="logic"):
    root = post(client, op="create", scopeNodeId="s1", track=track, title="3. VRSTVA", text=TEXT)["fragment"]
    children = post(client, op="split", fragmentId=root["id"], expectedRevision=1, splitter="heading-number")["children"]
    return root, children


def revisions(client, fragment_id):
    db = client.app_state.service.db_for("draft")
    return [tuple(row) for row in db.execute("SELECT revision, text, track FROM brief_fragment_revisions"
                                             " WHERE fragment_id=? ORDER BY revision", (fragment_id,))]


def test_root_needs_track_and_child_inherits(client):
    missing = client.post("/api/brief-vault", headers=AGENT, json={**SCOPE, "op": "create", "scopeNodeId": "s1",
                                                                   "title": "T", "text": "t"})
    assert missing.status_code == 400 and "kořen" in missing.json()["error"]
    for broken in (None, "design", ""):
        post(client, expect=400, op="create", scopeNodeId="s1", track=broken, title="T", text="t")
    assert tree(client) == []
    root, (first, second) = split_root(client)
    child = post(client, op="create", parentId=root["id"], title="Výjimka", text="UI", track="ux")["fragment"]
    assert root["track"] == "logic" and first["track"] is None and child["track"] == "ux"
    found = nodes(tree(client))
    assert found[root["id"]]["effectiveTrack"] == "logic" and found[first["id"]]["effectiveTrack"] == "logic"
    assert found[first["id"]]["track"] is None and found[child["id"]]["effectiveTrack"] == "ux"
    research = post(client, op="research", fragmentId=second["id"], title="Ověřit", text="")["fragment"]
    assert research["track"] is None and nodes(tree(client))[research["id"]]["effectiveTrack"] == "logic"


def test_revisions_keep_track(client):
    root, (first, _) = split_root(client, "ux")
    post(client, op="set-track", fragmentId=first["id"], expectedRevision=1, track="logic", note="Datový model.")
    revised = post(client, op="revise", fragmentId=first["id"], expectedRevision=2, text="3.1 Tabulky\nnové.",
                   note="upřesnění")["fragment"]
    proposed = post(client, op="propose-mvp", fragmentIds=[first["id"]])["changed"][0]
    assert revised["track"] == "logic" and proposed["track"] == "logic"
    post(client, headers=HEADERS, op="restore", fragmentId=first["id"], expectedRevision=4, revision=1, note="zpět")
    assert revisions(client, first["id"])[-1] == (5, "3.1 Tabulky\nřádky.", "logic")
    assert post(client, op="revise", fragmentId=root["id"], expectedRevision=1, title="3. Vrstva",
                note="název")["fragment"]["track"] == "ux"


def test_set_track_moves_subtree_with_cas_and_same_text(client):
    root, (first, second) = split_root(client)
    deep = post(client, op="create", parentId=first["id"], title="3.1.1", text="detail")["fragment"]
    post(client, expect=409, op="set-track", fragmentId=first["id"], expectedRevision=0, track="ux", note="staré")
    moved = post(client, op="set-track", fragmentId=first["id"], expectedRevision=1, track="ux",
                 note="Obrazovka, ne logika.")["fragment"]
    assert moved["revision"] == 2 and moved["track"] == "ux" and moved["by"] == "track-1"
    assert revisions(client, first["id"]) == [(1, "3.1 Tabulky\nřádky.", None), (2, "3.1 Tabulky\nřádky.", "ux")]
    found = nodes(tree(client))
    assert found[deep["id"]]["effectiveTrack"] == "ux" and found[second["id"]]["effectiveTrack"] == "logic"
    post(client, expect=409, op="set-track", fragmentId=first["id"], expectedRevision=2, track="ux", note="znovu")
    post(client, expect=409, op="set-track", fragmentId=first["id"], expectedRevision=2, track="logic", note="")
    post(client, expect=400, op="set-track", fragmentId=root["id"], expectedRevision=1, track=None, note="pryč")
    back = post(client, headers=HEADERS, op="set-track", fragmentId=first["id"], expectedRevision=2, track=None,
                note="Zpět na dědění.")["fragment"]
    assert back["track"] is None and nodes(tree(client))[deep["id"]]["effectiveTrack"] == "logic"
    assert len(revisions(client, first["id"])) == 3


def test_filter_keeps_path_to_root_and_recounts_coverage(client):
    root, (first, second) = split_root(client)
    post(client, op="set-track", fragmentId=second["id"], expectedRevision=1, track="ux", note="UI")
    ux = tree(client, track="ux")
    assert [item["id"] for item in ux] == [root["id"]]
    assert [item["id"] for item in ux[0]["children"]] == [second["id"]] and ux[0]["coverage"]["leaves"] == 1
    logic = tree(client, track="logic")[0]
    assert [item["id"] for item in logic["children"]] == [first["id"]] and logic["coverage"]["leaves"] == 1
    assert tree(client, track="none") == [] and tree(client)[0]["coverage"]["leaves"] == 2
    bad = client.get("/api/brief-vault", params={**SCOPE, "track": "design"})
    assert bad.status_code == 400


def test_effective_tracks_without_recursion_and_cycle():
    rows = {"r": {"parent_id": None, "track": "ux"}, "a": {"parent_id": "r", "track": None},
            "b": {"parent_id": "a", "track": "logic"}, "c": {"parent_id": "b", "track": None},
            "x": {"parent_id": "y", "track": None}, "y": {"parent_id": "x", "track": None}, "o": {"parent_id": "chybí", "track": None}}
    chain = {f"d{n}": {"parent_id": f"d{n - 1}" if n else "r", "track": None} for n in range(5000)}
    tracks = effective_tracks({**rows, **chain})
    assert {key: tracks[key] for key in rows} == {"r": "ux", "a": "ux", "b": "logic", "c": "logic", "x": None, "y": None, "o": None}
    assert tracks["d4999"] == "ux"


def test_old_database_gets_column_and_rows_are_unassigned(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector")], "edges": []})
        root = post(client, op="create", scopeNodeId="s1", track="ux", title="Staré", text="t")["fragment"]
        path = client.app.state.service.folder("draft").database
    db = sqlite3.connect(path)  # databáze z doby před stopami: sloupec track neexistuje
    db.execute("ALTER TABLE brief_fragment_revisions DROP COLUMN track")
    db.commit()
    db.close()
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        found = tree(client)[0]
        assert found["id"] == root["id"] and found["track"] is None and found["effectiveTrack"] is None
        assert [item["id"] for item in tree(client, track="none")] == [root["id"]] and tree(client, track="ux") == []
        moved = post(client, op="set-track", fragmentId=root["id"], expectedRevision=1, track="logic", note="Zařazeno.")
        assert moved["fragment"]["track"] == "logic"
    db = sqlite3.connect(path)
    assert db.execute("SELECT revision, track FROM brief_fragment_revisions ORDER BY revision").fetchall() == [(1, None), (2, "logic")]
    ensure_brief_fragment_columns(db)  # idempotentní
    assert [row[1] for row in db.execute("PRAGMA table_info(brief_fragment_revisions)")].count("track") == 1
    db.close()


def test_node_brief_carries_effective_track(client):
    _root, (first, _) = split_root(client)
    digest = client.get("/api/view", params=SCOPE).json()["digest"]
    current = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
    planned = client.post("/api/canvas-plan", headers=AGENT, json={**SCOPE, "digest": digest, "dryRun": False, "plan": {
        "extend": [{"node": "@c1", "expectedRevision": current, "fragmentRef": [{"fragmentId": first["id"]}]}]}})
    assert planned.status_code == 200, planned.text
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()["fragments"]
    assert brief["items"][0]["effectiveTrack"] == "logic"
    post(client, op="set-track", fragmentId=first["id"], expectedRevision=1, track="ux", note="UI")
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()["fragments"]
    assert brief["items"][0]["effectiveTrack"] == "ux" and brief["items"][0]["changedSinceInsert"] is False


def test_canvas_version_carries_track(client):
    from backend.editor.canvas_versions.test_canvas_versions import digest, save, versions
    _root, (first, _) = split_root(client)
    saved = save(client).json()["version"]
    post(client, op="set-track", fragmentId=first["id"], expectedRevision=1, track="ux", note="UI")
    assert versions(client)["dirty"] is True
    restored = client.post("/api/canvas-versions/restore", headers=HEADERS, json={
        **SCOPE, "versionId": saved["id"], "digest": digest(client), "author": "test",
        "expectedToken": versions(client)["currentToken"]})
    assert restored.status_code == 200, restored.text
    assert nodes(tree(client))[first["id"]]["track"] is None and revisions(client, first["id"])[-1][2] is None
    assert versions(client)["dirty"] is False


def test_version_saved_before_tracks_keeps_digest_and_restores():
    from backend.editor.canvas_versions.version_content import (
        STORES,
        content_digest,
        empty_data,
        validate_records,
        with_later_stores,
    )
    old = {key: value for key, value in empty_data("briefFragments").items() if key != "track"}
    row = {**old, "parent_id": None, "scope_node_id": "", "ord": 1, "title": "T", "text": "t", "actor": "agent", "deleted": 0}
    records = {name: [] for name in STORES}
    records["briefFragments"] = [{"key": ["f1"], "revision": 1, "data": row}, {"key": ["f2"], "revision": 2, "data": old}]
    before = {"records": records, "assets": []}
    upgraded = {"records": with_later_stores(records), "assets": []}
    assert upgraded["records"]["briefFragments"][0]["data"]["track"] is None
    assert content_digest({}, {}, before) == content_digest({}, {}, upgraded)
    validate_records(upgraded["records"], "draft", "main")


def test_tree_helpers_on_rows_without_tracks():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE brief_fragment_revisions(project_id TEXT, workspace_id TEXT, fragment_id TEXT, revision INTEGER,"
               " parent_id TEXT, scope_node_id TEXT, ord INTEGER, kind TEXT, title TEXT, text TEXT, stage TEXT, mvp TEXT,"
               " note TEXT, by TEXT, actor TEXT, deleted INTEGER, saved_at TEXT)")
    db.execute("INSERT INTO brief_fragment_revisions VALUES('p','w','r',1,NULL,'',1,'brief','R','t','draft','none','','a','agent',0,'T')")
    ensure_brief_fragment_columns(db)
    ensure_brief_fragment_columns(db)
    roots = tree_of(latest_rows(db, "p", "w"), {})
    assert roots[0]["track"] is None and roots[0]["effectiveTrack"] is None
    rows = latest_rows(db, "p", "w")
    assert tree_of(rows, {}, track="none")[0]["id"] == "r" and tree_of(rows, {}, track="logic") == []


def _row(fragment_id, parent, track=None, kind="brief"):
    return {"fragment_id": fragment_id, "revision": 1, "parent_id": parent, "scope_node_id": "" if parent is None else None,
            "ord": 1, "kind": kind, "title": fragment_id, "text": "t", "stage": "draft", "mvp": "none", "note": "", "by": "a",
            "actor": "agent", "deleted": 0, "saved_at": "T", "track": track}


def test_filter_reaches_below_depth_limit_and_counts_only_its_track():
    """Fragment stopy hlouběji než strop hloubky nezmizí; pokrytí a hidden se počítají nad úplnými řádky."""
    rows = {"r": _row("r", None, "logic"), "side": _row("side", "r")}
    parent = "r"
    for index in range(MAX_DEPTH + 3):  # řetěz logic pod strop, na jeho konci list ux
        rows[f"d{index}"] = _row(f"d{index}", parent)
        parent = f"d{index}"
    rows["ux"] = _row("ux", parent, "ux")
    rows["logicleaf"] = _row("logicleaf", parent)
    ux = tree_of(rows, {}, track="ux")
    assert [root["id"] for root in ux] == ["r"] and ux[0]["coverage"]["leaves"] == 1
    assert [kid["id"] for kid in ux[0]["children"]] == ["d0"]
    cursor, depth = ux[0], 1
    while cursor["children"]:
        cursor, depth = cursor["children"][0], depth + 1
    assert depth == MAX_DEPTH and cursor["children"] == [] and cursor["hidden"] == 5 and cursor["coverage"]["leaves"] == 1
    logic = tree_of(rows, {}, track="logic")[0]
    assert logic["coverage"]["leaves"] == 2 and tree_of(rows, {})[0]["coverage"]["leaves"] == 3
    assert tree_of(rows, {}, track="none") == []


def test_add_column_tolerates_concurrent_duplicate_only(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE brief_fragment_revisions(fragment_id TEXT)")
    db.execute("CREATE TABLE canvas_versions(id TEXT, project_id TEXT, workspace_id TEXT)")
    add_column(db, "brief_fragment_revisions", "track")
    add_column(db, "brief_fragment_revisions", "track")  # souběžný proces sloupec už přidal
    with pytest.raises(sqlite3.OperationalError):
        add_column(db, "neexistuje", "track")
    # Druhý proces přečetl PRAGMA dřív, než první sloupce přidal: ALTER spadne na duplicitu a projde.
    ensure_canvas_version_columns(db)
    stale = {"brief_fragment_revisions": {"fragment_id"}, "canvas_versions": {"id", "project_id", "workspace_id"}}
    real = project_schema._columns
    monkeypatch.setattr(project_schema, "_columns", lambda db, table: stale.pop(table, None) or real(db, table))
    ensure_brief_fragment_columns(db)
    ensure_canvas_version_columns(db)
    assert {"snapshot", "content_digest"} <= real(db, "canvas_versions") and "track" in real(db, "brief_fragment_revisions")
