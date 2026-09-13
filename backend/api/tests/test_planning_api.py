import json

from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}


def test_plan_preview_uses_saved_project_and_wireframe_not_source_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    secret = source / "private.txt"
    secret.write_text("PRIVATE_FILE_MUST_NOT_REACH_MODEL", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        project = client.post("/api/local-project", headers=HEADERS, json={"name": "Landing", "path": str(source), "confirmed": True}).json()
        pid = project["id"]
        config = client.get("/api/project-settings", params={"project": pid}).json()
        config["settings"]["goal"] = "Navrhni srozumitelnou registraci"
        saved = client.post("/api/project-settings", headers=HEADERS, json={"project": pid, "expected_revision": 0, "name": "Landing", "settings": config["settings"]})
        assert saved.status_code == 200
        element = {"id": "button", "type": "rectangle", "x": 40, "y": 80, "width": 120, "height": 48, "customData": {"oporaWireframe": {"version": 1, "role": "element", "component": "button", "notes": "Primární CTA", "action": "Otevři registraci", "behavior": "Zobraz formulář", "animation": {"preset": "fade", "durationMs": 300, "delayMs": 0}, "parallax": {"enabled": False, "speed": 0}}}}
        drawing = client.post("/api/drawing", headers=HEADERS, json={"project": pid, "workspace": "draft", "layer": "", "expected_revision": 0, "scene": {"elements": [element]}})
        assert drawing.status_code == 200
        preview = client.get("/api/llm/preview", params={"project": pid, "workspace": "draft", "layer": ""})
        assert preview.status_code == 200
        context = preview.json()["context"]
        assert context["configRevision"] == 1
        assert context["wireframe"]["drawingRevision"] == 1
        assert context["wireframe"]["elements"][0]["wireframe"]["action"] == "Otevři registraci"
        assert "PRIVATE_FILE_MUST_NOT_REACH_MODEL" not in json.dumps(context)
        assert str(source) not in json.dumps(context)
        assert client.get("/api/llm/runs").json()["runs"] == []
