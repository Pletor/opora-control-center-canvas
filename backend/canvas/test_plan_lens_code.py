"""Vazby kódu z Graphify a ověření hotového specu připnutým PR Lens CLI."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.canvas.plan_lens import build
from backend.canvas.plan_lens_code import code_edges, file_links, owner_of, owners
from backend.canvas.test_plan_lens import world

WIN = r"C:\repo"  # absolutní cesta Graphify uvnitř kořene se zkrátí na relativní
GRAPH = {"nodes": [{"id": "a", "source_file": "src/a.py"}, {"id": "a2", "source_file": "src/a.py"},
                   {"id": "b", "source_file": WIN + r"\src\b.py"}, {"id": "c", "source_file": "lib/c.ts"},
                   {"id": "x"}],
         "links": [{"source": "a", "target": "b", "relation": "imports_from"},
                   {"source": "a", "target": "a2", "relation": "calls"},
                   {"source": "b", "target": "c", "relation": "calls"},
                   {"source": "c", "target": "a", "relation": "contains"},
                   {"source": "c", "target": "x", "relation": "imports"}]}


def test_file_links_keep_code_relations_between_files():
    assert file_links(GRAPH, WIN) == [("src/a.py", "src/b.py"), ("src/b.py", "lib/c.ts")]
    assert file_links({"nodes": "?"}) == [] and file_links(None) == []


def test_owner_is_the_most_specific_path():
    by_path = owners({"dir": "src", "file": "src/b.py", "dup": "src", "lib": "lib"})
    assert by_path == {"lib": "lib", "src": "dir", "src/b.py": "file"}
    assert owner_of("src/b.py", by_path) == "file" and owner_of("src/a.py", by_path) == "dir"
    assert owner_of("srcx/a.py", by_path) is None


def test_code_edges_between_cards():
    links = file_links(GRAPH, WIN)
    assert code_edges({"dir": "src", "file": "src/b.py", "lib": "lib/c.ts"}, links) == [("dir", "file"), ("file", "lib")]


CLI = Path(__file__).resolve().parents[3] / "tools" / "pr-lens" / "node_modules" / ".bin" / "pr-lens.cmd"


@pytest.mark.skipif(not CLI.exists() or shutil.which("node") is None, reason="připnuté PR Lens CLI chybí")
def test_generated_specs_validate_with_pinned_cli(tmp_path):
    graph, state, reality = world()
    files = []
    for area in (None, "a1", "a2"):
        target = tmp_path / f"plan-{area or 'project'}.json"
        target.write_text(json.dumps(build(graph, state, reality, area, "p1", "draft")["spec"]), encoding="utf-8")
        files.append(str(target))
    done = subprocess.run([str(CLI), "validate", *files], capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
