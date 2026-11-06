"""Linie přes skutečnou aplikaci nad dočasným repozitářem: souhrn, graf, nasazení, editor s kuličkami, 403/428/409."""
import pytest
from fastapi.testclient import TestClient

from backend.agi_pletor.linie.test_branches import run
from backend.agi_pletor.linie.test_work import agent_commit, cloned
from backend.api.agi_pletor import linie_routes, linie_work_routes
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

JSON = {**HEADERS, "content-type": "application/json"}  # zápis (i DELETE) chce stejný Origin a JSON
AGENT = {**JSON, "X-Opora-Actor": "agent; name=dev"}
BASE = "/api/pletor/linie"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo = cloned(tmp_path / "git")
    monkeypatch.setattr(linie_routes, "REPO_ROOT", repo)
    monkeypatch.setattr(linie_work_routes, "REPO_ROOT", repo)
    return repo


def test_linie_state_graph_and_deployed(tmp_path, repo):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        state = client.get(f"{BASE}/", headers=HEADERS)
        assert state.status_code == 200
        assert set(state.json()) == {"main", "develop", "server", "deployed", "branches", "previews", "enforcement"}
        assert state.json()["enforcement"] == "nevynuceno" and state.json()["previews"] == []
        drawn = client.get(f"{BASE}/graph", headers=HEADERS)
        assert drawn.status_code == 200
        assert set(drawn.json()) == {"lanes", "active", "server", "deployed", "enforcement"}
        assert drawn.json()["lanes"][0]["name"] == "main"
        head = run(repo, "rev-parse", "feat/a")
        deployed = client.post(f"{BASE}/deployed", headers=HEADERS, json={"sha": head[:7]})
        assert deployed.status_code == 200 and deployed.json()["deployed"]["sha"] == head[:7]
        assert client.get(f"{BASE}/", headers=HEADERS).json()["deployed"]["sha"] == head[:7]

        diff = client.get(f"{BASE}/diff", headers=HEADERS, params={"branch": "feat/a", "target": "develop"})
        assert diff.status_code == 200 and diff.json()["files"] == 2 and len(diff.json()["commits"]) == 2


def test_linie_refusals(tmp_path, repo):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        for method, path, payload in (("get", "/", None), ("get", "/graph", None), ("get", "/diff", None),
                                      ("post", "/deployed", {"sha": "abc1234"}),
                                      ("post", "/previews", {"branch": "feat/a", "project": "draft"}),
                                      ("delete", "/previews/feat-a", None), ("get", "/previews/feat-a/log", None)):
            response = client.request(method, BASE + path, headers=AGENT, json=payload)
            assert response.status_code == 403, path
        assert client.post(f"{BASE}/deployed", headers=HEADERS, json={"sha": "nehex12"}).status_code == 422
        diff = client.get(f"{BASE}/diff", headers=HEADERS, params={"branch": "feat/nic", "target": "main"})
        assert diff.status_code == 422
        gone = client.post(f"{BASE}/previews", headers=HEADERS, json={"branch": "feat/a", "project": "nikde"})
        assert gone.status_code == 404
        assert client.delete(f"{BASE}/previews/nic", headers=JSON).status_code == 404
        assert client.get(f"{BASE}/previews/nic/log", headers=HEADERS).status_code == 404


def test_linie_work_flow(tmp_path, repo):
    q = {"project": "draft"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        before = run(repo, "for-each-ref", "refs/heads")
        row = client.post(f"{BASE}/rows", headers=HEADERS, params=q, json={"name": "Uzel", "type": "work"})
        assert row.status_code == 200 and run(repo, "for-each-ref", "refs/heads") == before
        row_id = row.json()["id"]
        assert client.patch(f"{BASE}/rows/{row_id}", headers=JSON, params=q,
                            json={"collapsed": True}).json()["collapsed"] is True
        body = {"rowId": row_id, "title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"],
                "branch": "feat/uzel", "baseBranch": "develop", "target": "develop"}
        created = client.post(f"{BASE}/work", headers=HEADERS, params={**q, "workspace": "main"}, json=body)
        assert created.status_code == 200 and created.json()["state"] == "open"
        tid = created.json()["ticketId"]
        assert client.delete(f"{BASE}/rows/{row_id}", headers=JSON, params=q).json()["code"] == "row_in_use"

        head = agent_commit(repo)
        work = f"{BASE}/work/{tid}"
        report = {"sha": head, "checks": [{"name": "npm test", "status": "green"}]}
        assert client.post(f"{work}/report", headers=HEADERS, params=q, json=report).status_code == 200
        assert client.post(f"{work}/report", headers={**HEADERS, "X-Opora-Actor": "agent; name=dev"}, params=q,
                           json=report).json()["work"]["checks"][0]["by"] == "agent:dev"
        token = client.post("/api/gate/sessions", headers=AGENT, json={"project": "draft", "workspace": "main",
                                                        "worker": {"name": "office-1"}}).json()["token"]
        gated = client.get(work, headers={**AGENT, "X-Opora-Gate-Token": token}, params=q)
        assert gated.status_code == 200 and gated.json()["work"]["headSha"] == head
        off = client.post(f"{work}/report", headers={**AGENT, "X-Opora-Gate-Token": token}, params=q,
                          json={"sha": run(repo, "rev-parse", "feat/a")})
        assert off.status_code == 409 and off.json()["code"] == "work_mismatch"
        assert client.get(work, headers={**AGENT, "X-Opora-Gate-Token": "spatny"}, params=q).status_code == 401
        assert client.post(f"{work}/merge", headers=AGENT, params=q).json()["code"] == "no_acceptance"
        for path, payload in (("/accept", {"sha": head}), ("/allow-merge", {"target": "develop"})):
            assert client.post(work + path, headers=AGENT, params=q, json=payload).status_code == 403
        assert client.post(f"{work}/accept", headers=HEADERS, params=q, json={"sha": head}).json()["work"][
            "acceptance"]["sha"] == head
        drawn = client.get(f"{BASE}/graph", headers=HEADERS, params=q).json()
        assert next(lane for lane in drawn["lanes"] if lane["name"] == "feat/uzel")["acceptance"]["valid"] is True
        assert client.post(f"{work}/allow-merge", headers=HEADERS, params=q, json={}).status_code == 200
        merged = client.post(f"{work}/merge", headers=AGENT, params=q)
        assert merged.status_code == 200 and merged.json()["state"] == "merged"
        assert merged.json()["work"]["merged"]["sha"] == run(repo, "rev-parse", "origin/develop")
        board = client.get(f"{BASE}/board", headers=HEADERS, params={**q, "workspace": "main"}).json()
        assert board["balls"][0]["state"] == "merged" and board["realMerges"][0]["target"] == "develop"


