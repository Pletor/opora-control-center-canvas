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
        # The global token read guard must preserve native ticket ownership checks.
        wrong_workspace = client.post("/api/gate/sessions", headers=AGENT,
            json={"project": "draft", "workspace": "draft", "worker": {"name": "outside"}}).json()["token"]
        denied = client.get(work, headers={**AGENT, "X-Opora-Gate-Token": wrong_workspace}, params=q)
        assert denied.status_code == 403 and denied.json()["code"] == "gate_scope"
        foreign_query = client.get(work, headers={**AGENT, "X-Opora-Gate-Token": token}, params={"project": "foreign"})
        assert foreign_query.status_code == 403 and foreign_query.json()["code"] == "gate_scope"
        off = client.post(f"{work}/report", headers={**AGENT, "X-Opora-Gate-Token": token}, params=q,
                          json={"sha": run(repo, "rev-parse", "feat/a")})
        assert off.status_code == 409 and off.json()["code"] == "work_mismatch"
        assert client.get(work, headers={**AGENT, "X-Opora-Gate-Token": "spatny"}, params=q).status_code == 401
        early = client.post(f"{work}/merge", headers=AGENT, params=q)  # L7 §2a: pending merge nepovoluje
        assert early.status_code == 409 and early.json()["code"] == "action_not_allowed"
        for path, payload in (("/accept-merge", {"sha": head}),):  # L7g: přijmout a začlenit jen člověk
            assert client.post(work + path, headers=AGENT, params=q, json=payload).status_code == 403
        untried = client.post(f"{work}/accept", headers=AGENT, params=q, json={"sha": head})
        assert untried.status_code == 409 and untried.json()["code"] == "not_tried"
        acceptance = client.post(f"{work}/accept", headers=AGENT, params=q,
                                 json={"sha": head, "untested": True}).json()["work"]["acceptance"]
        assert acceptance["sha"] == head and acceptance["by"] == "agent:dev" and acceptance["tested"] is None
        drawn = client.get(f"{BASE}/graph", headers=HEADERS, params=q).json()
        assert next(lane for lane in drawn["lanes"] if lane["name"] == "feat/uzel")["acceptance"]["valid"] is True
        allowed = client.post(f"{work}/allow-merge", headers=AGENT, params=q, json={})
        assert allowed.status_code == 200 and allowed.json()["work"]["mergeAllowed"]["by"] == "agent:dev"
        merged = client.post(f"{work}/merge", headers=AGENT, params=q)
        assert merged.status_code == 200 and merged.json()["state"] == "merged"
        assert merged.json()["work"]["merged"]["sha"] == run(repo, "rev-parse", "origin/develop")
        board = client.get(f"{BASE}/board", headers=HEADERS, params={**q, "workspace": "main"}).json()
        assert board["balls"][0]["state"] == "merged" and board["balls"][0]["trial"]["state"] == "none"
        assert merged.json()["work"]["merged"]["mode"] == "squash"  # feat/* jedním commitem, bez merge commitu
        assert client.post(f"{work}/merge", headers=AGENT, params=q).status_code == 200  # začleněné = idempotentní


