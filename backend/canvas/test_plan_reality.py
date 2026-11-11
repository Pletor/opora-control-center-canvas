"""Folie z kódu F1 nad dočasným repozitářem: shoda / chybí / navíc, symboly a routy, přejmenování, mazání, cizí karta."""
from backend.agi_pletor.linie.test_branches import run
from backend.canvas import plan_reality as pr

ROUTE = 'from fastapi import APIRouter\n\nrouter = APIRouter()\n\n\n@router.get("/x")\ndef read_x():\n    return 1\n'


def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    run(path, "init", "-q", "-b", "main")
    (path / "README.md").write_text("x\n", encoding="utf-8")
    run(path, "add", ".")
    run(path, "commit", "-q", "-m", "start")
    return path


def commit(path, files, trailer="Opora-Node: n1", remove=(), move=()):
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    for old, new in move:
        run(path, "mv", old, new)
    for name in remove:
        run(path, "rm", "-q", name)
    run(path, "add", "-A")
    run(path, "commit", "-q", "-m", f"změna\n\n{trailer}")
    return run(path, "rev-parse", "HEAD")


def expected(*paths):
    return [{"kind": "file", "name": p, "path": p, "line": None, "source": "step:s1"} for p in paths]


def names(items):
    return {(item["kind"], item["name"], item.get("change")) for item in items}


def test_compare_matched_missing_extra_and_outputs():
    files = [{"kind": "file", "name": "app/a.py", "path": "app/a.py"},
             {"kind": "file", "name": "app/c.py", "path": "app/c.py", "from": "old/c.py"},
             {"kind": "file", "name": "doc.md", "path": "doc.md"}]
    symbols = [{"kind": "symbol", "name": "Kosik.seznam_produktu", "path": "app/a.py"}]
    wanted = expected("app/a.py", "old/", "lib/") + [
        {"kind": "output", "name": "Seznam produktů", "path": None, "line": None, "source": "flow.outputs"},
        {"kind": "output", "name": "Cena", "path": None, "line": None, "source": "flow.dataTo"}]
    found = pr.compare(wanted, files, symbols, {"commit": "abc", "at": "t"})
    assert [item["path"] for item in found["matched"][:2]] == ["app/a.py", "app/c.py"]  # přejmenování z očekávané
    assert [item["name"] for item in found["matched"][2:]] == ["Seznam produktů"]
    assert [item["name"] for item in found["missing"]] == ["lib/", "Cena"]
    assert [item["path"] for item in found["extra"]] == ["doc.md"]
    assert pr.state(found) == "bad" and pr.counts(found) == {"matched": 3, "missing": 2, "extra": 1}


def test_without_file_expectations_everything_is_new_not_extra():
    files = [{"kind": "file", "name": "a.py", "path": "a.py"}]
    found = pr.compare([], files, [], {"commit": "abc", "at": "t"})
    assert found["extra"] == [] and found["symbols"] == files and pr.state(found) == "ok"
    assert pr.state(pr.compare([], [], [], None)) is None


def test_commit_function_and_route_then_drift(tmp_path):
    path = repo(tmp_path)
    first = commit(path, {"app/routes.py": ROUTE, "app/logic.py": "def secti(a, b):\n    return a + b\n",
                          "app/test_logic.py": "def test_secti():\n    assert True\n"})
    found = pr.card(path, "n1", [], expected("app/"))
    assert names(found["symbols"]) == {("route", "GET /x", "added"), ("symbol", "secti", "added"),
                                       ("test", "test_secti", "added")}
    assert found["extra"] == [] and found["missing"] == [] and found["evidence"]["commit"] == first
    assert pr.state(found) == "ok"
    commit(path, {"app/logic.py": "def secti(a, b):\n    return b + a\n", "tools/x.py": "def mimo():\n    pass\n"})
    found = pr.card(path, "n1", [], expected("app/"))
    assert [item["path"] for item in found["extra"]] == ["tools/x.py"] and pr.state(found) == "bad"
    logic = next(item for item in found["symbols"] if item["name"] == "secti")
    assert logic["change"] == "added" and logic["line"] == 1  # přidaná kartou zůstává přidaná i po úpravě


