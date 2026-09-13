"""Podklady pro agenta: úplný, přesný, deterministický balíček s manifestem a neměnným snapshotem."""
import json

from fastapi.testclient import TestClient
from test_workspace_sources import attach

from backend.agents.packets import desktop_v3_packets
from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
FIELDS = {"purpose", "goal", "architecture", "technologies", "notes", "requirements"}
FAKE_KEY = "sk-" + "proj-" + "B" * 40


def _rect(element_id, x, y, **extra):
    return {"id": element_id, "type": "rectangle", "x": x, "y": y, "width": 100, "height": 40, "strokeColor": "#000", "backgroundColor": "transparent", **extra}


def parent_scene(count=30):
    """Rev1 kresba rodiče: 30 aktivních prvků včetně šipky s geometrií a jeden smazaný prvek."""
    elements = [_rect(f"box{i}", i * 10, 0) for i in range(count - 3)]
    elements.append({"id": "flow", "type": "arrow", "x": 5, "y": 5, "width": 200, "height": 30,
                     "points": [[0, 0], [120, 12], [200, 30]],
                     "startBinding": {"elementId": "box0", "focus": 0.1, "gap": 2},
                     "endBinding": {"elementId": "box1", "focus": -0.2, "gap": 4}})
    elements.append({"id": "label", "type": "text", "x": 0, "y": 0, "width": 50, "height": 20, "text": "Přihlášení", "containerId": "box0"})
    elements.append({"id": "secretnote", "type": "text", "x": 0, "y": 60, "width": 50, "height": 20, "text": "token = " + FAKE_KEY})
    elements.append(_rect("ghost", 999, 999, isDeleted=True))
    return {"elements": elements}