def test_linie_board_snapshot_summary_and_accept_on_nocheck(tmp_path, repo):
    q = {"project": "draft", "workspace": "main"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = {"title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"], "branch": "feat/uzel"}
        tid = client.post(f"{BASE}/work", headers=HEADERS, params=q, json=body).json()["ticketId"]
        early = client.post(f"{BASE}/work/{tid}/preview", headers=JSON, params=q)  # bez HEAD není co spustit
        assert early.status_code == 409 and early.json()["code"] == "action_not_allowed"
        revoke = client.delete(f"{BASE}/work/{tid}/accept", headers=JSON, params=q)
        assert revoke.status_code == 409 and revoke.json()["code"] == "action_not_allowed"
        head = agent_commit(repo)
        client.post(f"{BASE}/work/{tid}/report", headers=AGENT, params=q, json={"sha": head})
        refused = client.post(f"{BASE}/work/{tid}/accept", headers=HEADERS, params=q, json={"sha": head})
        assert refused.status_code == 409 and refused.json()["code"] == "action_not_allowed"
        assert refused.json()["error"].startswith(f"work.submitted & checks.missing({head[:7]})")
        detail = client.get(f"{BASE}/work/{tid}", headers=AGENT, params=q).json()
        assert detail["summary"]["key"] == "nocheck" and detail["axes"]["checks"]["state"] == "missing"
        board = client.get(f"{BASE}/board", headers=HEADERS, params=q).json()
        ball = board["balls"][0]
        assert set(board["snapshot"]["sources"]) == {"git", "prs", "checks", "sessions", "deploy"}
        assert board["snapshot"]["id"].startswith("snap_") and board["snapshot"]["builtAt"]
        assert ball["summary"]["key"] == "nocheck" and ball["state"] == "awaiting_checks"
        assert "accept" in ball["blocked"] and ball["allowed"] == ["preview", "defer", "block"]
        assert "deploy" not in ball["incomplete"]
        assert [item["kind"] for item in ball["evidence"]] == ["commit"]
        assert ball["queues"] == ["officeTasks"] and board["queues"]["officeTasks"] == 1
        assert board["queues"]["plansWaiting"] is None  # graf draft/main nejde přečíst = nevím, ne 0
        assert detail["plan"]["state"] == "none" and detail["plan"]["diff"] is False
        snap = board["snapshot"]["id"]
        by_plan = client.get(f"{BASE}/board", headers=HEADERS, params={**q, "group": "plan", "snapshot": snap}).json()
        assert by_plan["snapshot"]["id"] == snap and [b["ticketId"] for b in by_plan["balls"]] == [tid]
        assert by_plan["balls"][0]["rowId"] == "plan:none" and by_plan["rows"][0]["name"] == "bez plánu"
        gone = client.get(f"{BASE}/board", headers=HEADERS, params={**q, "group": "plan", "snapshot": "snap_nic"})
        assert gone.status_code == 404 and gone.json()["code"] == "snapshot_not_found"
        assert client.get(f"{BASE}/board", headers=HEADERS, params={**q, "group": "x"}).status_code == 422


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
                                      ("delete", "/work/tk_1/accept", None),
                                      ("post", "/work/tk_1/attach", ATTACH)):
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


def test_linie_deploy_origin_and_permission(tmp_path, repo):
    q = {"project": "draft"}
    head = run(repo, "rev-parse", "develop")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        refused = client.post(f"{BASE}/deploy", headers=HEADERS, params=q, json={"env": "preview", "sha": head})
        assert refused.status_code == 403 and refused.json()["code"] == "deploy_not_allowed"  # bez [linie.deploy] nikdo
        (repo / "opora.local.toml").write_text('[linie.deploy]\npreview = ["human", "agent:deploy"]\n', encoding="utf-8")
        human = client.post(f"{BASE}/deploy", headers=HEADERS, params=q, json={"env": "preview", "sha": head[:7]})
        assert human.status_code == 200 and human.json()["origin"] == "human" and human.json()["sha"] == head
        for headers, env in ((AGENT, "preview"), (HEADERS, "production")):  # agent dev ani cizí prostředí nesmí
            assert client.post(f"{BASE}/deploy", headers=headers, params=q,
                               json={"env": env, "sha": head}).json()["code"] == "deploy_not_allowed"
        script = {**JSON, "X-Opora-Actor": "agent; name=deploy"}
        machine = client.post(f"{BASE}/deploy", headers=script, params=q, json={"env": "preview", "sha": head})
        assert machine.status_code == 200 and machine.json()["origin"] == "environment"
        assert client.post(f"{BASE}/deploy", headers=HEADERS, params=q,
                           json={"env": "preview", "sha": head, "repo": str(tmp_path)}).status_code == 422
        assert client.post(f"{BASE}/deploy", headers=HEADERS, params=q,
                           json={"env": "preview", "sha": "abc1234"}).status_code == 422
        board = client.get(f"{BASE}/board", headers=HEADERS, params={**q, "workspace": "main"}).json()
        assert board["deploy"]["envs"]["preview"] == {"sha": head, "at": machine.json()["at"], "origin": "environment",
                                                      "by": "agent:deploy"}
        # verifiedAt = přečtení záznamu při sestavení (čerstvé), stáří události je v envs[env].at
        read = board["snapshot"]["sources"]["deploy"]
        assert read["ok"] is True and read["verifiedAt"] >= machine.json()["at"]


