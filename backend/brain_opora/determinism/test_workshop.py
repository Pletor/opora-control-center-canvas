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
    assert workshop.context(service, "draft", "draft", "tasks") == []
    for project, name in (("draft", "secrets"), ("nikde", "tasks")):
        with pytest.raises(GateError):
            workshop.context(service, project, "draft", name)


STEP = {"id": "s1", "order": 1, "title": "Krok", "acceptance": ["hotovo"], "dependsOn": []}


def test_plan_of_lists_nodes_with_spec_sector_and_next_and_is_capped(service, monkeypatch):
    view = service.view("draft", "draft")
    graph = {"nodes": [
        {"id": "s1", "parentId": None, "kind": "sector", "name": "MVP", "purpose": "", "x": 0, "y": 0},
        {"id": "a", "parentId": "s1", "kind": "node", "name": "[task] A", "purpose": "p" * 3000, "x": 0, "y": 0},
        {"id": "b", "parentId": "s1", "kind": "node", "name": "[task] B", "purpose": "", "x": 0, "y": 0}],
        "edges": [{"id": "e1", "source": "a", "target": "b"}]}
    service.save_graph("draft", "draft", graph, view["digest"])
    service.specs.save(("draft", "draft", "a"), 0, {"goal": "Cíl A", "non_goals": "", "acceptance": "test",
                                                    "steps": [STEP]})
    items = workshop.context(service, "draft", "draft", "plan-of", "draft")
    a = next(item for item in items if item["id"] == "a")
    assert a["sector"] == "s1" and a["parent"] == "s1" and a["next"] == ["b"] and a["architecture"] is False
    assert a["spec"]["goal"] == "Cíl A" and a["spec"]["steps"] == [STEP]
    assert len(a["purpose"]) == workshop.PLAN_OF_TEXT + 1
    monkeypatch.setattr(workshop, "PLAN_OF_BYTES", 400)
    cut = workshop.plan_of(service, "draft")
    assert cut[-1] == {"truncated": True, "total": 3, "shown": len(cut) - 1}
    with pytest.raises(GateError):
        workshop.context(service, "draft", "draft", "plan-of")  # bez projektu
