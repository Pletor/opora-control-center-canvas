from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.integrations.gitio import git
from backend.project.workspace.test_workspace_sources import ORIGIN, attach

IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false")
HEADERS = {"origin": ORIGIN}
ACTOR = {"kind": "human", "name": "Orchestrátor"}
FIELDS = {"goal": "Pozdrav", "non_goals": "Nic navíc", "acceptance": "Test prochází"}


def run(root, *args):
    return git(root, *IDENTITY, *args, timeout=30)


def source_repo(tmp_path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "hello.py").write_text("print('ahoj')\n", encoding="utf-8")
    run(source, "init", "-q", "-b", "main")
    run(source, "add", "-A")
    run(source, "commit", "-q", "-m", "zaklad")
    return source


def graph():
    return {
        "nodes": [
            {"id": "sector-1", "parentId": None, "kind": "sector", "name": "Zdroje",
             "purpose": "Sektor nad složkou src", "x": 0, "y": 0,
             "sourceRef": {"origin": "existing", "path": "src", "kind": "directory"}},
            {"id": "node-1", "parentId": "sector-1", "kind": "node", "name": "Pozdrav",
             "purpose": "", "x": 10, "y": 10,
             "sourceRef": {"origin": "existing", "path": "src/hello.py", "kind": "file"}},
        ],
        "edges": [],
    }


def save_graph(client, pid):
    view = client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()
    response = client.post("/api/graph", headers={"origin": ORIGIN}, json={
        "project": pid, "workspace": "draft", "graph": graph(), "digest": view["digest"],
    })
    assert response.status_code == 200, response.text


def report(client, pid):
    response = client.get("/api/sync-report", params={"project": pid, "workspace": "draft"})
    assert response.status_code == 200, response.text
    return response.json()


def types(payload):
    return {signal["type"] for signal in payload["signals"]}


def verdict_of(payload, scope_id):
    return next(item for item in payload["verdicts"] if item["scope"]["id"] == scope_id)