def test_linie_merge_op_abandon_and_run_worktree(tmp_path, repo):
    q = {"project": "draft"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = {"title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"], "branch": "feat/uzel"}
        tid = client.post(f"{BASE}/work", headers=HEADERS, params={**q, "workspace": "main"}, json=body).json()["ticketId"]
        work = f"{BASE}/work/{tid}"
        ran = client.post(f"{work}/run", headers=AGENT, params=q,
                          json={"sessionId": "s1", "agent": "dev", "worktree": str(tmp_path / "wt")})
        assert ran.json()["work"]["runs"][0]["worktree"] == str(tmp_path / "wt")
        assert ran.json()["summary"]["text"] == "probíhá"  # čerstvý heartbeat s vazbou
        first = agent_commit(repo)
        head = agent_commit(repo, name="v.txt")
        client.post(f"{work}/report", headers=AGENT, params=q,
                    json={"sha": head, "checks": [{"name": "npm test", "status": "green"}]})
        gave_up = client.post(f"{work}/abandon", headers=AGENT, params=q, json={"sha": first, "why": "slepá ulička"})
        assert gave_up.status_code == 200 and gave_up.json()["work"]["headSha"] == head
        assert gave_up.json()["work"]["abandoned"][0]["by"] == "agent:dev"
        client.post(f"{work}/accept", headers=HEADERS, params=q, json={"sha": head, "untested": True})
        client.post(f"{work}/allow-merge", headers=HEADERS, params=q, json={})
        op = "6f1c2a8e-1b2c-4d3e-8f90-123456789abc"
        merged = client.post(f"{work}/merge", headers=AGENT, params=q, json={"op": op})
        assert merged.status_code == 200 and merged.json()["axes"]["integration"]["op"] == op
        tip = run(repo, "rev-parse", "origin/develop")
        again = client.post(f"{work}/merge", headers=AGENT, params=q, json={"op": op})
        assert again.status_code == 200 and again.json()["axes"]["integration"] == merged.json()["axes"]["integration"]
        assert run(repo, "rev-parse", "origin/develop") == tip and merged.json()["work"]["merged"]["by"] == "agent:dev"


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


def test_linie_board_txt_plain_text_for_agent_and_human(tmp_path, repo):
    q = {"project": "draft", "workspace": "main"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = {"title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"], "branch": "feat/uzel"}
        tid = client.post(f"{BASE}/work", headers=HEADERS, params=q, json=body).json()["ticketId"]
        head = agent_commit(repo)
        client.post(f"{BASE}/work/{tid}/report", headers=AGENT, params=q, json={"sha": head})
        for headers in (AGENT, HEADERS):
            text = client.get(f"{BASE}/board.txt", headers=headers, params=q)
            assert text.status_code == 200 and text.headers["content-type"] == "text/plain; charset=utf-8"
            assert text.text.startswith("Pletor: Na plátně 1 kulička") and "Čeká na člověka:" in text.text
            assert "Uzel · " in text.text and "Deník (posledních 20):" in text.text
        assert "Uzel" not in client.get(f"{BASE}/board.txt", headers=AGENT, params={**q, "mine": 1}).text.split("Řádky")[1]
        assert client.get(f"{BASE}/board.txt", headers=HEADERS, params={**q, "mine": 1}).status_code == 422


