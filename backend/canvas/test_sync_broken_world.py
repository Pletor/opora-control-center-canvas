"""Scénáře úrovně L5 vrstvy OPORA → kód → git → Oracle: rozbitý svět, zmatek a zátěž.

L5 se neptá, jestli proces funguje, ale jestli přežije poškozená data, zmatek v úložišti
a zátěž. Nic se nemockuje: každý test staví vlastní git repozitář v `tmp_path` a mluví přes
skutečné HTTP API; kontrakt je `docs/synchronizace-pravdy.md` (části 4, 6, 7 a 8), scénáře
`docs/scenare-vrstvy.md`. Scénář, který aplikace neustojí, se neobchází ani neopravuje:
test je napsaný tak, jak se aplikace chovat má, a nález patří do hlášení.
"""

import shutil
import stat
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.integrations.gitio import git

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
IDENTITY = ("-c", "user.name=Test", "-c", "user.email=t@e.cz", "-c", "commit.gpgsign=false")
ACTOR = {"kind": "human", "name": "Orchestrátor"}
FIELDS = {"goal": "Pozdrav", "non_goals": "Nic navíc", "acceptance": "Test prochází"}

def run(root, *args):
    return git(root, *IDENTITY, *args, timeout=60)

def source_repo(tmp_path, files=("src/hello.py",)):
    """Repozitář s větví `main`; zadané soubory jsou v prvním commitu."""
    source = tmp_path / "source"
    for name in files:
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        (source / name).write_text("print('ahoj')\n", encoding="utf-8")
    run(source, "init", "-q", "-b", "main")
    run(source, "add", "-A")
    run(source, "commit", "-q", "-m", "zaklad")
    return source

def wipe(path):
    """Smaže strom i s objekty gitu, které jsou na Windows jen pro čtení."""
    shutil.rmtree(path, onexc=lambda func, target, _error: (
        Path(target).chmod(stat.S_IWRITE), func(target)))

def client_for(tmp_path):
    """Klient, kterému pád serveru přijde jako odpověď: L5 se ptá i na to, zda přijde 500."""
    return TestClient(create_app(tmp_path / "data"), base_url=ORIGIN,
                      raise_server_exceptions=False)

def post(client, path, body):
    response = client.post(path, headers=HEADERS, json=body)
    assert response.status_code == 200, response.text
    return response.json()

def attach(client, source):
    return post(client, "/api/local-project",
                {"name": "Source project", "path": str(source), "confirmed": True})["id"]

def sector(ident, path, parent=None):
    return {"id": ident, "parentId": parent, "kind": "sector", "name": ident,
            "purpose": "Sektor nad složkou " + path, "x": 0, "y": 0,
            "sourceRef": {"origin": "existing", "path": path, "kind": "directory"}}

def node(ident, parent, path):
    return {"id": ident, "parentId": parent, "kind": "node", "name": ident, "purpose": "",
            "x": 10, "y": 10, "sourceRef": {"origin": "existing", "path": path, "kind": "file"}}

def pair_graph():
    return [sector("sector-1", "src"), node("node-1", "sector-1", "src/hello.py")]

def save_graph(client, pid, nodes, expect=200):
    view = client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()
    response = client.post("/api/graph", headers=HEADERS, json={
        "project": pid, "workspace": "draft", "graph": {"nodes": nodes, "edges": []},
        "digest": view["digest"]})
    assert response.status_code == expect, response.text

def ask(client, pid):
    return client.get("/api/sync-report", params={"project": pid, "workspace": "draft"})

def report(client, pid):
    response = ask(client, pid)
    assert response.status_code == 200, response.text
    return response.json()

def verdict_of(payload, scope_id):
    return next(item for item in payload["verdicts"] if item["scope"]["id"] == scope_id)

def check_of(verdict, check_id):
    return next(check for check in verdict["checks"] if check["id"] == check_id)

def save_spec(client, pid, scope):
    return post(client, "/api/node-spec", {"project": pid, "workspace": "draft", "node": scope,
                                           "expected_revision": 0, "fields": FIELDS})

