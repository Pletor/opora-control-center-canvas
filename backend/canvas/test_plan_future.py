"""Budoucnost karty F4 nad dočasným repozitářem: změny, čisté a konfliktní sloučení, dopady přes vazbu a zrcadlo,
překryv s jiným úkolem, sloučený úkol se nepočítá, paměť bez gitu při stejných hlavách."""
import pytest

from backend.agi_pletor.linie import gitsnap
from backend.agi_pletor.linie.test_branches import run
from backend.canvas import plan_future as pf
from backend.canvas import plan_reality
from backend.integrations import gitio

NODES = [{"id": "a", "name": "Košík"}, {"id": "b", "name": "Platba"}, {"id": "c", "name": "Sklad"}]
EDGES = [{"id": "e1", "source": "b", "target": "a", "relation": "vyžaduje"}]


def write(repo, files, message):
    for name, text in files.items():
        (repo / name).write_text(text, encoding="utf-8")
    run(repo, "add", "-A")
    run(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """main + větve `feat/a` (mění košík a čtvrtý soubor s diakritikou), `feat/x` (košík jako feat/a, sklad v konfliktu s main)."""
    path = tmp_path / "repo s mezerou č"
    path.mkdir()
    run(path, "init", "-q", "-b", "main")
    write(path, {"kosik.py": "a = 1\n", "sklad.py": "s = 1\n"}, "start")
    run(path, "checkout", "-q", "-b", "feat/a")
    write(path, {"kosik.py": "a = 2\n", "účet.py": "u = 1\n"}, "košík")
    run(path, "checkout", "-q", "-b", "feat/x", "main")
    write(path, {"kosik.py": "a = 3\n", "sklad.py": "s = 3\n"}, "jinak")
    run(path, "checkout", "-q", "-b", "feat/b", "main")
    write(path, {"platba.py": "p = 1\n"}, "jiný soubor")
    run(path, "checkout", "-q", "main")
    write(path, {"sklad.py": "s = 2\n"}, "main jde dál")
    monkeypatch.setattr(pf, "PAIRS", {})
    monkeypatch.setattr(pf, "VERDICTS", {})
    monkeypatch.setattr(plan_reality, "CARDS", {})
    return path


def work(mark, branch, **extra):
    return {"mark": mark, "branch": branch, "baseBranch": "main", "headSha": None, "merged": None, **extra}


def test_neighbour_via_edge_counts_only_with_shared_files(repo):
    works = {"a": [work("OP-A", "feat/a")], "b": [work("OP-B", "feat/b")]}  # b je propojená, mění jiný soubor
    found = pf.card(repo, "a", NODES, EDGES, works)
    [item] = found["works"]
    assert item["target"] == "main" and sorted(item["changed"]) == ["kosik.py", "účet.py"]  # diakritika bez escapů
    assert item["conflicts"] == [] and item["overlaps"] == [] and item["impacts"] == []
    assert found["verdict"] == "clean"  # vazba bez společných souborů dopad není
    plan_reality.CARDS[(str(repo), "b")] = ("k", {"matched": [{"path": "kosik.py"}], "extra": [], "symbols": []})
    found = pf.card(repo, "a", NODES, EDGES, works)
    assert found["works"][0]["impacts"] == [{"nodeId": "b", "name": "Platba", "via": "vyžaduje", "paths": ["kosik.py"]}]
    assert found["verdict"] == "warning"


def test_conflicting_branch_is_blocked_with_the_file(repo):
    found = pf.card(repo, "c", NODES, [], {"c": [work("OP-X", "feat/x")]})
    assert found["works"][0]["conflicts"] == ["sklad.py"] and found["verdict"] == "blocked"


def test_impact_through_mirror_and_overlap_with_other_open_work(repo):
    plan_reality.CARDS[(str(repo), "c")] = ("k", {"matched": [{"path": "kosik.py"}], "extra": [], "symbols": []})
    works = {"a": [work("OP-A", "feat/a")], "b": [work("OP-X", "feat/x")]}
    [item] = pf.card(repo, "a", NODES, [], works)["works"]
    assert item["impacts"] == [{"nodeId": "c", "name": "Sklad", "via": "shares_code", "paths": ["kosik.py"]},
                               {"nodeId": "b", "name": "Platba", "via": "shares_code", "paths": ["kosik.py"]}]
    assert item["overlaps"] == [{"nodeId": "b", "mark": "OP-X", "branch": "feat/x", "paths": ["kosik.py"]}]
    merged = {"a": works["a"], "b": [work("OP-X", "feat/x", merged={"sha": "x"})]}
    assert pf.card(repo, "a", NODES, [], merged)["works"][0]["overlaps"] == []  # sloučený úkol se nepočítá
    assert pf.card(repo, "b", NODES, [], merged) is None  # karta bez otevřené práce budoucnost nemá
    blocked = {"a": works["a"], "b": [work("OP-X", "feat/x", blocked={"reason": "slepá"})]}
    assert pf.card(repo, "a", NODES, [], blocked)["works"][0]["overlaps"] == []  # blokovaný úkol se nepočítá
    assert pf.card(repo, "b", NODES, [], blocked) is None


def test_same_heads_do_not_call_git_again_and_memory_follows_the_work(repo, monkeypatch):
    works = {"a": [work("OP-A", "feat/a")]}
    first = pf.card(repo, "a", NODES, EDGES, works)
    calls = []

    def counted(*args, **kwargs):
        calls.append(args)
        return gitio.git(*args, **kwargs)

    monkeypatch.setattr(pf, "git", counted)
    monkeypatch.setattr(gitsnap, "git", counted)
    assert pf.card(repo, "a", NODES, EDGES, works) == first and calls == []
    assert pf.remembered(repo, "a", works["a"]) == first
    assert pf.remembered(repo, "a", [work("OP-A", "feat/a", headSha="f" * 40)]) is None  # nové hlášení = přepočet
    run(repo, "checkout", "-q", "feat/a")
    write(repo, {"kosik.py": "a = 4\n"}, "další")
    pf.card(repo, "a", NODES, EDGES, works)
    assert calls  # nová hlava = git znovu


def test_work_in_its_own_repository_feeds_future_and_mirror(repo, tmp_path):
    """Kořen prostoru je jiný klon bez větví úkolu: budoucnost i zrcadlo čtou git v `work.repository`."""
    space = tmp_path / "prostor"
    space.mkdir()
    run(space, "init", "-q", "-b", "main")
    write(space, {"jiny.py": "x = 1\n"}, "jiný klon")
    base = run(repo, "rev-parse", "main~1")
    run(repo, "checkout", "-q", "feat/a")
    write(repo, {"kosik.py": "a = 5\n"}, "košík\n\nOpora-Mark: OP-T")
    run(repo, "checkout", "-q", "main")
    task = work("OP-T", "feat/a", repository=str(repo), baseSha=base)
    found = pf.card(space, "a", NODES, [], {"a": [task]})
    assert sorted(found["works"][0]["changed"]) == ["kosik.py", "účet.py"]
    mirror = plan_reality.card(space, "a", [task], [], build=True)
    assert mirror["evidence"] is not None and "kosik.py" in {item["path"] for item in mirror["symbols"]}
    missing = work("OP-T", "feat/a", repository=str(tmp_path / "není"), baseSha=base)
    assert pf.card(space, "a", NODES, [], {"a": [missing]}) is None  # nečitelné repo = práce se přeskočí
    assert plan_reality.card(space, "b", [missing], [], build=True)["evidence"] is None