def seed(client, tmp_path, focus_source=True):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "app.py").write_text("print('PRIVATE_SOURCE_CONTENT')", encoding="utf-8")
    (source / "docs").mkdir()
    (source / "docs" / "guide.md").write_text("PRIVATE_GUIDE", encoding="utf-8")
    project = attach(client, source)
    scope = {"project": project, "workspace": "draft"}
    view = client.get("/api/view", params=scope).json()
    focus = {"id": "focus", "parentId": "parent", "kind": "node", "name": "Editor", "purpose": "Editor uzlu", "x": 0, "y": 0}
    if focus_source:
        focus["sourceRef"] = {"origin": "existing", "path": "src/app.py", "kind": "file"}
    graph = {"nodes": [
        {"id": "sector", "parentId": None, "kind": "sector", "name": "Plátno", "purpose": "Sektor plátna", "x": 0, "y": 0,
         "sourceRef": {"origin": "existing", "path": "src", "kind": "directory"}},
        {"id": "parent", "parentId": "sector", "kind": "node", "name": "Rodič", "purpose": "Rodič s kresbou", "x": 0, "y": 0},
        focus,
        {"id": "sibling", "parentId": "sector", "kind": "node", "name": "Sourozenec", "purpose": "Mimo větev", "x": 5, "y": 5},
    ], "edges": [{"id": "e1", "source": "focus", "target": "sibling"}, {"id": "e2", "source": "parent", "target": "sibling"}]}
    assert client.post("/api/graph", headers=HEADERS, json={**scope, "graph": graph, "digest": view["digest"]}).status_code == 200
    drawn = client.post("/api/drawing", headers=HEADERS, json={**scope, "layer": "parent", "expected_revision": 0, "scene": parent_scene()})
    assert drawn.status_code == 200, drawn.text
    assert drawn.json()["revision"] == 1
    spec = client.post("/api/node-spec", headers=HEADERS, json={**scope, "node": "focus", "expected_revision": 0,
                       "fields": {"goal": "Přejmenovat kartu inline", "non_goals": "Žádný mobil", "acceptance": "Test prochází"}})
    assert spec.status_code == 200, spec.text
    assert client.post("/api/node-text", headers=HEADERS, json={**scope, "node": "parent", "expected_revision": 0, "text": "Text rodiče"}).status_code == 200
    doc_scope = {**scope, "path": "src/app.py"}
    current = client.get("/api/workspace/document", params=doc_scope).json()
    fields = {key: "" for key in FIELDS}
    fields["notes"] = "DOKUMENTACE_APP"
    assert client.post("/api/workspace/document", headers=HEADERS, json={**doc_scope, "expectedRevision": current["revision"], "fields": fields, "nodeId": None}).status_code == 200
    state = {
        "settings": [{"id": "s1", "key": "framework", "value": "React"}, {"id": "s2", "key": "leak", "value": "api_key = " + FAKE_KEY}],
        "rules": [
            {"id": "r1", "text": "Nikdy nespouštět agenta automaticky.", "kind": "must", "scope": "project", "target": ""},
            {"id": "r2", "text": "Měnit src bez testu.", "kind": "must_not", "scope": "path", "target": "src"},
            {"id": "r3", "text": "Jen docs.", "kind": "must", "scope": "path", "target": "docs"},
            {"id": "r4", "text": "Digest pro focus.", "kind": "must", "scope": "node", "target": "focus"},
            {"id": "r5", "text": "Jen sourozenec.", "kind": "must", "scope": "node", "target": "sibling"},
        ],
        "decisions": [
            {"id": "d1", "text": "Připnuté všude.", "pinned": True, "path": "", "nodeId": "", "createdAt": "2026-09-10T10:00:00+00:00", "by": "human"},
            {"id": "d2", "text": "Nepřipnuté pro focus.", "pinned": False, "path": "", "nodeId": "focus", "createdAt": "2026-09-10T11:00:00+00:00", "by": "agent"},
            {"id": "d3", "text": "Nepřipnuté jinde.", "pinned": False, "path": "docs", "nodeId": "sibling", "createdAt": "2026-09-10T12:00:00+00:00", "by": "human"},
        ],
        "nodes": {"focus": {"phase": "discover", "criteria": [{"id": "c1", "text": "Cíl popsán", "checked": True}],
                            "steps": [{"id": "st1", "text": "Napsat test", "assignee": "builder", "done": False}]}},
        "tickets": [
            {"id": "t1", "title": "Ticket uzlu", "priority": "high", "status": "open", "nodeId": "focus", "sessionId": "", "createdBy": "agent"},
            {"id": "t2", "title": "Ticket session", "priority": "low", "status": "doing", "nodeId": "", "sessionId": "sess1", "createdBy": "human"},
            {"id": "t3", "title": "Cizí ticket", "priority": "normal", "status": "done", "nodeId": "sibling", "sessionId": "other", "createdBy": "human"},
        ],
    }
    assert client.post("/api/desktop-v3/state", headers=HEADERS, json={**scope, "expectedRevision": 0, "state": state}).status_code == 200
    # Ticket t2 odkazuje na sess1: ta musí existovat jako skutečný uložený plánovací běh, ne jen ID v paměti.
    store_planning_run(client, project, "sess1", output="Návrh sess1: api_key = " + FAKE_KEY)
    return scope


def store_planning_run(client, project, run_id, workspace="draft", layer="focus", output="Uložený návrh."):
    """Dokončený lokální plánovací běh v jeho skutečné tabulce (bez spuštění modelu)."""
    db = client.app.state.service.db
    with db:
        db.execute(
            "INSERT INTO llm_runs(id,project_id,workspace,layer,digest,context,status,message,output,provider_billing,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, project, workspace, layer, "fixture-digest", "{}", "completed", "Návrh dokončen.", output,
             "unknown", "2026-09-10T00:00:00Z", "2026-09-10T00:00:01Z"),
        )


def request(scope, **overrides):
    payload = {**scope, "nodeId": "focus", "path": "src/app.py", "sessionId": "sess1", "references": ["docs/guide.md"], "note": "Udělej to pečlivě."}
    payload.update(overrides)
    return payload


def preview(client, scope, **overrides):
    return client.post("/api/desktop-v3/packet/preview", headers=HEADERS, json=request(scope, **overrides))


