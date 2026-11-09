"""Data dílny (§3b): strom zdroje bez node_modules, .git a buildu se stropem; neznámý druh a projekt."""
import pytest

from backend.brain_opora.determinism import brain_files, workshop
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService


def test_tree_skips_dependencies_vcs_and_build_output_and_is_capped(tmp_path):
    for path in ("src/a.ts", "src/b/c.ts", "node_modules/x/i.js", ".git/HEAD", "dist/out.js", "build/x.js",
                 "README.md"):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("x" * 3, encoding="utf-8")
    items = workshop.tree(tmp_path)
    assert [item["path"] for item in items] == ["README.md", "src/a.ts", "src/b/c.ts"]
    assert items[0]["size"] == 3 and isinstance(items[0]["mtime"], int)
    assert len(workshop.tree(tmp_path, cap=2)) == 2


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def test_context_reads_all_journal_entries_and_refuses_unknown_names(service):
    brain = brain_files.brain_dir(service, "draft")
    brain.mkdir(parents=True)
    (brain / brain_files.JOURNAL).write_text("".join(f'{{"at": "t{i}"}}\n' for i in range(12)), encoding="utf-8")
    assert len(workshop.context(service, "draft", "draft", "journal")) == 12
    assert workshop.context(service, "draft", "draft", "work") == []
    for project, name in (("draft", "secrets"), ("nikde", "work")):
        with pytest.raises(GateError):
            workshop.context(service, project, "draft", name)


STEP = {"id": "s1", "order": 1, "title": "Krok", "acceptance": ["hotovo"], "dependsOn": []}


def _plan(service):
    view = service.view("draft", "draft")
    graph = {"nodes": [
        {"id": "s1", "parentId": None, "kind": "sector", "name": "MVP", "purpose": "", "x": 0, "y": 0},
        {"id": "a", "parentId": "s1", "kind": "node", "name": "[task] A", "purpose": "p" * 3000, "x": 0, "y": 0},
        {"id": "a1", "parentId": "a", "kind": "node", "name": "[task] A1", "purpose": "", "x": 0, "y": 0},
        {"id": "b", "parentId": "s1", "kind": "node", "name": "[task] B", "purpose": "", "x": 0, "y": 0}],
        "edges": [{"id": "e1", "source": "a", "target": "b"}]}
    service.save_graph("draft", "draft", graph, view["digest"])
    steps = [STEP, {**STEP, "id": "s2", "order": 2, "title": "t" * 200, "acceptance": ["x" * 1000]}]
    service.specs.save(("draft", "draft", "a"), 0, {"goal": "Cíl A", "non_goals": "n" * 900, "acceptance": "a" * 900,
                                                    "steps": steps})


def test_plan_of_is_compact_by_default_so_the_whole_plan_fits(service):
    _plan(service)
    items = workshop.context(service, "draft", "draft", "plan-of", "draft")
    assert [item["id"] for item in items] == ["s1", "a", "a1", "b"]  # celý plán, žádná značka zkrácení
    a = next(item for item in items if item["id"] == "a")
    assert a["sector"] == "s1" and a["parent"] == "s1" and a["next"] == ["b"] and a["architecture"] is False
    assert a["path"] == "MVP" and items[2]["path"] == "MVP › [task] A"
    assert a["goal"] == "Cíl A" and len(a["acceptance"]) == len(a["purpose"]) == workshop.PLAN_OF_SHORT + 1
    assert a["steps"] == ["Krok", "t" * 200] and "spec" not in a and "non_goals" not in a


def test_plan_of_node_gives_full_detail_of_one_subtree(service):
    _plan(service)
    items = workshop.context(service, "draft", "draft", "plan-of", "draft", None, "a")
    assert [item["id"] for item in items] == ["a", "a1"]
    a = items[0]
    assert a["spec"]["steps"][0] == STEP and len(a["spec"]["non_goals"]) == 900
    assert len(a["purpose"]) == workshop.PLAN_OF_TEXT + 1
    assert len(a["spec"]["steps"][1]["acceptance"][0]) == 1000  # kritéria kroku celá
    with pytest.raises(GateError) as missing:
        workshop.plan_of(service, "draft", None, "nikde")
    assert missing.value.status == 404


def test_plan_of_over_the_cap_names_every_cut_node(service, monkeypatch):
    _plan(service)
    monkeypatch.setattr(workshop, "PLAN_OF_BYTES", 900)
    cut = workshop.plan_of(service, "draft")
    marker = cut[-1]
    assert marker["truncated"] is True and marker["total"] == 4 and marker["shown"] == len(cut) - 1
    assert [item["id"] for item in cut[:-1]] + [node["id"] for node in marker["cut"]] == ["s1", "a", "a1", "b"]
    assert marker["cut"] and "--node" in marker["hint"]
    with pytest.raises(GateError):
        workshop.context(service, "draft", "draft", "plan-of")  # bez projektu


def test_node_detail_preserves_observed_and_unknown_files_without_expanding_summary(service):
    _plan(service)
    current = service.specs.read(("draft", "draft", "a"))
    steps = [{**STEP, "kind": "research", "files": ["src/cache.py"]},
             {**STEP, "id": "s2", "order": 2, "kind": "design", "files": []}]
    service.specs.save(("draft", "draft", "a"), current["revision"], {**current["fields"], "steps": steps})
    detail = workshop.plan_of(service, "draft", "draft", "a")[0]
    assert detail["spec"]["steps"] == steps
    summary = next(item for item in workshop.plan_of(service, "draft") if item["id"] == "a")
    assert summary["steps"] == ["Krok", "Krok"] and "spec" not in summary
