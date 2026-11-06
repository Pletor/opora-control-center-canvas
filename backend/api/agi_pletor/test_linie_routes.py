"""Linie přes skutečnou aplikaci nad dočasným repozitářem: souhrn, přijetí a jeho zastarání, nasazení, 403, 422."""
import pytest
from fastapi.testclient import TestClient

from backend.agi_pletor.linie.test_branches import commit, make_repo, run
from backend.api.agi_pletor import linie_routes
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

JSON = {**HEADERS, "content-type": "application/json"}  # zápis (i DELETE) chce stejný Origin a JSON
AGENT = {**JSON, "X-Opora-Actor": "agent; name=dev"}
BASE = "/api/pletor/linie"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "repo")
    monkeypatch.setattr(linie_routes, "REPO_ROOT", repo)
    return repo


def test_linie_accept_and_deployed(tmp_path, repo):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        state = client.get(f"{BASE}/", headers=HEADERS)
        assert state.status_code == 200
        assert set(state.json()) == {"main", "develop", "server", "deployed", "branches", "previews", "enforcement"}
        assert state.json()["enforcement"] == "nevynuceno" and state.json()["previews"] == []
        head = run(repo, "rev-parse", "feat/a")
        accepted = client.post(f"{BASE}/accept", headers=HEADERS,
                               json={"branch": "feat/a", "sha": head, "target": "topic/1-t", "note": "vzhled ok"})
        assert accepted.status_code == 200

        def row():
            rows = client.get(f"{BASE}/", headers=HEADERS).json()["branches"]
            return next(b for b in rows if b["name"] == "feat/a")

        assert row()["acceptance"]["valid"] is True and row()["preview"] is None
        run(repo, "checkout", "-q", "feat/a")
        commit(repo, "e.txt")
        assert row()["acceptance"]["valid"] is False  # nová hlava = přijetí zastaralé
        assert client.delete(f"{BASE}/accept/feat/a", headers=JSON).status_code == 200
        assert row()["acceptance"] is None

        deployed = client.post(f"{BASE}/deployed", headers=HEADERS, json={"sha": head[:7]})
        assert deployed.status_code == 200 and deployed.json()["deployed"]["sha"] == head[:7]
        assert client.get(f"{BASE}/", headers=HEADERS).json()["deployed"]["sha"] == head[:7]

        diff = client.get(f"{BASE}/diff", headers=HEADERS, params={"branch": "feat/a", "target": "topic/1-t"})
        assert diff.status_code == 200 and diff.json()["files"] == 3 and len(diff.json()["commits"]) == 3


def test_linie_refusals(tmp_path, repo):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = {"branch": "feat/a", "sha": "abc1234", "target": "develop"}
        for method, path, payload in (("get", "/", None), ("get", "/diff", None), ("post", "/accept", body),
                                      ("delete", "/accept/feat/a", None), ("post", "/deployed", {"sha": "abc1234"}),
                                      ("post", "/previews", {"branch": "feat/a", "project": "draft"}),
                                      ("delete", "/previews/feat-a", None), ("get", "/previews/feat-a/log", None)):
            response = client.request(method, BASE + path, headers=AGENT, json=payload)
            assert response.status_code == 403, path
        for sha in ("xyz1234", "abc"):
            assert client.post(f"{BASE}/accept", headers=HEADERS, json={**body, "sha": sha}).status_code == 422
        assert client.post(f"{BASE}/accept", headers=HEADERS, json={**body, "target": "feat/b"}).status_code == 422
        assert client.post(f"{BASE}/deployed", headers=HEADERS, json={"sha": "nehex12"}).status_code == 422
        diff = client.get(f"{BASE}/diff", headers=HEADERS, params={"branch": "feat/nic", "target": "main"})
        assert diff.status_code == 422
        gone = client.post(f"{BASE}/previews", headers=HEADERS, json={"branch": "feat/a", "project": "nikde"})
        assert gone.status_code == 404
        assert client.delete(f"{BASE}/previews/nic", headers=JSON).status_code == 404
        assert client.get(f"{BASE}/previews/nic/log", headers=HEADERS).status_code == 404
