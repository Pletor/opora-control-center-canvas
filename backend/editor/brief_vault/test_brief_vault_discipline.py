"""Disciplíny schránky (docs/schranka-neurony.md §2, §9 bod 5): kořen nese disciplínu vždy, dítě ji dědí,
`set-discipline` přeřadí podstrom novou revizí se stejným textem, filtr stromu nechá cestu ke kořeni,
stará databáze dostane sloupce a backfill ze stopy, node-brief nese `effectiveDiscipline`, uložená verze
plátna disciplínu nese (starší verze se stopou zůstanou platné a obnoví se s disciplínou) a `track`
/ `set-track` / `effectiveTrack` jsou dočasné aliasy do K5."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.graph import digest as digest_of
from backend.editor.brief_vault.brief_vault_disciplines import DISCIPLINE_IDS
from backend.editor.brief_vault.brief_vault_model import MAX_DEPTH, effective_disciplines, latest_rows
from backend.editor.brief_vault.brief_vault_tree import tree_of
from backend.editor.node.test_removals import HEADERS, ORIGIN, SCOPE, install_graph, node
from database.schema import project_schema
from database.schema.project_schema import add_column, ensure_brief_fragment_columns, ensure_canvas_version_columns

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=discipline-1"}
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


def split_root(client, discipline="be"):
    root = post(client, op="create", scopeNodeId="s1", discipline=discipline, title="3. VRSTVA", text=TEXT)["fragment"]
    children = post(client, op="split", fragmentId=root["id"], expectedRevision=1, splitter="heading-number")["children"]
    return root, children


def revisions(client, fragment_id):
    db = client.app_state.service.db_for("draft")
    return [tuple(row) for row in db.execute("SELECT revision, text, discipline FROM brief_fragment_revisions"
                                             " WHERE fragment_id=? ORDER BY revision", (fragment_id,))]


def test_root_needs_discipline_and_child_inherits(client):
    missing = client.post("/api/brief-vault", headers=AGENT, json={**SCOPE, "op": "create", "scopeNodeId": "s1",
                                                                   "title": "T", "text": "t"})
    assert missing.status_code == 400 and "kořen" in missing.json()["error"]
    for broken in (None, "design", "", "logic", 3):
        post(client, expect=400, op="create", scopeNodeId="s1", discipline=broken, title="T", text="t")
    assert tree(client) == []
    root, (first, second) = split_root(client)
    child = post(client, op="create", parentId=root["id"], title="Výjimka", text="UI", discipline="ui")["fragment"]
    post(client, expect=400, op="create", parentId=root["id"], title="X", text="x", discipline="neni")
    assert root["discipline"] == "be" and first["discipline"] is None and child["discipline"] == "ui"
    assert "track" not in root
    found = nodes(tree(client))
    assert found[root["id"]]["effectiveDiscipline"] == "be" and found[first["id"]]["effectiveDiscipline"] == "be"
    assert found[first["id"]]["discipline"] is None and found[child["id"]]["effectiveDiscipline"] == "ui"
    research = post(client, op="research", fragmentId=second["id"], title="Ověřit", text="")["fragment"]
    assert research["discipline"] is None and nodes(tree(client))[research["id"]]["effectiveDiscipline"] == "be"


def test_revisions_keep_discipline(client):
    root, (first, _) = split_root(client, "ux")
    post(client, op="set-discipline", fragmentId=first["id"], expectedRevision=1, discipline="db", note="Datový model.")
    revised = post(client, op="revise", fragmentId=first["id"], expectedRevision=2, text="3.1 Tabulky\nnové.",
                   note="upřesnění")["fragment"]
    proposed = post(client, op="propose-mvp", fragmentIds=[first["id"]])["changed"][0]
    assert revised["discipline"] == "db" and proposed["discipline"] == "db"
    post(client, headers=HEADERS, op="restore", fragmentId=first["id"], expectedRevision=4, revision=1, note="zpět")
    assert revisions(client, first["id"])[-1] == (5, "3.1 Tabulky\nřádky.", "db")
    assert post(client, op="revise", fragmentId=root["id"], expectedRevision=1, title="3. Vrstva",
                note="název")["fragment"]["discipline"] == "ux"


def test_set_discipline_moves_subtree_with_cas_and_same_text(client):
    root, (first, second) = split_root(client)
    deep = post(client, op="create", parentId=first["id"], title="3.1.1", text="detail")["fragment"]
    post(client, expect=409, op="set-discipline", fragmentId=first["id"], expectedRevision=0, discipline="ux", note="staré")
    moved = post(client, op="set-discipline", fragmentId=first["id"], expectedRevision=1, discipline="ux",
                 note="Obrazovka, ne logika.")["fragment"]
    assert moved["revision"] == 2 and moved["discipline"] == "ux" and moved["by"] == "discipline-1"
    assert revisions(client, first["id"]) == [(1, "3.1 Tabulky\nřádky.", None), (2, "3.1 Tabulky\nřádky.", "ux")]
    found = nodes(tree(client))
    assert found[deep["id"]]["effectiveDiscipline"] == "ux" and found[second["id"]]["effectiveDiscipline"] == "be"
    post(client, expect=409, op="set-discipline", fragmentId=first["id"], expectedRevision=2, discipline="ux", note="znovu")
    post(client, expect=409, op="set-discipline", fragmentId=first["id"], expectedRevision=2, discipline="api", note="")
    post(client, expect=400, op="set-discipline", fragmentId=first["id"], expectedRevision=2, discipline="neni", note="x")
    post(client, expect=400, op="set-discipline", fragmentId=root["id"], expectedRevision=1, discipline=None, note="pryč")
    back = post(client, headers=HEADERS, op="set-discipline", fragmentId=first["id"], expectedRevision=2, discipline=None,
                note="Zpět na dědění.")["fragment"]
    assert back["discipline"] is None and nodes(tree(client))[deep["id"]]["effectiveDiscipline"] == "be"
    assert len(revisions(client, first["id"])) == 3


def test_filter_keeps_path_to_root_and_recounts_coverage(client):
    root, (first, second) = split_root(client)
    post(client, op="set-discipline", fragmentId=second["id"], expectedRevision=1, discipline="ux", note="UI")
    ux = tree(client, discipline="ux")
    assert [item["id"] for item in ux] == [root["id"]]
    assert [item["id"] for item in ux[0]["children"]] == [second["id"]] and ux[0]["coverage"]["leaves"] == 1
    be = tree(client, discipline="be")[0]
    assert [item["id"] for item in be["children"]] == [first["id"]] and be["coverage"]["leaves"] == 1
    assert tree(client, discipline="none") == [] and tree(client, discipline="db") == []
    assert tree(client)[0]["coverage"]["leaves"] == 2
    for bad in ("design", "logic"):
        assert client.get("/api/brief-vault", params={**SCOPE, "discipline": bad}).status_code == 400


def test_effective_disciplines_without_recursion_and_cycle():
    rows = {"r": {"parent_id": None, "discipline": "ux"}, "a": {"parent_id": "r", "discipline": None},
            "b": {"parent_id": "a", "discipline": "be"}, "c": {"parent_id": "b", "discipline": None},
            "x": {"parent_id": "y", "discipline": None}, "y": {"parent_id": "x", "discipline": None},
            "o": {"parent_id": "chybí", "discipline": None}}
    chain = {f"d{n}": {"parent_id": f"d{n - 1}" if n else "r", "discipline": None} for n in range(5000)}
    found = effective_disciplines({**rows, **chain})
    assert {key: found[key] for key in rows} == {"r": "ux", "a": "ux", "b": "be", "c": "be", "x": None, "y": None, "o": None}
    assert found["d4999"] == "ux"


def test_old_database_gets_columns_and_rows_are_unassigned(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector")], "edges": []})
        root = post(client, op="create", scopeNodeId="s1", discipline="ux", title="Staré", text="t")["fragment"]
        path = client.app.state.service.folder("draft").database
    db = sqlite3.connect(path)  # databáze z doby před stopami: sloupce track ani discipline neexistují
    db.execute("ALTER TABLE brief_fragment_revisions DROP COLUMN discipline")
    db.execute("ALTER TABLE brief_fragment_revisions DROP COLUMN track")
    db.commit()
    db.close()
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        found = tree(client)[0]
        assert found["id"] == root["id"] and found["discipline"] is None and found["effectiveDiscipline"] is None
        assert [item["id"] for item in tree(client, discipline="none")] == [root["id"]] and tree(client, discipline="ux") == []
        moved = post(client, op="set-discipline", fragmentId=root["id"], expectedRevision=1, discipline="be", note="Zařazeno.")
        assert moved["fragment"]["discipline"] == "be"
    db = sqlite3.connect(path)
    assert db.execute("SELECT revision, track, discipline FROM brief_fragment_revisions ORDER BY revision").fetchall() == [
        (1, None, None), (2, None, "be")]
    ensure_brief_fragment_columns(db)  # idempotentní
    names = [row[1] for row in db.execute("PRAGMA table_info(brief_fragment_revisions)")]
    assert names.count("track") == 1 and names.count("discipline") == 1
    db.close()


def test_backfill_maps_tracks_once_and_keeps_intentional_null(tmp_path):
    """Databáze se stopami: ux → ux, logic → be, NULL zůstává; revize nepřibývají; záměrné NULL po
    set-discipline se opakovaným otevřením nepřepíše (nový kód track nepíše)."""
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector")], "edges": []})
        root, (first, second) = split_root(client)
        ux_root = post(client, op="create", scopeNodeId="s1", discipline="ux", title="UX", text="u")["fragment"]
        post(client, op="set-discipline", fragmentId=first["id"], expectedRevision=1, discipline="api", note="API")
        path = client.app.state.service.folder("draft").database
    db = sqlite3.connect(path)  # stav z doby stop: track vyplněný, discipline ještě neexistuje
    db.execute("ALTER TABLE brief_fragment_revisions DROP COLUMN discipline")
    db.execute("UPDATE brief_fragment_revisions SET track='logic' WHERE fragment_id IN (?, ?)", (root["id"], first["id"]))
    db.execute("UPDATE brief_fragment_revisions SET track='ux' WHERE fragment_id=?", (ux_root["id"],))
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM brief_fragment_revisions").fetchone()[0]
    db.close()
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        db = client.app.state.service.db_for("draft")
        assert db.execute("SELECT COUNT(*) FROM brief_fragment_revisions").fetchone()[0] == count
        stored = {(row[0], row[1]): row[2] for row in db.execute(
            "SELECT fragment_id, revision, discipline FROM brief_fragment_revisions")}
        assert stored[(root["id"], 1)] == "be" and stored[(ux_root["id"], 1)] == "ux"
        assert stored[(first["id"], 1)] == "be" and stored[(first["id"], 2)] == "be"  # historie i poslední revize
        assert stored[(second["id"], 1)] is None
        found = nodes(tree(client))
        assert found[second["id"]]["effectiveDiscipline"] == "be" and found[ux_root["id"]]["effectiveDiscipline"] == "ux"
        reset = post(client, headers=HEADERS, op="set-discipline", fragmentId=first["id"], expectedRevision=2,
                     discipline=None, note="Dědí.")["fragment"]
        assert reset["revision"] == 3 and reset["discipline"] is None
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:  # opakované otevření = znovu backfill
        row = latest_rows(client.app.state.service.db_for("draft"), SCOPE["project"], SCOPE["workspace"], [first["id"]])[first["id"]]
        assert row["revision"] == 3 and row["discipline"] is None and row["track"] is None
        assert nodes(tree(client))[first["id"]]["discipline"] is None


def test_disciplines_endpoint_counts_live_fragments(client):
    empty = client.get("/api/brief-vault/disciplines", params=SCOPE).json()
    assert [item["id"] for item in empty["disciplines"]] == list(DISCIPLINE_IDS) and empty["unassigned"] == 0
    assert all(item["live"] == 0 for item in empty["disciplines"])
    assert empty["disciplines"][5] == {"id": "be", "group": "logika", "label": "Backend", "layer": "backend",
                                       "logicBlocks": True, "live": 0}
    root, (first, second) = split_root(client)
    post(client, op="set-discipline", fragmentId=second["id"], expectedRevision=1, discipline="ux", note="UI")
    post(client, op="research", fragmentId=first["id"], title="Ověřit", text="")  # poznámka, ne kus zadání
    gone = post(client, op="create", parentId=root["id"], title="Pryč", text="x", discipline="db")["fragment"]
    under = post(client, op="create", parentId=gone["id"], title="Pod smazaným", text="y")["fragment"]
    post(client, headers=HEADERS, op="delete", fragmentId=gone["id"], expectedRevision=1, note="ne")
    assert under["id"]
    counts = client.get("/api/brief-vault/disciplines", params=SCOPE).json()
    live = {item["id"]: item["live"] for item in counts["disciplines"]}
    assert live["be"] == 2 and live["ux"] == 1 and live["db"] == 0 and sum(live.values()) == 3
    assert counts["unassigned"] == 0
    db = client.app_state.service.db_for("draft")  # řádek bez disciplíny (z doby před stopami) = nezařazený
    with db:
        db.execute("UPDATE brief_fragment_revisions SET discipline=NULL WHERE fragment_id=?", (root["id"],))
    counts = client.get("/api/brief-vault/disciplines", params=SCOPE).json()
    live = {item["id"]: item["live"] for item in counts["disciplines"]}
    assert counts["unassigned"] == 2 and live["ux"] == 1 and live["be"] == 0


def test_track_aliases_until_k5(client):
    """Alias do K5, pak smazat: `track` v create/from-idea, `op: set-track`, odvozený `effectiveTrack`."""
    root = post(client, op="create", scopeNodeId="s1", track="logic", title="R", text=TEXT)["fragment"]
    assert root["discipline"] == "be" and "track" not in root
    ux = post(client, op="create", parentId=root["id"], track="ux", title="U", text="u")["fragment"]
    inherit = post(client, op="create", parentId=root["id"], track=None, title="I", text="i")["fragment"]
    assert ux["discipline"] == "ux" and inherit["discipline"] is None
    post(client, expect=400, op="create", scopeNodeId="s1", track=None, title="T", text="t")
    post(client, expect=400, op="create", scopeNodeId="s1", track="design", title="T", text="t")
    post(client, expect=400, op="create", scopeNodeId="s1", track="be", title="T", text="t")
    post(client, expect=400, op="create", scopeNodeId="s1", track="ux", discipline="ux", title="T", text="t")
    moved = post(client, op="set-track", fragmentId=inherit["id"], expectedRevision=1, track="ux", note="UI")["fragment"]
    assert moved["discipline"] == "ux"
    post(client, expect=409, op="set-track", fragmentId=inherit["id"], expectedRevision=2, track="ux", note="znovu")
    post(client, expect=400, op="set-track", fragmentId=root["id"], expectedRevision=1, track=None, note="pryč")
    post(client, op="set-discipline", fragmentId=ux["id"], expectedRevision=1, discipline="security", note="Bezpečnost")
    found = nodes(tree(client))
    assert found[root["id"]]["effectiveTrack"] == "logic" and found[inherit["id"]]["effectiveTrack"] == "ux"
    assert found[ux["id"]]["effectiveTrack"] == "logic" and found[ux["id"]]["effectiveDiscipline"] == "security"
    detail = client.get("/api/brief-vault/fragment", params={**SCOPE, "id": inherit["id"]}).json()
    assert detail["effectiveTrack"] == "ux" and detail["effectiveDiscipline"] == "ux" and "track" not in detail["fragment"]
    from backend.editor.brief_vault.test_brief_vault_develop import put_state, state
    put_state(client, nodes={"c1": {"phase": "discover", "criteria": [], "steps": [], "ideas": [
        {"id": "i1", "text": "Podnět.", "by": "review", "source": "review", "at": "T", "status": "open"}]}})
    made = post(client, op="from-idea", nodeId="c1", ideaId="i1", scopeNodeId="s1", track="logic")["fragment"]
    assert made["discipline"] == "be" and state(client)["state"]["nodes"]["c1"]["ideas"][0]["fragmentId"] == made["id"]


def test_from_idea_root_needs_discipline(client):
    from backend.editor.brief_vault.test_brief_vault_develop import put_state
    put_state(client, nodes={"c1": {"phase": "discover", "criteria": [], "steps": [], "ideas": [
        {"id": "i1", "text": "Podnět.", "by": "review", "source": "review", "at": "T", "status": "open"}]}})
    post(client, expect=400, op="from-idea", nodeId="c1", ideaId="i1", scopeNodeId="s1")
    post(client, expect=400, op="from-idea", nodeId="c1", ideaId="i1", scopeNodeId="s1", discipline="neni")
    made = post(client, op="from-idea", nodeId="c1", ideaId="i1", scopeNodeId="s1", discipline="observability")
    assert made["fragment"]["discipline"] == "observability"


def test_node_brief_carries_effective_discipline(client):
    _root, (first, _) = split_root(client)
    digest = client.get("/api/view", params=SCOPE).json()["digest"]
    current = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
    planned = client.post("/api/canvas-plan", headers=AGENT, json={**SCOPE, "digest": digest, "dryRun": False, "plan": {
        "extend": [{"node": "@c1", "expectedRevision": current, "fragmentRef": [{"fragmentId": first["id"]}]}]}})
    assert planned.status_code == 200, planned.text
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()["fragments"]
    assert brief["items"][0]["effectiveDiscipline"] == "be" and "effectiveTrack" not in brief["items"][0]
    post(client, op="set-discipline", fragmentId=first["id"], expectedRevision=1, discipline="ux", note="UI")
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "c1"}).json()["fragments"]
    assert brief["items"][0]["effectiveDiscipline"] == "ux" and brief["items"][0]["changedSinceInsert"] is False


def test_canvas_version_carries_discipline(client):
    from backend.editor.canvas_versions.test_canvas_versions import digest, save, versions
    _root, (first, _) = split_root(client)
    saved = save(client).json()["version"]
    post(client, op="set-discipline", fragmentId=first["id"], expectedRevision=1, discipline="ux", note="UI")
    assert versions(client)["dirty"] is True
    restored = client.post("/api/canvas-versions/restore", headers=HEADERS, json={
        **SCOPE, "versionId": saved["id"], "digest": digest(client), "author": "test",
        "expectedToken": versions(client)["currentToken"]})
    assert restored.status_code == 200, restored.text
    assert nodes(tree(client))[first["id"]]["discipline"] is None and revisions(client, first["id"])[-1][2] is None
    assert versions(client)["dirty"] is False


def test_version_saved_with_tracks_stays_valid_and_restores_disciplines(client):
    """Verze uložená v době stop (data řádku nesou `track`, ne `discipline`): integrita platí a obnova
    jí dá disciplínu stejně jako backfill databáze (logic → be, ux → ux)."""
    from backend.editor.canvas_versions.test_canvas_versions import digest, save, versions
    from backend.editor.canvas_versions.version_content import content_digest
    root, (first, _) = split_root(client)
    saved = save(client).json()["version"]
    db = client.app_state.service.db_for("draft")
    row = db.execute("SELECT graph, state, snapshot FROM canvas_versions WHERE id=?", (saved["id"],)).fetchone()
    snapshot = json.loads(row["snapshot"])
    for item in snapshot["records"]["briefFragments"]:
        value = item["data"].pop("discipline")
        item["data"]["track"] = {"be": "logic", "ux": "ux", None: None}[value]
    snapshot["integrity"] = digest_of({key: value for key, value in snapshot.items() if key != "integrity"})
    with db:  # takto snímek vypadal při uložení (digest obsahu stejný jako tehdy: track null se vynechá)
        db.execute("UPDATE canvas_versions SET snapshot=?, content_digest=? WHERE id=?", (
            json.dumps(snapshot, ensure_ascii=False), content_digest(json.loads(row["graph"]), json.loads(row["state"]), snapshot),
            saved["id"]))
    post(client, op="set-discipline", fragmentId=root["id"], expectedRevision=1, discipline="ux", note="UI")
    post(client, op="set-discipline", fragmentId=first["id"], expectedRevision=1, discipline="db", note="DB")
    restored = client.post("/api/canvas-versions/restore", headers=HEADERS, json={
        **SCOPE, "versionId": saved["id"], "digest": digest(client), "author": "test",
        "expectedToken": versions(client)["currentToken"]})
    assert restored.status_code == 200, restored.text
    found = nodes(tree(client))
    assert found[root["id"]]["discipline"] == "be" and found[first["id"]]["discipline"] is None


def test_version_saved_before_tracks_keeps_digest_and_restores():
    from backend.editor.canvas_versions.version_content import (
        STORES,
        content_digest,
        empty_data,
        validate_records,
        with_later_stores,
    )
    old = {key: value for key, value in empty_data("briefFragments").items() if key != "discipline"}
    row = {**old, "parent_id": None, "scope_node_id": "", "ord": 1, "title": "T", "text": "t", "actor": "agent", "deleted": 0}
    tracked = [{**row, "track": track} for track in ("ux", "logic", None)]
    records = {name: [] for name in STORES}
    records["briefFragments"] = [{"key": ["f1"], "revision": 1, "data": row}, {"key": ["f2"], "revision": 2, "data": old},
                                 *({"key": [f"t{index}"], "revision": 1, "data": data} for index, data in enumerate(tracked))]
    before = {"records": records, "assets": []}
    upgraded = {"records": with_later_stores(records), "assets": []}
    assert [item["data"]["discipline"] for item in upgraded["records"]["briefFragments"]] == [None, None, "ux", "be", None]
    assert all("track" not in item["data"] for item in upgraded["records"]["briefFragments"])
    # Snímek bez stopy i se stopou null má stejný digest jako po převodu (None se vynechá).
    plain = {"records": {**records, "briefFragments": records["briefFragments"][:2] + [records["briefFragments"][4]]}, "assets": []}
    assert content_digest({}, {}, plain) == content_digest({}, {}, {"records": with_later_stores(plain["records"]), "assets": []})
    assert content_digest({}, {}, before) != content_digest({}, {}, upgraded)  # stopa ux/logic je obsah uložené verze
    validate_records(upgraded["records"], "draft", "main")


def test_tree_helpers_on_rows_without_columns():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE brief_fragment_revisions(project_id TEXT, workspace_id TEXT, fragment_id TEXT, revision INTEGER,"
               " parent_id TEXT, scope_node_id TEXT, ord INTEGER, kind TEXT, title TEXT, text TEXT, stage TEXT, mvp TEXT,"
               " note TEXT, by TEXT, actor TEXT, deleted INTEGER, saved_at TEXT)")
    db.execute("INSERT INTO brief_fragment_revisions VALUES('p','w','r',1,NULL,'',1,'brief','R','t','draft','none','','a','agent',0,'T')")
    ensure_brief_fragment_columns(db)
    ensure_brief_fragment_columns(db)
    roots = tree_of(latest_rows(db, "p", "w"), {})
    assert roots[0]["discipline"] is None and roots[0]["effectiveDiscipline"] is None and roots[0]["effectiveTrack"] is None
    rows = latest_rows(db, "p", "w")
    assert tree_of(rows, {}, discipline="none")[0]["id"] == "r" and tree_of(rows, {}, discipline="be") == []


def _row(fragment_id, parent, discipline=None, kind="brief"):
    return {"fragment_id": fragment_id, "revision": 1, "parent_id": parent, "scope_node_id": "" if parent is None else None,
            "ord": 1, "kind": kind, "title": fragment_id, "text": "t", "stage": "draft", "mvp": "none", "note": "", "by": "a",
            "actor": "agent", "deleted": 0, "saved_at": "T", "discipline": discipline}


def test_filter_reaches_below_depth_limit_and_counts_only_its_discipline():
    """Fragment disciplíny hlouběji než strop hloubky nezmizí; pokrytí a hidden se počítají nad úplnými řádky."""
    rows = {"r": _row("r", None, "be"), "side": _row("side", "r")}
    parent = "r"
    for index in range(MAX_DEPTH + 3):  # řetěz be pod strop, na jeho konci list ux
        rows[f"d{index}"] = _row(f"d{index}", parent)
        parent = f"d{index}"
    rows["ux"] = _row("ux", parent, "ux")
    rows["beleaf"] = _row("beleaf", parent)
    ux = tree_of(rows, {}, discipline="ux")
    assert [root["id"] for root in ux] == ["r"] and ux[0]["coverage"]["leaves"] == 1
    assert [kid["id"] for kid in ux[0]["children"]] == ["d0"]
    cursor, depth = ux[0], 1
    while cursor["children"]:
        cursor, depth = cursor["children"][0], depth + 1
    assert depth == MAX_DEPTH and cursor["children"] == [] and cursor["hidden"] == 5 and cursor["coverage"]["leaves"] == 1
    be = tree_of(rows, {}, discipline="be")[0]
    assert be["coverage"]["leaves"] == 2 and tree_of(rows, {})[0]["coverage"]["leaves"] == 3
    assert tree_of(rows, {}, discipline="none") == []


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
    ensure_brief_fragment_columns(db)
    stale = {"brief_fragment_revisions": {"fragment_id"}, "canvas_versions": {"id", "project_id", "workspace_id"}}
    real = project_schema._columns
    monkeypatch.setattr(project_schema, "_columns", lambda db, table: stale.pop(table, None) or real(db, table))
    ensure_brief_fragment_columns(db)
    ensure_canvas_version_columns(db)
    assert {"snapshot", "content_digest"} <= real(db, "canvas_versions")
    assert {"track", "discipline"} <= real(db, "brief_fragment_revisions")
