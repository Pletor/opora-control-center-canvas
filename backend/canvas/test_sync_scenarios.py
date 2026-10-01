"""Scénáře vrstvy OPORA → kód → git → Oracle (S4 až S10 z `docs/scenare-vrstvy.md`).

Každý test staví skutečný git repozitář v `tmp_path`, projede ho skutečným API
(`/api/graph`, `/api/node-spec`, `/api/sync-report`) a ptá se jen na své echo a svůj
verdikt. Nic se nemockuje: echo počítá `sync_signals`, páry `commit_pairs` a stav cest
skutečný git. Počty cizího echa se nekontrolují, repozitář smí mít i jiné nálezy.
"""

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.integrations.gitio import git
from backend.project.workspace.test_workspace_sources import ORIGIN, attach

IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false")
HEADERS = {"origin": ORIGIN}


def run(root, *args):
    return git(root, *IDENTITY, *args, timeout=30)


def source_repo(tmp_path):
    """Repozitář s jedním commitem nad `src/hello.py`; větev `main`."""
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "hello.py").write_text("print('ahoj')\n", encoding="utf-8")
    run(source, "init", "-q", "-b", "main")
    run(source, "add", "-A")
    run(source, "commit", "-q", "-m", "zaklad")
    return source


def head_sha(source):
    return run(source, "rev-parse", "HEAD")


def ref(path, kind="file", origin="existing"):
    return {"origin": origin, "path": path, "kind": kind}


def sector():
    return {"id": "sector-1", "parentId": None, "kind": "sector", "name": "Zdroje",
            "purpose": "Sektor nad složkou src", "x": 0, "y": 0,
            "sourceRef": ref("src", kind="directory")}


def node(node_id, source_ref, name="Karta"):
    return {"id": node_id, "parentId": "sector-1", "kind": "node", "name": name,
            "purpose": "", "x": 10, "y": 10, "sourceRef": source_ref}


def save_graph(client, pid, nodes):
    view = client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()
    response = client.post("/api/graph", headers=HEADERS, json={
        "project": pid, "workspace": "draft",
        "graph": {"nodes": [sector(), *nodes], "edges": []},
        "digest": view["digest"],
    })
    assert response.status_code == 200, response.text


def save_spec(client, pid, node_id, goal):
    response = client.post("/api/node-spec", headers=HEADERS, json={
        "project": pid, "workspace": "draft", "node": node_id, "expected_revision": 0,
        "fields": {"goal": goal, "non_goals": "", "acceptance": "testy projdou"},
    })
    assert response.status_code == 200, response.text
    return response.json()


def add_workspace(service, pid, wid, node_id, base_sha, directory):
    """Řádek pracovního prostoru přímo do registru.

    `CanvasService.create_workspace` zakládá worktree jen projektu druhu `git`; projekt
    z `/api/local-project` je druhu `local`, takže by ho API odmítlo. Scénář ale potřebuje
    jen řádek v tabulce `workspaces`, ze kterého Oracle čte, ne skutečný worktree.
    """
    service.db.execute(
        "INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)",
        (wid, pid, str(directory), "work/" + wid, node_id, "Test", base_sha),
    )
    service.db.commit()


def report(client, pid):
    response = client.get("/api/sync-report", params={"project": pid, "workspace": "draft"})
    assert response.status_code == 200, response.text
    return response.json()


def echoes(payload, kind):
    return [signal for signal in payload["signals"] if signal["type"] == kind]


def verdict_of(payload, scope_id):
    return next(item for item in payload["verdicts"] if item["scope"]["id"] == scope_id)


def check_of(verdict, check_id):
    return next(check for check in verdict["checks"] if check["id"] == check_id)


def test_s4_planned_source_that_already_exists_reports_low_echo(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid, [node("node-1", ref("src/chystane.py", origin="planned"))])
        # Soubor vzniká až po uložení grafu: návrh byl v době zápisu opravdu jen návrhem.
        (source / "src" / "chystane.py").write_text("print('uz jsem tady')\n", encoding="utf-8")
        payload = report(client, pid)

    found = echoes(payload, "planned-exists")
    assert [item["subject"]["id"] for item in found] == ["node-1"]
    assert found[0]["severity"] == "low"
    assert found[0]["subject"]["path"] == "src/chystane.py"
    assert check_of(verdict_of(payload, "node-1"), "source")["passed"] is False