def manifest_index(packet):
    return {(item["kind"], item["ownerId"]): item for item in packet["sourceManifest"]}


def test_preview_includes_ancestor_drawing_with_revision_geometry_and_deleted_filtering(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        response = preview(client, scope)
        assert response.status_code == 200, response.text
        body = response.json()
        packet = body["packet"]
        assert packet["schema"] == "opora.packet/1"
        assert packet["scope"] == {**scope, "nodeId": "focus", "path": "src/app.py", "sessionId": "sess1"}
        assert isinstance(body["digest"], str) and len(body["digest"]) == 64
        index = manifest_index(packet)
        focus_drawing = index[("drawing", "focus")]
        assert focus_drawing["revision"] == 0 and focus_drawing["included"] is False
        parent_drawing = index[("drawing", "parent")]
        assert parent_drawing["revision"] == 1 and parent_drawing["included"] is True
        assert ("drawing", "sector") in index and ("drawing", "") in index
        drawings = {item["layer"]: item for item in packet["context"]["drawings"]}
        parent = drawings["parent"]
        assert parent["revision"] == 1
        assert parent["elementCount"] == 30
        ids = {element["id"] for element in parent["elements"]}
        assert "ghost" not in ids and len(ids) == 30
        arrow = next(element for element in parent["elements"] if element["id"] == "flow")
        assert arrow["points"] == [[0, 0], [120, 12], [200, 30]]
        assert arrow["startBinding"]["elementId"] == "box0" and arrow["endBinding"]["elementId"] == "box1"
        box = next(element for element in parent["elements"] if element["id"] == "box0")
        assert box["label"] == "Přihlášení"
        assert [item["nodeId"] for item in packet["context"]["ancestors"]] == ["parent", "sector"]
        assert packet["task"]["spec"]["fields"]["goal"] == "Přejmenovat kartu inline"
        assert packet["task"]["spec"]["revision"] == 1
        texts = {item["nodeId"]: item for item in packet["context"]["texts"]}
        assert texts["parent"]["text"] == "Text rodiče" and texts["parent"]["revision"] == 1
        assert any(item["kind"] == "text" and item["ownerId"] == "parent" and item["revision"] == 1 for item in packet["sourceManifest"])
        relations = packet["context"]["relations"]
        assert {edge["id"] for edge in relations} == {"e1", "e2"}
        assert packet["warnings"] == [] or all(isinstance(w, str) for w in packet["warnings"])


def test_preview_scopes_rules_decisions_tickets_documents_and_keeps_references_unread(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        packet = preview(client, scope).json()["packet"]
        memory = packet["context"]["memory"]
        assert memory["revision"] == 1
        assert [rule["id"] for rule in memory["rules"]] == ["r1", "r2", "r4"]
        assert [item["id"] for item in memory["decisions"]] == ["d1", "d2"]
        assert [item["id"] for item in memory["tickets"]] == ["t1", "t2"]
        assert memory["phase"] == "discover" and memory["criteria"][0]["checked"] is True
        assert memory["steps"][0]["assignee"] == "builder"
        assert {item["key"]: item["value"] for item in memory["settings"]}["framework"] == "React"
        documents = {item["path"]: item for item in packet["context"]["documents"]}
        assert documents["src/app.py"]["fields"]["notes"] == "DOKUMENTACE_APP"
        assert documents["src/app.py"]["revision"] == 1
        index = manifest_index(packet)
        assert index[("document", "src/app.py")]["included"] is True
        assert index[("reference", "docs/guide.md")] == {"kind": "reference", "ownerId": "docs/guide.md", "revision": None, "included": False, "reason": "reference_only"}
        assert packet["task"]["references"] == [{"path": "docs/guide.md", "mode": "reference", "contentIncluded": False}]
        assert index[("path", "src/app.py")]["included"] is True
        assert packet["task"]["note"] == "Udělej to pečlivě."
        assert packet["policy"] == {"autostart": False, "requiresConfirmation": True, "provider": None, "proposalOnly": True}
        serialized = json.dumps(packet, ensure_ascii=False)
        assert "PRIVATE_SOURCE_CONTENT" not in serialized
        assert "PRIVATE_GUIDE" not in serialized
        assert str(tmp_path) not in serialized


def test_preview_redacts_secrets_from_memory_and_drawing_text(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        response = preview(client, scope)
        assert FAKE_KEY not in response.text
        assert "[REDACTED]" in response.text


def test_preview_digest_is_deterministic_and_changes_with_ancestor_drawing(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        first, second = preview(client, scope).json(), preview(client, scope).json()
        assert first == second
        other_note = preview(client, scope, note="jiná poznámka").json()
        assert other_note["digest"] != first["digest"]
        scene = parent_scene()
        scene["elements"][0]["x"] = 777
        assert client.post("/api/drawing", headers=HEADERS, json={**scope, "layer": "parent", "expected_revision": 1, "scene": scene}).status_code == 200
        changed = preview(client, scope).json()
        assert changed["digest"] != first["digest"]
        assert manifest_index(changed["packet"])[("drawing", "parent")]["revision"] == 2


def test_snapshot_requires_matching_digest_and_stays_immutable_after_source_change(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        seen = preview(client, scope).json()
        wrong = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS, json={**request(scope), "digest": "0" * 64})
        assert wrong.status_code == 409
        stored = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS, json={**request(scope), "digest": seen["digest"]})
        assert stored.status_code == 200, stored.text
        snapshot = stored.json()
        assert snapshot["digest"] == seen["digest"] and snapshot["packet"] == seen["packet"]
        assert isinstance(snapshot["id"], str) and snapshot["id"]
        loaded = client.get(f"/api/desktop-v3/packet/snapshots/{snapshot['id']}", params=scope)
        assert loaded.status_code == 200 and loaded.json()["packet"] == seen["packet"]
        assert client.post("/api/node-text", headers=HEADERS, json={**scope, "node": "parent", "expected_revision": 1, "text": "Změněný text rodiče"}).status_code == 200
        stale = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS, json={**request(scope), "digest": seen["digest"]})
        assert stale.status_code == 409
        assert "změn" in stale.json()["error"].lower()
        again = client.get(f"/api/desktop-v3/packet/snapshots/{snapshot['id']}", params=scope).json()
        assert again["packet"] == seen["packet"] and again["digest"] == seen["digest"]
        assert {item["nodeId"]: item["text"] for item in again["packet"]["context"]["texts"]}["parent"] == "Text rodiče"
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Other", "confirmed": True}).json()["id"]
        assert client.get(f"/api/desktop-v3/packet/snapshots/{snapshot['id']}", params={"project": other, "workspace": "draft"}).status_code == 409
        assert client.get("/api/desktop-v3/packet/snapshots/missing", params=scope).status_code == 409


def test_preview_validates_scope_and_allows_concept_without_path(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path, focus_source=False)
        assert preview(client, scope, nodeId="missing").status_code == 409
        assert preview(client, scope, path="../secret").status_code == 409
        assert preview(client, scope, references=["../x"]).status_code == 409
        assert preview(client, scope, references="docs").status_code == 409
        assert preview(client, scope, note="x" * 5000).status_code == 409
        assert client.post("/api/desktop-v3/packet/preview", headers=HEADERS, json={**request(scope), "extra": 1}).status_code == 409
        concept = preview(client, scope, path="", references=[], note="")
        assert concept.status_code == 200, concept.text
        packet = concept.json()["packet"]
        assert packet["scope"]["path"] == "" and packet["task"]["sourceRef"] is None
        assert [rule["id"] for rule in packet["context"]["memory"]["rules"]] == ["r1", "r4"]
        assert ("path", "") not in manifest_index(packet)
        missing = preview(client, scope, path="src/nowhere.py")
        assert missing.status_code == 200
        entry = manifest_index(missing.json()["packet"])[("path", "src/nowhere.py")]
        assert entry["included"] is False and entry["reason"] == "not_found"
        assert any("src/nowhere.py" in warning for warning in missing.json()["packet"]["warnings"])


def test_byte_limit_is_explicit_in_manifest_or_error_never_silent(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        full = preview(client, scope).json()["packet"]
        parent = next(item for item in full["context"]["drawings"] if item["layer"] == "parent")
        size = len(json.dumps(parent, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        monkeypatch.setattr(desktop_v3_packets, "MAX_PACKET_BYTES", size)
        limited = preview(client, scope)
        assert limited.status_code == 200, limited.text
        packet = limited.json()["packet"]
        entry = manifest_index(packet)[("drawing", "parent")]
        assert entry["included"] is False and entry["reason"] == "limit_exceeded"
        assert all(item["layer"] != "parent" for item in packet["context"]["drawings"])
        assert any("parent" in warning for warning in packet["warnings"])
        monkeypatch.setattr(desktop_v3_packets, "MAX_PACKET_BYTES", 200)
        refused = preview(client, scope)
        assert refused.status_code == 409
        assert "limit" in refused.json()["error"].lower()


def test_planning_context_shares_the_same_ancestor_drawing_assembly(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        planning = client.get("/api/llm/preview", params={**scope, "layer": "focus"})
        assert planning.status_code == 200, planning.text
        context = planning.json()["context"]
        assert context["wireframe"]["drawingRevision"] == 0
        chain = {item["layer"]: item for item in context["drawings"]}
        assert chain["parent"]["revision"] == 1 and chain["parent"]["elementCount"] == 30
        assert "ghost" not in json.dumps(chain["parent"])
        assert chain["focus"]["revision"] == 0
        assert [rule["id"] for rule in context["memory"]["rules"]] == ["r1", "r2", "r4"]
        assert FAKE_KEY not in planning.text
        packet = preview(client, scope).json()["packet"]
        assert chain["parent"]["elements"] == next(item for item in packet["context"]["drawings"] if item["layer"] == "parent")["elements"]


def test_session_scope_includes_the_real_stored_planning_run_redacted_with_manifest(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        response = preview(client, scope)
        assert response.status_code == 200, response.text
        packet = response.json()["packet"]
        session = packet["context"]["session"]
        assert session["id"] == "sess1" and session["kind"] == "planning_run"
        assert session["nodeId"] == "focus" and session["status"] == "completed"
        assert session["output"].startswith("Návrh sess1: ") and "[REDACTED]" in session["output"]
        assert session["proposalOnly"] is True
        entry = manifest_index(packet)[("session", "sess1")]
        assert entry["included"] is True and entry["reason"] == "saved_planning_run"
        assert FAKE_KEY not in response.text
        no_session = preview(client, scope, sessionId="").json()["packet"]
        assert "session" not in no_session["context"]
        assert all(item["kind"] != "session" for item in no_session["sourceManifest"])
        assert [item["id"] for item in no_session["context"]["memory"]["tickets"]] == ["t1"]


def test_session_scope_rejects_memory_only_unknown_cross_project_and_cross_workspace_ids(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        # "other" existuje jen jako sessionId ticketu t3 v paměti; to není skutečná session.
        assert preview(client, scope, sessionId="other").status_code == 409
        assert preview(client, scope, sessionId="missing-session").status_code == 409
        store_planning_run(client, scope["project"], "foreign-ws", workspace="otherws", output="CIZI_WORKSPACE_VYSTUP")
        foreign_ws = preview(client, scope, sessionId="foreign-ws")
        assert foreign_ws.status_code == 409 and "CIZI_WORKSPACE_VYSTUP" not in foreign_ws.text
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Other", "confirmed": True}).json()["id"]
        store_planning_run(client, other, "foreign-project", output="CIZI_PROJEKT_VYSTUP")
        foreign_project = preview(client, scope, sessionId="foreign-project")
        assert foreign_project.status_code == 409 and "CIZI_PROJEKT_VYSTUP" not in foreign_project.text
        stale = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS, json={**request(scope, sessionId="foreign-project"), "digest": "0" * 64})
        assert stale.status_code == 409 and "CIZI_PROJEKT_VYSTUP" not in stale.text


def test_session_output_change_changes_digest_and_blocks_stale_snapshot_start(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        seen = preview(client, scope).json()
        assert preview(client, scope).json()["digest"] == seen["digest"]
        frozen = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS, json={**request(scope), "digest": seen["digest"]})
        assert frozen.status_code == 200, frozen.text
        snapshot = frozen.json()
        prepared = client.post(f"/api/desktop-v3/packet/snapshots/{snapshot['id']}/prepare", headers=HEADERS, json={**scope, "task": "Dokumentuj podle návrhu session."})
        assert prepared.status_code == 200, prepared.text
        record = prepared.json()
        exported = client.get(f"/api/task-handoffs/{record['id']}/export").json()
        assert exported["context"]["documents"]["context"]["session"] == snapshot["packet"]["context"]["session"]
        db = app.state.service.db
        with db:
            db.execute("UPDATE llm_runs SET output=? WHERE id=?", ("Přepsaný návrh.", "sess1"))
        changed = preview(client, scope).json()
        assert changed["digest"] != seen["digest"]
        assert changed["packet"]["context"]["session"]["output"] == "Přepsaný návrh."
        refused = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS, json={**request(scope), "digest": seen["digest"]})
        assert refused.status_code == 409
        started = client.post(f"/api/task-handoffs/{record['id']}/start", headers=HEADERS, json={"digest": record["digest"], "confirmed": True})
        assert started.status_code == 409, started.text
        assert client.get(f"/api/task-handoffs/{record['id']}").json()["status"] == "prepared"
        again = client.get(f"/api/desktop-v3/packet/snapshots/{snapshot['id']}", params=scope).json()
        assert again["packet"]["context"]["session"]["output"] == snapshot["packet"]["context"]["session"]["output"]


def test_prepared_documentation_handoff_is_a_real_session_and_its_result_changes_digest(tmp_path):
    app = create_app(tmp_path / "data")
    started = []
    app.state.task_handoffs._run = lambda run: started.append(run)
    with TestClient(app, base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        base = request(scope, sessionId="")
        seen = preview(client, scope, sessionId="").json()
        frozen = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS, json={**base, "digest": seen["digest"]}).json()
        handoff = client.post(f"/api/desktop-v3/packet/snapshots/{frozen['id']}/prepare", headers=HEADERS, json={**scope, "task": "Sepiš dokumentaci."}).json()
        response = preview(client, scope, sessionId=handoff["id"])
        assert response.status_code == 200, response.text
        packet = response.json()["packet"]
        session = packet["context"]["session"]
        assert session["kind"] == "documentation_handoff" and session["id"] == handoff["id"]
        assert session["status"] == "prepared" and session["task"] == "Sepiš dokumentaci." and session["output"] is None
        assert session["nodeId"] == "focus"
        assert "context" not in session and "packet" not in session
        entry = manifest_index(packet)[("session", handoff["id"])]
        assert entry["included"] is True and entry["reason"] == "saved_documentation_handoff"
        handoffs = app.state.task_handoffs
        handoffs._save(handoff["id"], status="completed", result={"content": "Výsledek token = " + FAKE_KEY, "sha256": "x" * 64})
        completed = preview(client, scope, sessionId=handoff["id"])
        assert completed.json()["digest"] != response.json()["digest"]
        assert completed.json()["packet"]["context"]["session"]["output"].startswith("Výsledek token = [REDACTED]")
        assert FAKE_KEY not in completed.text
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Other", "confirmed": True}).json()["id"]
        cross = client.post("/api/desktop-v3/packet/preview", headers=HEADERS,
                            json={"project": other, "workspace": "draft", "nodeId": "", "path": "", "sessionId": handoff["id"], "references": [], "note": ""})
        assert cross.status_code == 409 and "Výsledek" not in cross.text
        assert not started
