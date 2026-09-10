"""Nezávislé orákulum: změna hierarchie nesmí obejít rozsah zdroje."""
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

ORIGIN = "http://127.0.0.1:8740"


def entry(key, kind, parent, path, origin="existing"):
    return {"id": key, "kind": kind, "parentId": parent, "name": key,
            "purpose": "Samostatná oblast návrhu s vlastním účelem.", "x": 0, "y": 0,
            "sourceRef": {"origin": origin, "path": path,
                          "kind": "directory" if kind == "sector" else "file"}}


def scope(client, source):
    result = client.post("/api/local-project", headers={"origin": ORIGIN},
                         json={"name": "Oracle", "path": str(source), "confirmed": True})
    assert result.status_code == 200, result.text
    return result.json()["id"]


def save(client, pid, nodes):
    before = client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()
    return client.post("/api/graph", headers={"origin": ORIGIN}, json={
        "project": pid, "workspace": "draft", "digest": before["digest"],
        "graph": {"nodes": nodes, "edges": []}})


def fixture_source(tmp_path):
    root = tmp_path / "source"
    (root / "src").mkdir(parents=True)
    (root / "other").mkdir()
    (root / "src/main.py").write_text("pass\n", encoding="utf-8")
    return root


def test_reparent_cannot_keep_source_from_another_sector(tmp_path):
    source = fixture_source(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = scope(client, source)
        nodes = [entry("src-sector", "sector", None, "src"),
                 entry("other-sector", "sector", None, "other"),
                 entry("child", "node", "src-sector", "src/main.py")]
        first = save(client, pid, nodes)
        assert first.status_code == 200, first.text
        nodes[-1]["parentId"] = "other-sector"
        moved = save(client, pid, nodes)
        assert moved.status_code == 409, moved.text


def test_rebinding_sector_cannot_leave_children_outside(tmp_path):
    source = fixture_source(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = scope(client, source)
        nodes = [entry("src-sector", "sector", None, "src"),
                 entry("child", "node", "src-sector", "src/main.py")]
        first = save(client, pid, nodes)
        assert first.status_code == 200, first.text
        nodes[0]["sourceRef"]["path"] = "other"
        changed = save(client, pid, nodes)
        assert changed.status_code == 409, changed.text


def test_existing_source_cannot_bypass_unbound_planned_sector(tmp_path):
    source = fixture_source(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = scope(client, source)
        nodes = [entry("planned-sector", "sector", None, "future", "planned"),
                 entry("child", "node", "planned-sector", "src/main.py")]
        forged = save(client, pid, nodes)
        assert forged.status_code == 409, forged.text


def test_planned_node_path_cannot_escape_its_bound_sector(tmp_path):
    source = fixture_source(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = scope(client, source)
        nodes = [entry("src-sector", "sector", None, "src"),
                 entry("planned-child", "node", "src-sector", "other/secret.py", "planned")]
        forged = save(client, pid, nodes)
        assert forged.status_code == 409, forged.text


@pytest.mark.parametrize("path", ["src/../../outside.py", "src/../other/x.py", r"src\..\other\x.py", "src//../x.py"])
def test_review_traversal_is_rejected_by_real_http_guard(tmp_path, path):
    """Charakterizační důkaz již existujícího guardu, nikoli nová oprava."""
    source = fixture_source(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = scope(client, source)
        nodes = [entry("sector", "sector", None, "src"),
                 entry("child", "node", "sector", path, "planned")]
        before = client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()
        refused = save(client, pid, nodes)
        assert refused.status_code == 409, refused.text
        after = client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()
        assert after["digest"] == before["digest"]
        assert after["graph"] == before["graph"]