def test_report_pairs_existing_sources_and_blocks_merge_without_evidence(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        payload = report(client, pid)

    assert payload["project"] == pid and payload["gitHead"]
    assert {item["scope"]["id"] for item in payload["verdicts"]} == {"sector-1", "node-1"}
    # Zdroje existují, takže echo o vazbě nevzniká.
    assert "source-missing" not in types(payload) and "source-renamed" not in types(payload)
    # Commit se spáruje podle cest, ale bez důkazu a bez zeleného běhu testů se nemerguje.
    assert {"evidence-missing", "checks-unknown"} <= types(payload)
    node = verdict_of(payload, "node-1")
    assert node["canMerge"] is False
    assert node["state"] in ("draft", "waiting")
    assert [check["id"] for check in node["checks"]][:3] == ["spec", "source", "pair"]
    assert node["nextSteps"]
    assert payload["counts"]["signals"] == len(payload["signals"])


def test_report_reports_missing_source_after_the_file_disappears(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        (source / "src" / "hello.py").unlink()
        payload = report(client, pid)

    assert "source-missing" in types(payload)
    missing = next(item for item in payload["signals"] if item["type"] == "source-missing")
    assert missing["subject"]["id"] == "node-1"
    assert missing["severity"] == "high"
    assert verdict_of(payload, "node-1")["canMerge"] is False


def test_report_reports_renamed_source(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        run(source, "mv", "src/hello.py", "src/pozdrav.py")
        run(source, "commit", "-q", "-m", "prejmenovani")
        payload = report(client, pid)

    assert "source-renamed" in types(payload)
    renamed = next(item for item in payload["signals"] if item["type"] == "source-renamed")
    assert "src/pozdrav.py" in renamed["evidence"]["actual"]


def save_spec(client, pid):
    response = client.post("/api/node-spec", headers=HEADERS, json={
        "project": pid, "workspace": "draft", "node": "node-1",
        "expected_revision": 0, "fields": FIELDS,
    })
    assert response.status_code == 200, response.text


def commit_for_node(source):
    """Commit v mainu, který se hlásí k uzlu trailerem a nese revizi zadání.

    Datum je den dopředu schválně: git ukládá čas po sekundách, takže commit vzniklý
    ve stejné vteřině jako uložené zadání by vyšel jako starší a echo `spec-ahead`
    by drželo bránu zavřenou z čistě technického důvodu.
    """
    later = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    (source / "src" / "hello.py").write_text("print('ahoj svete')\n", encoding="utf-8")
    run(source, "add", "-A")
    run(source, "commit", "-q", "-m", "pozdrav", "-m", "Opora-Node: node-1@1", "--date", later)
    return run(source, "rev-parse", "HEAD")


def finish_process(client, pid):
    """Proces uzlu od návrhu až po hotovo; důkaz u kroku vyžaduje životní cyklus sám."""
    created = client.post("/api/processes", headers=HEADERS, json={
        "project": pid, "title": "Pozdrav", "nodeId": "node-1",
        "steps": ["Napsat pozdrav"], "by": ACTOR,
    })
    assert created.status_code == 200, created.text
    process = created.json()["process"]
    step = process["steps"][0]["id"]
    running = client.post(f"/api/processes/{process['id']}/transition", headers=HEADERS, json={
        "project": pid, "revision": process["revision"], "to": "running",
        "by": ACTOR, "note": "bez worktree",
    })
    assert running.status_code == 200, running.text
    marked = client.post(f"/api/processes/{process['id']}/steps/{step}", headers=HEADERS, json={
        "project": pid, "revision": running.json()["process"]["revision"], "state": "done",
        "evidence": {"summary": "hello.py napsán", "at": "2026-09-17T10:00:00Z", "by": ACTOR},
    })
    assert marked.status_code == 200, marked.text
    done = client.post(f"/api/processes/{process['id']}/transition", headers=HEADERS, json={
        "project": pid, "revision": marked.json()["process"]["revision"], "to": "done",
        "by": ACTOR, "note": "hotovo",
    })
    assert done.status_code == 200, done.text
    assert done.json()["process"]["state"] == "done"


def commit_spec(client, pid, scope="node-1"):
    """Commit zadání v OporaHubu; bez něj je zadání jen rozepsané a brána zůstane zavřená."""
    response = client.post("/api/opora-commit", headers=HEADERS, json={
        "project": pid, "workspace": "draft", "scope": scope,
        "subject": "zadání uzlu", "by": ACTOR,
    })
    assert response.status_code == 200, response.text
    return response.json()


def record_run(client, pid, sha, status="green"):
    response = client.post("/api/check-run", headers=HEADERS, json={
        "project": pid, "workspace": "draft", "scope": "node-1",
        "sha": sha, "status": status, "detail": "uv run pytest backend: prošlo",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_whole_way_to_green_opens_the_gate_for_the_node(tmp_path):
    """S11 z `docs/scenare-vrstvy.md`: zadání → commit → důkaz → zelený běh → `canMerge`."""
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        save_spec(client, pid)
        commit_spec(client, pid)
        sha = commit_for_node(source)
        finish_process(client, pid)
        written = record_run(client, pid, sha)
        assert written["sha"] == sha and written["status"] == "green"
        stored = client.get("/api/check-run", params={
            "project": pid, "workspace": "draft", "scope": "node-1"})
        assert stored.status_code == 200 and stored.json() == written
        payload = report(client, pid)

    node = verdict_of(payload, "node-1")
    assert [check["id"] for check in node["checks"] if not check["passed"]] == []
    assert node["canMerge"] is True
    assert node["state"] == "green"
    assert node["blocking"] == [] and node["nextSteps"] == []


def test_check_run_without_a_record_answers_that_nothing_is_known(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        empty = client.get("/api/check-run", params={
            "project": pid, "workspace": "draft", "scope": "node-1"})
        assert empty.status_code == 200 and empty.json() == {"status": None}
        refused = client.post("/api/check-run", headers=HEADERS, json={
            "project": pid, "workspace": "draft", "scope": "node-1",
            "sha": "nope", "status": "green", "detail": ""})
        assert refused.status_code == 409


def test_green_run_on_an_unpaired_commit_keeps_the_gate_closed(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        save_spec(client, pid)
        commit_for_node(source)
        finish_process(client, pid)
        record_run(client, pid, "0" * 40)
        payload = report(client, pid)

    assert "checks-unknown" in types(payload)
    assert "evidence-missing" not in {signal["type"] for signal in payload["signals"]
                                      if signal["subject"]["id"] == "node-1"}
    assert verdict_of(payload, "node-1")["canMerge"] is False


def test_report_survives_project_without_source(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        payload = report(client, "draft")

    assert payload["gitHead"] is None
    assert payload["verdicts"] == [] or all(item["scope"]["id"] for item in payload["verdicts"])


def test_uncommitted_spec_keeps_the_gate_closed_and_says_why(tmp_path):
    """Zadání bez commitu OporaHubu je jen rozepsané; kontrola `spec` neprojde."""
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        save_spec(client, pid)
        sha = commit_for_node(source)
        finish_process(client, pid)
        record_run(client, pid, sha)
        payload = report(client, pid)

    node = verdict_of(payload, "node-1")
    assert node["canMerge"] is False
    assert [check["id"] for check in node["checks"] if not check["passed"]] == ["spec"]
    assert "opora-uncommitted" in types(payload)


def test_merge_is_refused_while_the_gate_is_closed_and_passes_when_it_opens(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        save_spec(client, pid)
        head = commit_spec(client, pid)
        refused = client.post("/api/opora-merge", headers=HEADERS, json={
            "project": pid, "workspace": "draft", "scope": "node-1", "id": head["id"], "by": ACTOR})
        assert refused.status_code == 409
        assert refused.json()["nextSteps"]

        sha = commit_for_node(source)
        finish_process(client, pid)
        record_run(client, pid, sha)
        merged = client.post("/api/opora-merge", headers=HEADERS, json={
            "project": pid, "workspace": "draft", "scope": "node-1", "id": head["id"], "by": ACTOR})
        assert merged.status_code == 200, merged.text
        assert merged.json()["inMain"] is True

        history = client.get("/api/opora-commits", params={
            "project": pid, "workspace": "draft", "scope": "node-1"})
        assert history.status_code == 200
        assert history.json()["main"]["id"] == head["id"]


def test_agent_may_not_commit_the_spec(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid)
        save_spec(client, pid)
        refused = client.post("/api/opora-commit", headers=HEADERS, json={
            "project": pid, "workspace": "draft", "scope": "node-1",
            "subject": "zkusím to sám", "by": {"kind": "agent", "name": "Claude"}})
        assert refused.status_code == 409
        assert client.get("/api/opora-commits", params={
            "project": pid, "workspace": "draft", "scope": "node-1"}).json()["items"] == []