def record_run(client, pid, scope, sha, status="green"):
    return post(client, "/api/check-run", {"project": pid, "workspace": "draft", "scope": scope,
                                           "sha": sha, "status": status, "detail": "pytest"})

def commit_spec(client, pid, scope):
    """Commit zadání v OporaHubu; bez něj je zadání jen rozepsané a brána zůstane zavřená."""
    return post(client, "/api/opora-commit", {"project": pid, "workspace": "draft",
                                              "scope": scope, "subject": "zadání", "by": ACTOR})

def commit_for(source, path, scope):
    """Commit v mainu, který se hlásí k rozsahu trailerem a nese revizi 1 zadání."""
    # Datum je den dopředu schválně: git ukládá čas po sekundách, takže commit z téže
    # vteřiny jako uložené zadání by vyšel jako starší a `spec-ahead` by držel bránu.
    later = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    (source / path).write_text("print('ahoj svete')\n", encoding="utf-8")
    run(source, "add", "-A")
    run(source, "commit", "-q", "-m", "prace", "-m", f"Opora-Node: {scope}@1", "--date", later)
    return run(source, "rev-parse", "HEAD")

def finish_process(client, pid, scope):
    """Proces rozsahu od návrhu po hotovo; důkaz u kroku vyžaduje životní cyklus sám."""
    process = post(client, "/api/processes", {"project": pid, "title": "Prace", "nodeId": scope,
                                              "steps": ["Napsat kod"], "by": ACTOR})["process"]
    step, path = process["steps"][0]["id"], f"/api/processes/{process['id']}"
    running = post(client, path + "/transition", {
        "project": pid, "revision": process["revision"], "to": "running",
        "by": ACTOR, "note": "bez worktree"})  # spuštění bez worktree chce výslovnou poznámku
    marked = post(client, f"{path}/steps/{step}", {
        "project": pid, "revision": running["process"]["revision"], "state": "done",
        "evidence": {"summary": "kód napsán", "at": "2026-09-17T10:00:00Z", "by": ACTOR}})
    done = post(client, path + "/transition", {
        "project": pid, "revision": marked["process"]["revision"], "to": "done",
        "by": ACTOR, "note": "hotovo"})
    assert done["process"]["state"] == "done"

def test_c1_corrupted_graph_in_the_database_answers_with_an_error(tmp_path):
    source = source_repo(tmp_path)
    with client_for(tmp_path) as client:
        pid = attach(client, source)
        save_graph(client, pid, pair_graph())
        # Zápis do databáze patří ke scénáři: přes API poškozený graf nevyrobíš (uložení
        # projde `validate_graph`), takhle vypadá až vadný disk nebo cizí zásah.
        db = client.app.state.service.db_for(pid)
        db.execute("UPDATE drafts SET graph='{' WHERE id=?", (pid,))
        db.commit()
        response = ask(client, pid)
    # Chyba, kterou klient pochopí: ne pád na 500 a ne prázdný report tvářící se jako pořádek.
    assert response.status_code in (409, 503), response.text
    assert response.json().get("error")

def test_c2_source_folder_that_disappears_is_reported_as_missing(tmp_path):
    source = source_repo(tmp_path)
    with client_for(tmp_path) as client:
        pid = attach(client, source)
        save_graph(client, pid, pair_graph())
        wipe(source)
        payload = report(client, pid)
    assert payload["gitHead"] is None
    assert {signal["subject"]["id"] for signal in payload["signals"]
            if signal["type"] == "source-missing"} == {"sector-1", "node-1"}
    assert all(item["canMerge"] is False for item in payload["verdicts"])
    assert check_of(verdict_of(payload, "node-1"), "source")["passed"] is False

def test_c3_file_that_turns_into_a_directory_raises_a_source_echo(tmp_path):
    source = source_repo(tmp_path)
    with client_for(tmp_path) as client:
        pid = attach(client, source)
        save_graph(client, pid, pair_graph())
        (source / "src" / "hello.py").unlink()  # cesta zůstává, mění se druh
        (source / "src" / "hello.py").mkdir()
        payload = report(client, pid)
    found = [signal for signal in payload["signals"] if signal["subject"]["id"] == "node-1"
             and signal["type"] in ("source-missing", "source-renamed")]
    assert found, "druh vazby nesedí, echo o vazbě musí vzniknout"
    assert found[0]["subject"]["path"] == "src/hello.py"
    verdict = verdict_of(payload, "node-1")
    assert check_of(verdict, "source")["passed"] is False
    # Echo o vazbě blokuje i práci ve větvi (část 8 kontraktu).
    assert verdict["canCommit"] is False

