import pytest

from backend.context_packets import ContextPackets
from backend.service import CanvasService

ORIGIN = "http://127.0.0.1:8740"


def make_service(tmp_path):
    return CanvasService(tmp_path / "data")


def seed_graph(service, project="draft", workspace="draft"):
    nodes = [
        {"id": "sector", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
        {"id": "focus", "parentId": "sector", "kind": "node", "name": "Ohnisko", "purpose": "Účel", "x": 0, "y": 0},
        {"id": "friend", "parentId": "sector", "kind": "node", "name": "Soused", "purpose": "", "x": 10, "y": 10},
    ]
    view = service.view(project, workspace)
    return service.save_graph(project, workspace, {"nodes": nodes, "edges": []}, view["digest"])


def base_payload(**overrides):
    payload = {
        "project": "draft",
        "workspace": "draft",
        "node": "focus",
        "includeNodeIds": [],
        "includeJournalDays": [],
        "maxBytes": 50000,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("field", ["name", "purpose"])
def test_packet_redacts_project_style_credentials_from_all_node_text(tmp_path, field):
    """Známé tvary klíčů nesmí uniknout ani přes název uzlu do snapshotu."""
    service = make_service(tmp_path)
    try:
        seed_graph(service)
        view = service.view("draft", "draft")
        fake_key = "sk-" + "proj-" + "A" * 40
        next(n for n in view["graph"]["nodes"] if n["id"] == "focus")[field] = fake_key
        service.save_graph("draft", "draft", view["graph"], view["digest"])
        packets = ContextPackets(service)
        stored = packets.build(base_payload())
        assert stored["content"]["focus"][field] == "[REDACTED]"
        assert fake_key not in str(packets.load(stored["id"]))
        row = service.db.execute("SELECT payload FROM context_packets WHERE id=?", (stored["id"],)).fetchone()
        assert fake_key not in row["payload"]
    finally:
        service.close()


def test_build_load_and_validate_roundtrip(tmp_path):
    service = make_service(tmp_path)
    seed_graph(service)
    service.texts.access("draft", "draft", "focus", {
        "project": "draft", "workspace": "draft", "node": "focus", "expected_revision": 0, "text": "Vlastní text uzlu",
    })
    packets = ContextPackets(service)
    stored = packets.build(base_payload(includeNodeIds=["friend"]))
    assert stored["content"]["focus"]["text"]["text"] == "Vlastní text uzlu"
    assert [n["nodeId"] for n in stored["content"]["neighbors"]] == ["friend"]
    assert stored["excluded"] == []
    assert stored["truncated"] == []

    loaded_first = packets.load(stored["id"])
    loaded_second = packets.load(stored["id"])
    assert loaded_first == loaded_second == stored

    check = packets.validate(stored["id"])
    assert check["stale"] is False
    assert check["changes"] == []


def test_source_edit_makes_snapshot_stale_but_immutable(tmp_path):
    service = make_service(tmp_path)
    seed_graph(service)
    packets = ContextPackets(service)
    stored = packets.build(base_payload())
    before_reload = packets.load(stored["id"])

    service.texts.access("draft", "draft", "focus", {
        "project": "draft", "workspace": "draft", "node": "focus", "expected_revision": 0, "text": "Nový obsah po uložení",
    })

    check = packets.validate(stored["id"])
    assert check["stale"] is True
    assert any(change["kind"] == "text" and change["nodeId"] == "focus" for change in check["changes"])

    after_reload = packets.load(stored["id"])
    assert after_reload == before_reload
    assert after_reload["content"]["focus"]["text"]["text"] == ""


def test_scoped_selection_does_not_leak_across_projects(tmp_path):
    service = make_service(tmp_path)
    seed_graph(service, project="draft", workspace="draft")
    other = service.project_hub.empty_project({"name": "Other", "confirmed": True})
    other_id = other["id"]
    other_view = service.view(other_id, "draft")
    service.save_graph(other_id, "draft", {
        "nodes": [{"id": "secretnode", "parentId": None, "kind": "node", "name": "Tajny", "purpose": "SOUKROMY_OBSAH_B", "x": 0, "y": 0}],
        "edges": [],
    }, other_view["digest"])

    packets = ContextPackets(service)
    stored = packets.build(base_payload(includeNodeIds=["secretnode"]))
    assert {e["nodeId"]: e["reason"] for e in stored["excluded"]} == {"secretnode": "not_found"}
    assert stored["content"]["neighbors"] == []
    assert "SOUKROMY_OBSAH_B" not in str(stored)


def test_utf8_byte_cap_truncates_optional_sections_with_reason(tmp_path):
    service = make_service(tmp_path)
    seed_graph(service)
    service.texts.access("draft", "draft", "friend", {
        "project": "draft", "workspace": "draft", "node": "friend", "expected_revision": 0, "text": "x" * 2000,
    })
    packets = ContextPackets(service)
    stored = packets.build(base_payload(includeNodeIds=["friend"], maxBytes=1000))
    assert stored["sizeBytes"] <= stored["maxBytes"]
    assert any(t["nodeId"] == "friend" and t["reason"] == "max_bytes_exceeded" for t in stored["truncated"])
    assert stored["content"]["neighbors"] == []


def test_focus_exceeding_budget_is_a_clear_error_not_silent_truncation(tmp_path):
    service = make_service(tmp_path)
    seed_graph(service)
    service.texts.access("draft", "draft", "focus", {
        "project": "draft", "workspace": "draft", "node": "focus", "expected_revision": 0, "text": "y" * 60000,
    })
    packets = ContextPackets(service)
    with pytest.raises(ValueError):
        packets.build(base_payload(maxBytes=1000))


def test_fake_credential_in_text_is_redacted(tmp_path):
    service = make_service(tmp_path)
    seed_graph(service)
    fake_key = "AKIAABCDEFGHIJKLMNOP"
    service.texts.access("draft", "draft", "focus", {
        "project": "draft", "workspace": "draft", "node": "focus", "expected_revision": 0,
        "text": f"credentials: {fake_key} nesmí uniknout",
    })
    packets = ContextPackets(service)
    stored = packets.build(base_payload())
    assert fake_key not in str(stored)
    assert "[REDACTED]" in stored["content"]["focus"]["text"]["text"]


@pytest.mark.parametrize("overrides", [
    {"maxBytes": -1},
    {"maxBytes": "50000"},
    {"maxBytes": 999999999},
    {"node": "not an id"},
    {"includeNodeIds": ["ok"] * 25},
    {"includeNodeIds": ["bad id"]},
    {"includeJournalDays": ["not-a-date"]},
    {"includeJournalDays": ["2026-13-40"]},
])
def test_invalid_inputs_are_rejected(tmp_path, overrides):
    service = make_service(tmp_path)
    seed_graph(service)
    packets = ContextPackets(service)
    with pytest.raises(ValueError):
        packets.build(base_payload(**overrides))


def test_missing_required_key_is_rejected(tmp_path):
    service = make_service(tmp_path)
    seed_graph(service)
    packets = ContextPackets(service)
    payload = base_payload()
    del payload["maxBytes"]
    with pytest.raises(ValueError):
        packets.build(payload)


def test_build_on_readonly_main_is_disallowed(tmp_path):
    import json
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    node = {"id": "node-1", "parentId": None, "kind": "node", "name": "Main", "purpose": "", "x": 0, "y": 0}
    git("init", "-b", "main")
    (repo / "opora-canvas.json").write_text(json.dumps({"nodes": [node], "edges": []}), encoding="utf-8")
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture")

    service = make_service(tmp_path)
    service.register_repository("p", "Project", repo, "https://github.com/example/project", "main")
    packets = ContextPackets(service)
    with pytest.raises(ValueError):
        packets.build(base_payload(project="p", workspace="main", node="node-1"))


def test_load_unknown_id_and_validate_unknown_id_raise(tmp_path):
    service = make_service(tmp_path)
    packets = ContextPackets(service)
    with pytest.raises(ValueError):
        packets.load("doesnotexist")
    with pytest.raises(ValueError):
        packets.validate("doesnotexist")
