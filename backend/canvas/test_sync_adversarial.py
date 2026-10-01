"""Nepřátelské scénáře vrstvy OPORA → kód → git → Oracle.

Skupina A zkouší chybujícího agenta, skupina B kritika, který chce bránu obejít. Nic se
nemockuje: každý test staví vlastní git repozitář v `tmp_path` a mluví přes HTTP API.
Kontrakt je `docs/synchronizace-pravdy.md` (části 4, 6, 7 a 8), scénáře `docs/scenare-vrstvy.md`.
Scénář, který aplikace neustojí, se nesimuluje ani neobchází: test je napsaný tak, jak se
aplikace chovat má, a nese `xfail(strict=True)` s důvodem. Až díl vznikne, `strict` to ohlásí.
"""

import shutil
import stat
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.integrations.gitio import git

ORIGIN = "http://127.0.0.1:8740"
IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false")
# Pevná data commitů: pořadí „zadání proti kódu“ nesmí stát na tom, že git tiká po sekundách.
OLD, NEW = "2020-01-01T00:00:00+00:00", "2030-01-01T00:00:00+00:00"


def run(root, *args):
    return git(root, *IDENTITY, *args, timeout=30)


def source_repo(tmp_path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "hello.py").write_text("print('ahoj')\n", encoding="utf-8")
    run(source, "init", "-q", "-b", "main")
    run(source, "add", "-A")
    run(source, "commit", "-q", "--date", OLD, "-m", "zaklad")
    return source


def commit(source, path, text, message, date=NEW):
    target = source / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    run(source, "add", "-A")
    run(source, "commit", "-q", "--date", date, "-m", message)


def wipe(path):
    """Smaže strom i s objekty gitu, které jsou na Windows jen pro čtení."""
    def clear(func, target, _error):
        Path(target).chmod(stat.S_IWRITE)
        func(target)
    shutil.rmtree(path, onexc=clear)


def attach(client, source):
    project = {"name": "Source project", "path": str(source), "confirmed": True}
    response = client.post("/api/local-project", headers={"origin": ORIGIN}, json=project)
    assert response.status_code == 200, response.text
    return response.json()["id"]


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


def view(client, pid):
    return client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()


def save(client, pid, value, expect=200):
    response = client.post("/api/graph", headers={"origin": ORIGIN}, json={
        "project": pid, "workspace": "draft", "graph": value, "digest": view(client, pid)["digest"],
    })
    assert response.status_code == expect, response.text
    return response


def spec(client, pid, node, revision, goal, expect=200):
    response = client.post("/api/node-spec", headers={"origin": ORIGIN}, json={
        "project": pid, "workspace": "draft", "node": node, "expected_revision": revision,
        "fields": {"goal": goal, "non_goals": "", "acceptance": ""}})
    assert response.status_code == expect, response.text
    return response


def read_spec(client, pid, node):
    response = client.get("/api/node-spec",
                          params={"project": pid, "workspace": "draft", "node": node})
    assert response.status_code == 200, response.text
    return response.json()


def drop_node(client, pid, target):
    where = {"project": pid, "workspace": "draft", "kind": "node", "target": target}
    preview = client.get("/api/removal-preview", params=where)
    assert preview.status_code == 200, preview.text
    response = client.post("/api/remove", headers={"origin": ORIGIN},
                           json={**where, "digest": preview.json()["digest"], "confirmed": True})
    assert response.status_code == 200, response.text


def report(client, pid, expect=200):
    response = client.get("/api/sync-report", params={"project": pid, "workspace": "draft"})
    assert response.status_code == expect, response.text
    return response.json()


def types(payload):
    return {signal["type"] for signal in payload["signals"]}


def verdict_of(payload, scope_id):
    return next(item for item in payload["verdicts"] if item["scope"]["id"] == scope_id)


def check_of(verdict, check_id):
    return next(check for check in verdict["checks"] if check["id"] == check_id)


# --- Skupina A: chybující agent -------------------------------------------------------

def test_a1_link_to_a_path_that_is_not_on_disk_is_refused(tmp_path):
    source = source_repo(tmp_path)
    broken = graph()
    broken["nodes"][1]["sourceRef"] = {"origin": "existing", "path": "src/chybi.py", "kind": "file"}
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        response = save(client, pid, broken, expect=409)
        assert "soubor" in response.json()["error"].lower()
        # Odmítnuté uložení nesmí nechat na plátně ani kus grafu.
        assert view(client, pid)["graph"]["nodes"] == []
        assert report(client, pid)["verdicts"] == []