def test_linie_trial_preview_tried_and_accept(tmp_path, repo, monkeypatch):
    """Zkouška (docs/navrhy/2026-11-08-linie-zkouska.md): Vyzkoušet, tried jen člověk, přijetí podle zkoušky,
    restart náhledu po reportu, fronta s `trial`."""
    from backend.agi_pletor.linie import previews
    from backend.agi_pletor.linie.test_work import Alive
    q = {"project": "draft"}
    starts = []

    def start(folder, root, branch, project, data_root, now, fresh=False, **kwargs):
        starts.append((branch, fresh))
        record = {"slug": "feat-uzel", "branch": branch, "sha": run(root, "rev-parse", branch), "state": "running",
                  "port": 8790, "url": "http://127.0.0.1:8790/", "startedAt": now}
        previews._save(folder, {"feat-uzel": record})
        return record

    monkeypatch.setattr(previews, "start", start)
    monkeypatch.setitem(previews.RUNNING, "feat-uzel", Alive())
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = {"title": "Uzel", "essence": "Proč.", "build": "Uzel.", "doneCriteria": ["testy"],
                "branch": "feat/uzel", "baseBranch": "develop", "target": "develop"}
        tid = client.post(f"{BASE}/work", headers=HEADERS, params={**q, "workspace": "main"}, json=body).json()[
            "ticketId"]
        work = f"{BASE}/work/{tid}"
        green = [{"name": "npm test", "status": "green"}]
        head = agent_commit(repo)
        client.post(f"{work}/report", headers=AGENT, params=q, json={"sha": head, "checks": green})
        assert starts == []  # první spuštění je akce člověka
        none = client.post(f"{work}/tried", headers=JSON, params=q)
        assert none.status_code == 409 and none.json()["code"] == "preview_not_running"
        assert client.post(f"{work}/preview", headers=AGENT, params=q, json={"fresh": True}).status_code == 403
        shown = client.post(f"{work}/preview", headers=JSON, params=q, json={"fresh": True}).json()
        assert starts == [("feat/uzel", True)] and shown["work"]["preview"]["state"] == "running"
        assert shown["trial"]["state"] == "current" and shown["trial"]["url"] == "http://127.0.0.1:8790/"
        refused = client.post(f"{work}/accept", headers=JSON, params=q, json={"sha": head})
        assert refused.status_code == 409 and refused.json()["code"] == "not_tried"
        assert refused.json()["error"].startswith("Nevyzkoušeno, hlava je")
        assert client.post(f"{work}/tried", headers=AGENT, params=q).status_code == 403
        tried = client.post(f"{work}/tried", headers=JSON, params=q).json()
        assert tried["work"]["tried"]["sha"] == head and tried["trial"]["triedCurrent"] is True
        assert client.post(f"{work}/accept", headers=AGENT, params=q,
                           json={"sha": head}).json()["code"] == "not_tried"
        newer = agent_commit(repo, name="v.txt")
        far = client.post(f"{work}/report", headers=AGENT, params=q,
                          json={"sha": newer, "tryout": {"at": "https://evil.example/?a=1", "steps": []}})
        assert far.status_code == 422  # odkaz Vyzkoušet jen do náhledu
        client.post(f"{work}/report", headers=AGENT, params=q, json={
            "sha": newer, "checks": green, "tryout": {"at": "screen=pletor&part=linie", "steps": ["Otevři Linii"]}})
        assert starts[-1] == ("feat/uzel", False)  # report posunul hlavu: služba náhled restartuje, data drží
        shown = client.get(work, headers=JSON, params=q).json()
        assert shown["trial"]["state"] == "current" and shown["trial"]["news"] == [{"sha": newer,
                                                                                     "subject": "přidán v.txt"}]
        assert shown["trial"]["url"] == "http://127.0.0.1:8790/?screen=pletor&part=linie"
        assert shown["trial"]["steps"] == ["Otevři Linii"]
        queue = client.get(f"{BASE}/board", headers=HEADERS, params={**q, "workspace": "main"}).json()[
            "queues"]["human"]
        assert queue[0]["trial"]["tried"]["sha"] == head and queue[0]["trial"]["head"] == newer
        stale = client.post(f"{BASE}/work/{tid}/accept-merge", headers=JSON, params=q, json={"sha": newer})
        assert stale.status_code == 409 and stale.json()["code"] == "not_tried"
        assert f"Vyzkoušeno na {head[:7]}, hlava je {newer[:7]}." in stale.json()["error"]
        done = client.post(f"{BASE}/work/{tid}/accept-merge", headers=JSON, params=q,
                           json={"sha": newer, "untested": True}).json()
        assert done["summary"]["key"] == "merged" and done["work"]["acceptance"]["tested"] is None


def test_agent_creates_work_with_identity_scope_and_idempotency(tmp_path, repo):
    q = {"project": "draft", "workspace": "main"}
    body = {"title": "Autonomous", "essence": "Why", "build": "Task", "doneCriteria": ["tests"],
            "branch": "feat/autonomous", "idempotencyKey": "autonomous-create"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        client.cookies.clear()
        assert client.post(f"{BASE}/work", headers=JSON, params=q, json=body).status_code == 428
        created = client.post(f"{BASE}/work", headers=AGENT, params=q, json=body)
        assert created.status_code == 200
        repeated = client.post(f"{BASE}/work", headers=AGENT, params=q, json=body)
        assert repeated.status_code == 200 and repeated.json()["ticketId"] == created.json()["ticketId"]
        conflict = client.post(f"{BASE}/work", headers=AGENT, params=q, json={**body, "title": "Changed"})
        assert conflict.status_code == 409 and conflict.json()["code"] == "idempotency_conflict"
        events = client.get(f"{BASE}/journal", params=q).json()["events"]
        made = [event for event in events if event["kind"] == "linie.work.created"]
        assert len(made) == 1 and made[0]["by"] == "agent:dev"
        token = client.post("/api/gate/sessions", headers=AGENT,
            json={"project": "draft", "workspace": "main", "worker": {"name": "office-1"}}).json()["token"]
        gated = {**AGENT, "X-Opora-Gate-Token": token}
        payload = {**body, "branch": "feat/token", "idempotencyKey": "token-create"}
        assert client.post(f"{BASE}/work", headers=gated, params={**q, "workspace": "draft"},
                           json=payload).json()["code"] == "gate_scope"
        assert client.post(f"{BASE}/work", headers={**AGENT, "X-Opora-Gate-Token": "invalid"}, params=q,
                           json=payload).status_code == 401
        accepted = client.post(f"{BASE}/work", headers=gated, params=q, json=payload)
        assert accepted.status_code == 200
        events = client.get(f"{BASE}/journal", params=q).json()["events"]
        assert next(event for event in events if event["kind"] == "linie.work.created"
                    and event["by"] == "agent:office-1")
