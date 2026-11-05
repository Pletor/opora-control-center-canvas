"""Routy Dílny přes skutečnou aplikaci: měření (D0), editor skillů a funkcí, 201/404/409/422 a jen člověk."""
from fastapi.testclient import TestClient

from backend.agi_pletor.pletor_opora_settings import skills_store, workshop
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
BASE = "/api/pletor/workshop/tools"


def test_workshop_routes(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        tools = client.get(BASE, headers=HEADERS)
        assert tools.status_code == 200
        assert {"name": "rozdel_vety", "path": "rozdel_vety.py", "cases": 4} in tools.json()["tools"]
        measured = client.post(f"{BASE}/rozdel_vety/measure", headers=HEADERS, json={})
        assert measured.status_code == 200
        assert measured.json()["passed"] == 4 and measured.json()["deterministic"] is True
        assert client.post(f"{BASE}/neni/measure", headers=HEADERS, json={}).status_code == 404
        assert client.post(f"{BASE}/Spatny-nazev/measure", headers=HEADERS, json={}).status_code == 422
        assert client.get(BASE, headers=AGENT).status_code == 403
        assert client.post(f"{BASE}/rozdel_vety/measure", headers=AGENT, json={}).status_code == 403


def test_editor_routes(tmp_path, monkeypatch):
    """Zápisy jdou do podstrčených složek, ne do repa."""
    monkeypatch.setattr(workshop, "TOOLS", tmp_path / "tools")
    monkeypatch.setattr(skills_store, "SKILLS", tmp_path / "skills")
    (tmp_path / "tools").mkdir()
    skills = "/api/pletor/workshop/skills"
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        created = client.post(skills, headers=HEADERS, json={"name": "muj-skill"})
        assert created.status_code == 201 and created.json() == {"name": "muj-skill", "files": ["SKILL.md"]}
        assert client.post(skills, headers=HEADERS, json={"name": "muj-skill"}).status_code == 409
        assert client.post(skills, headers=HEADERS, json={"name": "Spatny"}).status_code == 422
        assert client.post(skills, headers=HEADERS, json={}).status_code == 422
        assert client.get(skills, headers=HEADERS).json()["skills"][0]["name"] == "muj-skill"

        file = f"{skills}/muj-skill/file"
        assert "## Postup" in client.get(file, headers=HEADERS, params={"path": "SKILL.md"}).json()["content"]
        assert client.get(file, headers=HEADERS, params={"path": "neni.md"}).status_code == 404
        assert client.get(f"{skills}/neni/file", headers=HEADERS).status_code == 404
        written = client.put(file, headers=HEADERS, json={"path": "scripts/a.py", "content": "x = 1\n"})
        assert written.status_code == 200 and written.json() == {"path": "scripts/a.py", "bytes": 6}
        assert client.put(file, headers=HEADERS, json={"path": "../a.md", "content": "x"}).status_code == 422
        assert client.put(file, headers=HEADERS, json={"path": "a.exe", "content": "x"}).status_code == 422

        assert client.post(BASE, headers=HEADERS, json={"name": "nova"}).status_code == 201
        assert client.post(BASE, headers=HEADERS, json={"name": "nova"}).status_code == 409
        tool = client.get(f"{BASE}/nova", headers=HEADERS).json()
        assert "def run" in tool["code"]
        assert client.get(f"{BASE}/neni", headers=HEADERS).status_code == 404
        bad = client.put(f"{BASE}/nova", headers=HEADERS, json={"code": tool["code"], "cases": "[{"})
        assert bad.status_code == 422 and "Případy" in bad.json()["error"]
        saved = client.put(f"{BASE}/nova", headers=HEADERS, json={"code": tool["code"], "cases": "[]"})
        assert saved.json() == {"name": "nova", "cases": 0}

        for method, url in [("get", skills), ("post", skills), ("get", file), ("put", file), ("get", f"{BASE}/nova"),
                            ("put", f"{BASE}/nova"), ("post", BASE)]:
            assert getattr(client, method)(url, headers=AGENT, **({} if method == "get" else {"json": {}})).status_code == 403