def test_c4_spec_on_a_scope_that_is_not_a_node_keeps_the_report_sane(tmp_path):
    source = source_repo(tmp_path)
    area = {"id": "area-1", "parentId": None, "kind": "area", "name": "Oblast",
            "purpose": "", "x": 0, "y": 0, "size": {"w": 600, "h": 400}}
    with client_for(tmp_path) as client:
        pid = attach(client, source)
        save_graph(client, pid, [*pair_graph(), area])
        assert save_spec(client, pid, "sector-1")["revision"] == 1
        assert save_spec(client, pid, "area-1")["revision"] == 1
        payload = report(client, pid)
    assert {item["scope"]["id"] for item in payload["verdicts"]} == {"sector-1", "node-1", "area-1"}
    # Každý druh rozsahu má vlastní kontroly z části 4; `spec` a `pair` patří jen uzlu.
    assert [check["id"] for check in verdict_of(payload, "sector-1")["checks"]] == [
        "source", "children", "noHighEcho"]
    assert [check["id"] for check in verdict_of(payload, "area-1")["checks"]] == ["children"]
    assert [check["id"] for check in verdict_of(payload, "node-1")["checks"]][:3] == [
        "spec", "source", "pair"]
    # Zadání u sektoru i u oblasti se počítá: obojí dostane echo ke svému rozsahu.
    assert {"sector-1", "area-1"} <= {signal["subject"]["id"] for signal in payload["signals"]
                                      if signal["type"] == "spec-ahead"}

def test_c5_deep_nesting_counts_the_deepest_floor(tmp_path):
    deep = "src/a/b/c/d/deep.py"
    source = source_repo(tmp_path, ["src/hello.py", deep])
    chain = [sector("sector-1", "src"), sector("sector-2", "src/a", "sector-1"),
             sector("sector-3", "src/a/b", "sector-2"), sector("sector-4", "src/a/b/c", "sector-3"),
             sector("sector-5", "src/a/b/c/d", "sector-4"), node("node-deep", "sector-5", deep)]
    area = {"id": "area-1", "parentId": None, "kind": "area", "name": "Oblast",
            "purpose": "", "x": 0, "y": 0, "size": {"w": 900, "h": 700}}
    with client_for(tmp_path) as client:
        pid = attach(client, source)
        # Strom pod oblast pověsit nejde; oblast je na plátně jen obdélník kolem karet.
        save_graph(client, pid, [area, *[dict(item, parentId=item["parentId"] or "area-1")
                                         for item in chain]], expect=409)
        save_graph(client, pid, [area, *chain])
        # Celá cesta k zelené pro uzel na dně: zadání → commit → důkaz → zelený běh.
        save_spec(client, pid, "node-deep")
        commit_spec(client, pid, "node-deep")
        sha = commit_for(source, deep, "node-deep")
        finish_process(client, pid, "node-deep")
        record_run(client, pid, "node-deep", sha)
        payload = report(client, pid)
    assert len(payload["verdicts"]) == 7  # oblast, pět pater sektorů a uzel na dně
    # Uzel na dně prošel branou; sektor nad ním i kořen o pět pater výš ho počítají.
    assert verdict_of(payload, "node-deep")["canMerge"] is True
    assert check_of(verdict_of(payload, "sector-5"), "children")["passed"] is True
    assert check_of(verdict_of(payload, "sector-1"), "children")["passed"] is True
    assert verdict_of(payload, "sector-1")["state"] == "green"
    # Oblast kreslená kolem stromu je podle části 4 taky zelená; prázdná by zelená nebyla.
    assert check_of(verdict_of(payload, "area-1"), "children")["passed"] is True
    assert verdict_of(payload, "area-1")["canMerge"] is True