def test_a2_two_saves_of_the_same_spec_revision_keep_the_first_text(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        assert spec(client, pid, "node-1", 0, "prvni zadani").json()["revision"] == 1
        # Druhý agent drží stejnou očekávanou revizi: nesmí přepsat, co už je uložené.
        conflict = spec(client, pid, "node-1", 0, "druhe zadani", expect=409)
        assert "Konflikt" in conflict.json()["error"]
        current = read_spec(client, pid, "node-1")
        assert current["revision"] == 1 and current["fields"]["goal"] == "prvni zadani"


def test_a3_spec_without_a_node_in_the_graph_is_reported(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        spec(client, pid, "node-1", 0, "zadani k smazanemu uzlu")
        drop_node(client, pid, "node-1")
        payload = report(client, pid)
        assert [item["scope"]["id"] for item in payload["verdicts"]] == ["sector-1"]
        # Zadání se smazáním uzlu nezmizelo: nový uzel téhož id ho dostane zpět.
        save(client, pid, graph())
        assert read_spec(client, pid, "node-1")["fields"]["goal"] == "zadani k smazanemu uzlu"
    orphan = [item for item in payload["signals"] if item["subject"]["id"] == "node-1"]
    assert orphan, "osiřelé zadání musí vydat echo (workspace-orphan podle části 7 kontraktu)"


def test_a4_commit_outside_every_owned_path_raises_code_unclaimed(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        commit(source, "tools/build.py", "print('build')\n", "nastroj mimo zadani")
        payload = report(client, pid)
    unclaimed = [item for item in payload["signals"] if item["type"] == "code-unclaimed"]
    # Vlastněná cesta echo nevydá: základní commit nad src/hello.py se spáruje podle cesty.
    assert len(unclaimed) == 1 and unclaimed[0]["subject"]["id"] == payload["gitHead"]
    assert unclaimed[0]["severity"] == "medium" and "code-unclaimed" in types(payload)


def test_a5_green_run_for_a_foreign_commit_does_not_open_the_gate(tmp_path):
    """Zelený běh zapsaný na commit mimo pár uzlu bránu neotevře; nesmysl místo SHA se odmítne."""
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        commit(source, "tools/build.py", "print('build')\n", "cizi commit")
        foreign = run(source, "rev-parse", "HEAD")
        refused = client.post("/api/check-run", headers={"origin": ORIGIN}, json={
            "project": pid, "workspace": "draft", "scope": "node-1",
            "sha": "neni-sha", "status": "green", "detail": ""})
        assert refused.status_code == 409, refused.text
        written = client.post("/api/check-run", headers={"origin": ORIGIN}, json={
            "project": pid, "workspace": "draft", "scope": "node-1",
            "sha": foreign, "status": "green", "detail": "prošlo jinde"})
        assert written.status_code == 200, written.text
        payload = report(client, pid)
    # Běh je zapsaný, ale patří commitu, který se k uzlu nehlásí; kontrola `checks` neprojde.
    assert "checks-unknown" in types(payload)
    node = next(item for item in payload["verdicts"] if item["scope"]["id"] == "node-1")
    assert node["canMerge"] is False


# --- Skupina B: kritik, který chce bránu obejít ----------------------------------------

def test_b1_source_ref_cannot_leave_the_project(tmp_path):
    source = source_repo(tmp_path)
    escapes = ["../mimo.py", "src/../../mimo.py", "/etc/passwd", "C:/Windows/win.ini", "src/.git"]
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        for path in escapes:
            bad = graph()
            bad["nodes"][1]["sourceRef"] = {"origin": "existing", "path": path, "kind": "file"}
            save(client, pid, bad, expect=409)
        assert view(client, pid)["graph"]["nodes"] == []


def test_b2_forged_trailer_alone_does_not_pair_the_scope(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        spec(client, pid, "node-1", 0, "zadani uzlu")
        commit(source, "tools/nic.py", "# nic\n", "uklid\n\nOpora-Node: node-1@99")
        payload = report(client, pid)
    node = verdict_of(payload, "node-1")
    assert node["canMerge"] is False
    assert check_of(node, "pair")["passed"] is False, "trailer bez vlastněné cesty není pár"


def test_b3_rewritten_history_does_not_look_finished(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        spec(client, pid, "node-1", 0, "uprav pozdrav")
        # Poctivý pár: commit sahá na vlastněnou cestu a hlásí revizi, kterou zadání má.
        # Trailer tu být musí: bez něj je `revisionInCode` None a `spec-ahead` drží kontrolu
        # `pair` zavřenou navždy, i když commit sedí na cestě i na čase (nález k části 6).
        commit(source, "src/hello.py", "print('ahoj svete')\n",
               "uprava pozdravu\n\nOpora-Node: node-1@1")
        before = report(client, pid)
        assert check_of(verdict_of(before, "node-1"), "pair")["passed"] is True
        # Kritik přepíše historii: spárovaný commit v mainu není.
        run(source, "reset", "--hard", "-q", "HEAD~1")
        after = report(client, pid)
    assert after["gitHead"] != before["gitHead"]
    node = verdict_of(after, "node-1")
    assert node["canMerge"] is False and node["state"] != "green"
    assert check_of(node, "pair")["passed"] is False and "spec-ahead" in types(after)


def test_b4_report_survives_a_repository_without_main(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        run(source, "branch", "-m", "main", "jina")
        payload = report(client, pid)
    assert payload["gitHead"] and len(payload["verdicts"]) == 2
    assert verdict_of(payload, "node-1")["canMerge"] is False


def test_b5_report_answers_even_without_a_git_directory(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        wipe(source / ".git")
        payload = report(client, pid)
    assert payload["gitHead"] is None and len(payload["verdicts"]) == 2
    assert verdict_of(payload, "node-1")["canMerge"] is False
    assert payload["counts"]["signals"] == len(payload["signals"])


def test_b6_oversized_input_is_refused_with_a_clear_error(tmp_path):
    source = source_repo(tmp_path)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        save(client, pid, graph())
        spec(client, pid, "node-1", 0, "x" * 4001, expect=409)
        long_path = graph()
        long_path["nodes"][1]["sourceRef"]["path"] = "src/" + "a" * 3000
        assert "cesta" in save(client, pid, long_path, expect=409).json()["error"].lower()
        save(client, pid, crowd(2500), expect=409)
        # Graf v mezích projde a report na něm nespadne ani nezhloupne.
        save(client, pid, crowd(300))
        payload = report(client, pid)
    assert len(payload["verdicts"]) == 302
    assert all(item["canMerge"] is False for item in payload["verdicts"])


def crowd(count):
    value = graph()
    value["nodes"] += [
        {"id": f"n{index}", "parentId": "sector-1", "kind": "node", "name": f"Uzel {index}",
         "purpose": "", "x": index, "y": 0}
        for index in range(count)
    ]
    return value