def test_linie_work_derives_parent_and_refuses_wrong_one(tmp_path, repo):
    q = {"project": "draft", "workspace": "main"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        row = client.post(f"{BASE}/rows", headers=HEADERS, params=q, json={"name": "Uzel", "type": "work"}).json()["id"]
        body = {"rowId": row, "title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"]}
        derived = client.post(f"{BASE}/work", headers=HEADERS, params=q, json={**body, "branch": "feat/uzel"})
        assert derived.status_code == 200
        assert (derived.json()["work"]["baseBranch"], derived.json()["work"]["target"]) == ("develop", "develop")
        wrong = client.post(f"{BASE}/work", headers=HEADERS, params=q,
                            json={**body, "branch": "feat/uzel-tlacitko", "baseBranch": "main"})
        assert wrong.status_code == 422 and wrong.json()["code"] == "branch_hierarchy"
        stray = client.post(f"{BASE}/work", headers=HEADERS, params=q,
                            json={**body, "branch": "feat/jiny", "target": "main"})
        assert stray.status_code == 422 and stray.json()["code"] == "target_not_parent"


ATTACH = {"rowId": "main", "branch": "feat/x", "baseBranch": "develop"}


def test_linie_work_refusals(tmp_path, repo):
    q = {"project": "draft"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        for method, path, payload in (("get", "/board", None), ("post", "/rows", {"name": "x", "type": "work"}),
                                      ("post", "/work", {**ATTACH, "title": "t", "essence": "e", "build": "b",
                                                         "doneCriteria": ["d"]}),
                                      ("post", "/work/tk_1/accept", {"sha": "abc1234"}),
                                      ("delete", "/work/tk_1/accept", None), ("post", "/work/tk_1/allow-merge", {}),
                                      ("post", "/work/tk_1/preview", None), ("post", "/work/tk_1/attach", ATTACH)):
            assert client.request(method, BASE + path, headers=AGENT, params=q, json=payload).status_code == 403, path
        assert client.get(f"{BASE}/board", headers=HEADERS, params={"project": "nikde"}).status_code == 404
        client.cookies.clear()  # bez relačního dokladu UI a bez hlavičky agenta
        nobody = client.get(f"{BASE}/work/tk_1", headers=HEADERS, params=q)
        assert nobody.status_code == 428 and nobody.json()["code"] == "identity_required"
        assert client.post(f"{BASE}/work/tk_1/merge", headers=AGENT, params=q).status_code == 404


def test_linie_run_and_trace(tmp_path, repo):
    q = {"project": "draft"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        row = client.post(f"{BASE}/rows", headers=HEADERS, params=q, json={"name": "Uzel", "type": "work"}).json()["id"]
        body = {"rowId": row, "title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"],
                "branch": "feat/uzel", "baseBranch": "develop", "target": "develop"}
        created = client.post(f"{BASE}/work", headers=HEADERS, params={**q, "workspace": "main"}, json=body).json()
        tid, mark = created["ticketId"], created["work"]["mark"]
        agent_commit(repo)
        for _ in range(2):  # opakování = aktualizace, ne duplikát
            ran = client.post(f"{BASE}/work/{tid}/run", headers=AGENT, params=q, json={"sessionId": "s1", "agent": "dev"})
        assert ran.status_code == 200 and len(ran.json()["work"]["runs"]) == 1
        found = client.get(f"{BASE}/trace/{mark}", headers=HEADERS, params=q)
        assert found.status_code == 200 and found.json()["mark"] == mark and found.json()["runs"][0]["agent"] == "dev"
        assert client.get(f"{BASE}/trace/OP-000000", headers=HEADERS, params=q).json()["code"] == "mark_not_found"


def test_linie_work_without_row_creates_branch_row(tmp_path, repo):
    q = {"project": "draft", "workspace": "main"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = {"title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"], "branch": "feat/uzel"}
        created = client.post(f"{BASE}/work", headers=HEADERS, params=q, json=body)
        assert created.status_code == 200
        board = client.get(f"{BASE}/board", headers=HEADERS, params=q).json()
        row = next(r for r in board["rows"] if r["branch"] == "feat/uzel")
        assert (row["name"], row["type"], row["depth"]) == ("feat/uzel", "work", 2)
        assert board["balls"][0]["rowId"] == row["id"] == created.json()["work"]["rowId"]