def test_c6_two_hundred_nodes_and_forty_commits_answer_in_time(tmp_path):
    paths = [f"src/mod_{index:03d}.py" for index in range(200)]
    source = source_repo(tmp_path, paths)
    for index in range(39):  # 39 dalších commitů: v mainu jich je celkem 40
        (source / paths[index]).write_text(f"print({index})\n", encoding="utf-8")
        run(source, "commit", "-q", "-am", f"zmena {index}")
    nodes = [sector("sector-1", "src"),
             *[node(f"n{index:03d}", "sector-1", path) for index, path in enumerate(paths)]]
    with client_for(tmp_path) as client:
        pid = attach(client, source)
        save_graph(client, pid, nodes)
        start = time.perf_counter()
        payload = report(client, pid)
        elapsed = time.perf_counter() - start
    print(f"\nC6: jedno volání reportu nad 200 uzly a 40 commity trvalo {elapsed:.2f} s")
    assert len(payload["verdicts"]) == 201
    assert elapsed < 20, f"report trval {elapsed:.1f} s, mez je 20 s"

def test_c7_the_newer_check_run_decides_and_a_foreign_one_shuts_the_gate(tmp_path):
    source = source_repo(tmp_path)
    with client_for(tmp_path) as client:
        pid = attach(client, source)
        save_graph(client, pid, pair_graph())
        save_spec(client, pid, "node-1")
        commit_spec(client, pid, "node-1")
        sha = commit_for(source, "src/hello.py", "node-1")
        finish_process(client, pid, "node-1")
        record_run(client, pid, "node-1", sha, status="red")
        red = report(client, pid)
        # Opravný běh je nový záznam, ne přepis staršího; rozhoduje ten novější.
        record_run(client, pid, "node-1", sha)
        green = report(client, pid)
        (source / "tools").mkdir()
        (source / "tools" / "build.py").write_text("print('build')\n", encoding="utf-8")
        run(source, "add", "-A")
        run(source, "commit", "-q", "-m", "cizi commit")
        record_run(client, pid, "node-1", run(source, "rev-parse", "HEAD"))
        after = report(client, pid)
    assert check_of(verdict_of(red, "node-1"), "checks")["passed"] is False
    assert verdict_of(green, "node-1")["canMerge"] is True
    # Zelený běh u commitu, který se uzlu nedotkl, není důkaz o uzlu.
    assert check_of(verdict_of(after, "node-1"), "checks")["passed"] is False
    assert verdict_of(after, "node-1")["canMerge"] is False
    assert "checks-unknown" in {signal["type"] for signal in after["signals"]}

def test_c8_five_reports_at_once_all_answer_the_same(tmp_path):
    """Pět souběžných čtení reportu; hlídá závod nad sdíleným spojením sqlite3.

    Dokud report četl `service.db`, zadání, běhy kontrol a osiřelá zadání mimo
    `CanvasService.lock`, vracel na zatíženém stroji 503 (`sqlite3.Error`) i 500
    (`IndexError` v `_orphan_specs`, kam z rozběhnutého dotazu dorazil prázdný řádek).
    Dnes je každé čtení pod zámkem (`sync_report.py:45`, `:53`, `:57`, `:155`).
    """
    # Desítky karet: každá je čtení zadání navíc, takže se dotazy potkají nad týmž spojením.
    paths = [f"src/mod_{index:03d}.py" for index in range(60)]
    source = source_repo(tmp_path, paths)
    nodes = [sector("sector-1", "src"),
             *[node(f"n{index:03d}", "sector-1", path) for index, path in enumerate(paths)]]
    with client_for(tmp_path) as client:
        pid = attach(client, source)
        save_graph(client, pid, nodes)
        answers = []
        for _ in range(3):  # tři nárazy: souběh se nesmí povést jen někdy
            with ThreadPoolExecutor(max_workers=5) as pool:
                answers += [future.result()
                            for future in [pool.submit(ask, client, pid) for _ in range(5)]]
    assert [answer.status_code for answer in answers] == [200] * 15, [
        answer.text[:200] for answer in answers]
    # Report jen čte, takže pět souběžných dotazů musí vidět tentýž svět.
    assert {len(answer.json()["verdicts"]) for answer in answers} == {61}