def test_rename_delete_and_removed_symbol(tmp_path):
    path = repo(tmp_path)
    commit(path, {"app/a.py": "def stara():\n    pass\n\n\ndef zustane():\n    pass\n", "app/c.py": "x = 1\n"})
    commit(path, {"app/a.py": "def zustane():\n    pass\n"})
    commit(path, {}, move=[("app/a.py", "app/b.py")], remove=["app/c.py"])
    found = pr.card(path, "n1", [], expected("app/"))
    files = {item["path"]: item for item in found["matched"]}
    assert files["app/b.py"]["change"] == "renamed" and files["app/b.py"]["from"] == "app/a.py"
    assert files["app/c.py"]["change"] == "deleted" and "app/a.py" not in files
    assert ("symbol", "stara", "deleted") in names(found["symbols"])
    assert all(item["path"] == "app/b.py" for item in found["symbols"])  # symboly jdou s přejmenováním


def test_foreign_card_is_not_mixed_in(tmp_path):
    path = repo(tmp_path)
    commit(path, {"app/a.py": "def moje():\n    pass\n"})
    commit(path, {"app/cizi.py": "def cizi():\n    pass\n"}, trailer="Opora-Node: n2")
    commit(path, {"app/bez.py": "def bez():\n    pass\n"}, trailer="")  # jen cesta, žádný trailer
    found = pr.card(path, "n1", [], expected("app/"))
    assert {item["name"] for item in found["symbols"]} == {"moje"}
    assert pr.card(path, "n9", [], expected("app/"))["evidence"] is None


def test_linie_task_commits_marks_and_cache(tmp_path):
    path = repo(tmp_path)
    base = run(path, "rev-parse", "HEAD")
    run(path, "checkout", "-q", "-b", "feat/uzel")
    commit(path, {"app/k.py": "def hlavni():\n    # OP-ABC123.1: proč tady\n    return 1\n"},
           trailer="Opora-Mark: OP-ABC123")
    head = commit(path, {"app/bez.py": "def dalsi():\n    pass\n"}, trailer="")  # na větvi úkolu bez značky
    run(path, "checkout", "-q", "main")
    work = {"mark": "OP-ABC123", "baseSha": base, "branch": "feat/uzel", "headSha": head}
    found = pr.card(path, "n5", [work], expected("app/"))
    by_name = {item["name"]: item for item in found["symbols"]}
    assert set(by_name) == {"hlavni", "dalsi"} and by_name["hlavni"]["note"].startswith("# OP-ABC123.1")
    assert found["evidence"]["commit"] == head
    assert pr.card(path, "n5", [work], expected("app/")) is found  # paměť: nic se nezměnilo
    assert pr.card(path, "n5", [work], expected("app/", "lib/")) is not found  # změna očekávání


def test_expectations_from_steps_source_ref_and_flow():
    nodes = [{"id": "n1", "parentId": None, "sourceRef": {"path": "backend/x"}},
             {"id": "n2", "parentId": "n1", "sourceRef": {"path": "backend/x/y.py"}}]
    steps = [{"id": "s1", "files": ["backend/x/y.py", "frontend/z.ts"]}]
    flow = {"nodes": [{"id": "vystup-1", "notes": "Seznam"}, {"id": "data-1", "params": {"title": "Cena"}},
                      {"id": "krok-1", "notes": "Nic"}]}
    found = pr.expectations("n1", nodes, steps, flow)
    assert [(item["kind"], item["name"], item["source"]) for item in found] == [
        ("file", "backend/x/y.py", "step:s1"), ("file", "frontend/z.ts", "step:s1"), ("file", "backend/x", "sourceRef"),
        ("output", "Seznam", "flow.outputs"), ("output", "Cena", "flow.dataTo")]
