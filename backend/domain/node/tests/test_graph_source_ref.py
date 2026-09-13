from fastapi.testclient import TestClient
from backend.integrations.tests.test_workspace_sources import ORIGIN, attach

from backend.app.factory import create_app


def view(client, pid, wid="draft"):
    return client.get("/api/view", params={"project": pid, "workspace": wid}).json()


def post_graph(client, pid, graph, digest, wid="draft"):
    return client.post(
        "/api/graph",
        headers={"origin": ORIGIN},
        json={"project": pid, "workspace": wid, "graph": graph, "digest": digest},
    )


def sector(id="sector-1", parent=None, source_ref=None, purpose="Účel"):
    node = {"id": id, "parentId": parent, "kind": "sector", "name": "Sektor", "purpose": purpose, "x": 0, "y": 0}
    if source_ref is not None or source_ref is False:
        node["sourceRef"] = None if source_ref is False else source_ref
    return node


def node(id="node-1", parent="sector-1", source_ref=None, kind="node"):
    n = {"id": id, "parentId": parent, "kind": kind, "name": "Uzel", "purpose": "", "x": 0, "y": 0}
    if source_ref is not None or source_ref is False:
        n["sourceRef"] = None if source_ref is False else source_ref
    return n


def test_sector_binds_existing_root_directory(tmp_path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        ref = {"origin": "existing", "path": "", "kind": "directory"}
        graph = {"nodes": [sector(source_ref=ref)], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 200, r.text
        reloaded = view(client, pid)
        assert reloaded["graph"]["nodes"][0]["sourceRef"] == ref


def test_sector_existing_path_must_exist_on_disk(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        ref = {"origin": "existing", "path": "nope", "kind": "directory"}
        graph = {"nodes": [sector(source_ref=ref)], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 409


def test_node_existing_descendant_of_bound_sector_is_accepted(tmp_path):
    source = tmp_path / "source"
    (source / "pkg" / "mod.py").parent.mkdir(parents=True)
    (source / "pkg" / "mod.py").write_text("x", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        sector_ref = {"origin": "existing", "path": "pkg", "kind": "directory"}
        node_ref = {"origin": "existing", "path": "pkg/mod.py", "kind": "file"}
        graph = {"nodes": [sector(source_ref=sector_ref), node(source_ref=node_ref)], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 200, r.text
        assert view(client, pid)["graph"]["nodes"][1]["sourceRef"] == node_ref


def test_node_existing_path_outside_bound_sector_is_forged_and_rejected(tmp_path):
    source = tmp_path / "source"
    (source / "pkg").mkdir(parents=True)
    (source / "other").mkdir()
    (source / "other" / "secret.py").write_text("x", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        sector_ref = {"origin": "existing", "path": "pkg", "kind": "directory"}
        node_ref = {"origin": "existing", "path": "other/secret.py", "kind": "file"}
        graph = {"nodes": [sector(source_ref=sector_ref), node(source_ref=node_ref)], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 409


def test_planned_node_requires_sector_ancestor(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        planned = {"origin": "planned", "path": "", "kind": "file"}
        graph = {"nodes": [node(id="orphan", parent=None, source_ref=planned)], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 409


def test_planned_sector_requires_meaningful_purpose(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        planned = {"origin": "planned", "path": "", "kind": "directory"}
        graph = {"nodes": [sector(source_ref=planned, purpose="krátce")], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 409


def test_planned_sector_with_meaningful_purpose_saves_without_disk_writes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        planned = {"origin": "planned", "path": "budouci/slozka", "kind": "directory"}
        graph = {"nodes": [sector(source_ref=planned, purpose="Návrh nové oblasti odpovědnosti.")], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 200, r.text
        assert not (source / "budouci").exists()


def test_legacy_node_without_source_ref_still_saves(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        graph = {"nodes": [sector(), node()], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 200, r.text
        nodes = view(client, pid)["graph"]["nodes"]
        assert "sourceRef" not in nodes[0]
        assert "sourceRef" not in nodes[1]


def test_unchanged_existing_binding_survives_source_deletion(tmp_path):
    source = tmp_path / "source"
    (source / "keep.txt").parent.mkdir(parents=True, exist_ok=True)
    (source / "keep.txt").write_text("x", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        v = view(client, pid)
        sector_ref = {"origin": "existing", "path": "", "kind": "directory"}
        ref = {"origin": "existing", "path": "keep.txt", "kind": "file"}
        graph = {"nodes": [sector(source_ref=sector_ref), node(source_ref=ref)], "edges": []}
        r = post_graph(client, pid, graph, v["digest"])
        assert r.status_code == 200, r.text
        (source / "keep.txt").unlink()
        v2 = view(client, pid)
        moved_graph = dict(v2["graph"])
        moved_graph["nodes"] = [dict(n) for n in moved_graph["nodes"]]
        moved_graph["nodes"][1]["x"] = 42
        r2 = post_graph(client, pid, moved_graph, v2["digest"])
        assert r2.status_code == 200, r2.text
        assert view(client, pid)["graph"]["nodes"][1]["sourceRef"] == ref
