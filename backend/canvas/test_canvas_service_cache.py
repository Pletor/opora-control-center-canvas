"""Cache čtení podle tokenu dat, neznámé ID projektu a velikost písmen (karta P3, blok 0 a 1)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_service import JOURNAL_SIZE_LIMIT, CanvasService, ProjectNotFound

ORIGIN = "http://127.0.0.1:8740"
NODES = [{"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0}]
# Čtecí cesty, které dřív pro neznámé ID založily projects/<id>/project.sqlite (kritik hacker P2).
READS = ["/api/view", "/api/desktop-v3/state", "/api/desktop-v3/leases", "/api/desktop-v3/frontier",
         "/api/desktop-v3/assignment-status", "/api/desktop-v3/work-overview", "/api/desktop-v3/card-checklist",
         "/api/desktop-v3/agent-workspace-summaries", "/api/canvas-versions", "/api/canvas-versions/head",
         "/api/canvas-index", "/api/drawing", "/api/project-settings"]


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def empty(service, name="Projekt"):
    return service.project_hub.empty_project({"name": name, "confirmed": True})["id"]


def test_unknown_project_reads_return_404_and_create_no_file_or_connection(tmp_path):
    root = tmp_path / "data"

    def folders():
        return sorted(path.name for path in (root / "projects").iterdir()) if (root / "projects").exists() else []

    with TestClient(create_app(root), base_url=ORIGIN) as client:
        assert client.get("/api/view", params={"project": "draft", "workspace": "draft"}).status_code == 200
        before = folders()
        for _ in range(3):
            ghost = uuid.uuid4().hex
            for url in READS:
                response = client.get(url, params={"project": ghost, "workspace": "draft"})
                assert response.status_code == 404, (url, response.status_code, response.text)
                assert response.json() == {"error": "Projekt neexistuje."}
            response = client.get("/api/desktop-v3/node-brief", params={"project": ghost, "workspace": "draft", "nodeId": "x"})
            assert response.status_code == 404, response.text
            assert not (root / "projects" / ghost).exists()
        assert folders() == before == ["draft"]


def test_unknown_project_gets_no_lock_and_no_database(service):
    ghost = uuid.uuid4().hex
    with pytest.raises(ProjectNotFound):
        service.lock_for(ghost)
    with pytest.raises(ProjectNotFound):
        service.db_for(ghost)
    with pytest.raises(ProjectNotFound), service.reading(ghost):
        pass
    assert ghost not in service._project_locks and ghost not in service._project_dbs
    assert not service.folder(ghost).path.exists()


def test_new_project_through_its_own_route_still_works(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        created = client.post("/api/empty-project", headers={"origin": ORIGIN}, json={"name": "Nový", "confirmed": True})
        assert created.status_code == 200, created.text
        pid = created.json()["id"]
        scope = {"project": pid, "workspace": "draft"}
        assert client.get("/api/view", params=scope).status_code == 200
        assert client.get("/api/desktop-v3/state", params=scope).json()["revision"] == 0


def test_other_letter_case_is_not_a_second_lock_or_database(service):
    pid = empty(service)
    alias = pid.upper()
    assert service.lock_for(pid) is service.lock_for(pid)
    service.view(pid, "draft")
    for call in (service.lock_for, service.graph_lock_for, service.db_for):
        with pytest.raises(ProjectNotFound):
            call(alias)
    with pytest.raises(ProjectNotFound):
        service.view(alias, "draft")
    with pytest.raises(ProjectNotFound):
        service.view("DRAFT", "draft")
    assert alias not in service._project_dbs and alias not in service._project_locks
    assert [key for key in service._project_dbs if key.lower() == pid] == [pid]


def test_every_connection_caps_the_wal_file(service):
    pid = empty(service)
    assert service.db_for(pid).execute("PRAGMA journal_size_limit").fetchone()[0] == JOURNAL_SIZE_LIMIT
    with service.reading(pid):
        reader = service.db_for(pid)
        assert reader is not service._project_dbs[pid]
        assert reader.execute("PRAGMA journal_size_limit").fetchone()[0] == JOURNAL_SIZE_LIMIT
    assert service.db.execute("PRAGMA journal_size_limit").fetchone()[0] == JOURNAL_SIZE_LIMIT


def test_data_token_is_stable_in_a_snapshot_changes_after_write_and_is_none_while_writing(service):
    pid = empty(service)
    assert service.data_token(pid) is None  # mimo čtecí blok se necachuje
    with service.reading(pid):
        first = service.data_token(pid)
        assert first is not None and service.data_token(pid) == first
    with service.reading(pid):
        assert service.data_token(pid) == first  # beze změny dat stejný token
    service.save_graph(pid, "draft", {"nodes": NODES, "edges": []}, service.view(pid, "draft")["digest"])
    with service.reading(pid):
        assert service.data_token(pid) not in (None, first)
    with service.lock_for(pid):
        assert service.data_token(pid) is None
        with service.reading(pid):
            assert service.data_token(pid) is None


def test_view_reuses_parsed_graph_until_the_graph_changes(service):
    pid = empty(service)
    service.save_graph(pid, "draft", {"nodes": NODES, "edges": []}, service.view(pid, "draft")["digest"])
    first, second = service.view(pid, "draft"), service.view(pid, "draft")
    assert first["graph"] is second["graph"] and first is not second
    with service.reading(pid):
        inner = service.view(pid, "draft")
        assert service.view(pid, "draft") == inner and service.view(pid, "draft") is not inner
    moved = {"nodes": [{**NODES[0], "x": 40}], "edges": []}
    saved = service.save_graph(pid, "draft", moved, first["digest"])
    assert saved["digest"] != first["digest"] and saved["graph"]["nodes"][0]["x"] == 40
    assert service.view(pid, "draft")["digest"] == saved["digest"]


def test_write_from_a_second_instance_invalidates_the_cache(tmp_path):
    first, second = CanvasService(tmp_path / "data"), CanvasService(tmp_path / "data")
    try:
        before = first.view("draft", "draft")
        assert first.view("draft", "draft")["graph"] is before["graph"]
        second.save_graph("draft", "draft", {"nodes": NODES, "edges": []}, second.view("draft", "draft")["digest"])
        after = first.view("draft", "draft")
        assert after["digest"] != before["digest"] and [n["id"] for n in after["graph"]["nodes"]] == ["focus"]
    finally:
        first.close()
        second.close()


def test_projects_never_share_cached_graphs(service):
    one, two = empty(service, "Jedna"), empty(service, "Dvě")
    service.save_graph(one, "draft", {"nodes": NODES, "edges": []}, service.view(one, "draft")["digest"])
    assert service.view(one, "draft")["graph"]["nodes"] and service.view(two, "draft")["graph"]["nodes"] == []
    assert service.view(one, "draft")["graph"] is not service.view(two, "draft")["graph"]


def test_removed_project_drops_its_cached_reads(service):
    pid = empty(service)
    service.view(pid, "draft")
    assert any(key[1] == pid for key in service.read_cache._entries)
    service.forget_project(pid)
    assert not any(key[1] == pid for key in service.read_cache._entries)


def test_unknown_project_writes_return_404_and_create_nothing(tmp_path):
    """Karta P3 (etapa test): i zápisové cesty pro neznámé ID (a alias velikosti písmen) skončí 404
    a nezaloží složku, soubor ani DB; registr se nezmění."""
    from backend.editor.agent_memory.desktop_v3_state import default_state

    root = tmp_path / "data"
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        real = client.post("/api/empty-project", headers={"origin": ORIGIN}, json={"name": "Skutečný", "confirmed": True})
        assert real.status_code == 200, real.text
        registry = client.get("/api/bootstrap").json()  # bootstrap založí i lokální návrh draft
        before = sorted(path.name for path in (root / "projects").iterdir())
        for ghost in (uuid.uuid4().hex, real.json()["id"].upper()):
            scope = {"project": ghost, "workspace": "draft"}
            calls = [
                ("/api/graph", {**scope, "graph": {"nodes": NODES, "edges": []}, "digest": "x"}),
                ("/api/desktop-v3/state", {**scope, "expectedRevision": 0, "state": default_state()}),
                ("/api/desktop-v3/rule", {**scope, "id": "a", "op": "add", "expected": None,
                                          "item": {"id": "a", "text": "R", "kind": "must", "scope": "project", "target": ""}}),
                ("/api/desktop-v3/decision", {**scope, "id": "a", "op": "add", "expected": None,
                                              "item": {"id": "a", "text": "D", "nodeId": "", "path": "", "pinned": False,
                                                       "createdAt": "2026-10-10T10:00:00+00:00", "by": "human"}}),
                ("/api/desktop-v3/pipeline", {**scope, "nodeId": "focus", "expectedRevision": 0, "op": "route",
                                              "profile": "code", "reason": "x"}),
                ("/api/desktop-v3/lease", {**scope, "nodeId": "focus", "op": "claim", "owner": "w", "ttlSeconds": 60}),
                ("/api/desktop-v3/agent-workspace", {**scope, "nodeId": "focus", "expectedRevision": 0, "by": "agent",
                                                     "sections": {"log": "x"}}),
                ("/api/canvas-versions", {**scope, "digest": "x", "author": "T"}),
            ]
            for url, body in calls:
                response = client.post(url, headers={"origin": ORIGIN}, json=body)
                assert response.status_code == 404, (ghost, url, response.status_code, response.text)
            # Názvy přes iterdir: na Windows by exists() u aliasu velikosti písmen našlo skutečnou složku.
            assert sorted(path.name for path in (root / "projects").iterdir()) == before
        assert client.get("/api/bootstrap").json() == registry
