from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.drawings import validate_scene

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
ROOT = {"project": "draft", "workspace": "draft", "layer": ""}
ELEMENT = {
    "id": "shape-1",
    "type": "rectangle",
    "x": 1,
    "y": 2,
    "width": 30,
    "height": 40,
    "customData": {"kept": True},
}


def drawing(client, scope=ROOT):
    return client.get("/api/drawing", params=scope)


def save(client, scene, expected_revision=0, scope=ROOT):
    return client.post(
        "/api/drawing",
        headers=HEADERS,
        json={**scope, "expected_revision": expected_revision, "scene": scene},
    )


def test_empty_drawing_is_read_only_free_and_persists_across_restart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        before = drawing(client)
        assert before.status_code == 200
        assert before.json() == {
            "scene": {"elements": []},
            "revision": 0,
            "readOnly": False,
            "available": True,
            "source": "Lokální kresba v SQLite; není součástí Git commitů.",
            "saved_at": None,
        }
        saved = save(client, {"elements": [ELEMENT]})
        assert saved.status_code == 200
        assert saved.json()["revision"] == 1
        assert saved.json()["scene"]["elements"][0]["customData"] == {"kept": True}
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        restored = drawing(client).json()
        assert restored["revision"] == 1 and restored["scene"] == {"elements": [ELEMENT]}


def test_stale_and_concurrent_drawing_saves_cannot_both_commit(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as first, TestClient(app, base_url=ORIGIN) as second:
        payload = {"elements": [ELEMENT]}
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda c: save(c, payload).status_code, [first, second]))
        assert sorted(statuses) == [200, 409]
        assert drawing(first).json()["revision"] == 1
        assert save(first, {"elements": []}).status_code == 409
        assert (
            app.state.service.db.execute("SELECT COUNT(*) FROM drawing_revisions").fetchone()[0]
            == 1
        )


@pytest.mark.parametrize(
    "scene",
    [
        {"elements": [{**ELEMENT, "id": "a"}, {**ELEMENT, "id": "a"}]},
        {"elements": [{**ELEMENT, "type": "image"}]},
        {"elements": [{**ELEMENT, "link": "javascript:alert(1)"}]},
        {"elements": [{**ELEMENT, "link": "https://"}]},
        {"elements": "not-a-list"},
        {"elements": [{**ELEMENT, "type": "text", "text": {"bad": "type"}}]},
        {"elements": [{**ELEMENT, "type": "line", "points": "bad"}]},
        {"elements": [{**ELEMENT, "type": "freedraw", "points": [[0, "bad"]]}]},
        {"elements": [{**ELEMENT, "type": []}]},
        {"elements": [{**ELEMENT, "x": 10**400}]},
        {"elements": [{**ELEMENT, "seed": 10**400}]},
    ],
)
def test_invalid_scene_does_not_create_revision(tmp_path, scene):
    with TestClient(create_app(tmp_path), base_url=ORIGIN, raise_server_exceptions=False) as client:
        result = save(client, scene)
        assert result.status_code == 409
        assert drawing(client).json()["revision"] == 0


def test_scene_rejects_nonfinite_geometry_before_storage():
    with pytest.raises(ValueError):
        validate_scene({"elements": [{**ELEMENT, "x": float("inf")}]})


def test_layer_scope_and_main_and_archived_project_are_guarded(tmp_path, monkeypatch):
    app = create_app(tmp_path / "data")
    service = app.state.service
    service.register_repository("p", "Project", str(tmp_path / "repo"), "fixture://p", "main")
    service.register_repository(
        "other", "Other", str(tmp_path / "other"), "fixture://other", "main"
    )
    service.db.execute(
        "INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)",
        (
            "other-workspace",
            "other",
            str(tmp_path / "other-work"),
            "work/other",
            "node",
            "Test",
            "base",
        ),
    )
    service.db.execute("INSERT INTO archived_projects VALUES(?,?,?)", ("other", "{}", "now"))
    service.db.commit()

    def fake_git(_root, *args, **_kwargs):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("branch", "--show-current"):
            return "main"
        return None

    monkeypatch.setattr("backend.service.git", fake_git)
    with TestClient(app, base_url=ORIGIN) as client:
        assert drawing(client, {**ROOT, "layer": "missing"}).status_code == 409
        main = drawing(client, {"project": "p", "workspace": "main", "layer": ""})
        assert main.status_code == 200
        assert main.json()["readOnly"] is True and main.json()["available"] is False
        assert (
            save(
                client, {"elements": []}, scope={"project": "p", "workspace": "main", "layer": ""}
            ).status_code
            == 409
        )
        assert (
            drawing(
                client, {"project": "p", "workspace": "other-workspace", "layer": ""}
            ).status_code
            == 409
        )
        assert (
            drawing(client, {"project": "other", "workspace": "main", "layer": ""}).status_code
            == 409
        )