def test_s5_two_cards_on_one_path_make_a_single_duplicate_echo(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid, [node("node-a", ref("src/hello.py"), name="Prvni"),
                                 node("node-b", ref("src/hello.py"), name="Druha")])
        payload = report(client, pid)

    found = [item for item in echoes(payload, "duplicate-path")
             if item["subject"]["path"] == "src/hello.py"]
    assert len(found) == 1
    assert found[0]["severity"] == "medium"
    assert "node-a" in found[0]["evidence"]["actual"]
    assert "node-b" in found[0]["evidence"]["actual"]


def test_s6_spec_saved_after_the_last_commit_blocks_merge_but_not_work(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid, [node("node-1", ref("src/hello.py"))])
        (source / "src" / "hello.py").write_text("print('kod v1')\n", encoding="utf-8")
        run(source, "commit", "-q", "-a", "-m", "kod v1")
        # Zadání až po posledním commitu: kód je starší než revize, kterou má plnit.
        assert save_spec(client, pid, "node-1", "zadani v2")["revision"] == 1
        payload = report(client, pid)

    found = echoes(payload, "spec-ahead")
    assert [item["subject"]["id"] for item in found] == ["node-1"]
    assert found[0]["severity"] == "high"
    assert found[0]["subject"]["specRevision"] == 1
    verdict = verdict_of(payload, "node-1")
    assert verdict["canMerge"] is False
    # Zadání se smí měnit kdykoli; spec-ahead nikdy neblokuje práci ve větvi (část 4).
    assert verdict["canCommit"] is True


def test_s7_commit_outside_every_binding_is_code_unclaimed(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid, [node("node-1", ref("src/hello.py"))])
        (source / "mimo").mkdir()
        (source / "mimo" / "volny.py").write_text("print('bez zadani')\n", encoding="utf-8")
        run(source, "add", "-A")
        run(source, "commit", "-q", "-m", "kod bez zadani")
        sha = head_sha(source)
        payload = report(client, pid)

    found = [item for item in echoes(payload, "code-unclaimed") if item["subject"]["id"] == sha]
    assert len(found) == 1
    assert found[0]["severity"] == "medium"
    assert found[0]["evidence"]["source"].endswith(sha)


def test_s8_workspace_based_outside_main_is_base_stale(tmp_path):
    source = source_repo(tmp_path)
    run(source, "checkout", "-q", "-b", "mimo")
    (source / "src" / "stranou.py").write_text("print('stranou')\n", encoding="utf-8")
    run(source, "add", "-A")
    run(source, "commit", "-q", "-m", "vetev mimo main")
    stale = head_sha(source)
    run(source, "checkout", "-q", "main")
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid, [node("node-1", ref("src/hello.py"))])
        add_workspace(app.state.service, pid, "wstale", "node-1", stale, tmp_path / "wstale")
        payload = report(client, pid)

    found = echoes(payload, "base-stale")
    assert [item["subject"]["id"] for item in found] == ["wstale"]
    assert found[0]["severity"] == "medium"
    assert "work/wstale" in found[0]["evidence"]["actual"]


def test_s9_workspace_without_a_node_in_the_graph_is_orphan(tmp_path):
    source = source_repo(tmp_path)
    base = head_sha(source)
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid, [node("node-1", ref("src/hello.py"))])
        add_workspace(app.state.service, pid, "worphan", "node-nikde", base, tmp_path / "worphan")
        payload = report(client, pid)

    found = echoes(payload, "workspace-orphan")
    assert [item["subject"]["id"] for item in found] == ["worphan"]
    assert found[0]["severity"] == "low"
    assert "node-nikde" in found[0]["evidence"]["actual"]


def test_s10_broken_doc_link_fails_the_docs_check_of_the_bound_node(tmp_path):
    source = source_repo(tmp_path)
    (source / "src" / "modul").mkdir()
    (source / "src" / "modul" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (source / "docs").mkdir()
    (source / "docs" / "plan.md").write_text(
        "# Plan\n\nKarta staví `src/modul/chybi.py`.\n", encoding="utf-8")
    run(source, "add", "-A")
    run(source, "commit", "-q", "-m", "plan s odkazem")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save_graph(client, pid, [node("node-1", ref("src/modul", kind="directory"))])
        payload = report(client, pid)

    found = [item for item in echoes(payload, "doc-path-missing")
             if item["subject"]["path"] == "src/modul/chybi.py"]
    assert len(found) == 1
    assert found[0]["subject"]["id"].startswith("docs/plan.md:")
    assert check_of(verdict_of(payload, "node-1"), "docs")["passed"] is False
