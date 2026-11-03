"""Git úložiště Brainu: zápis jen při změně, čtení verze, poslední verze pluginu, marketplace a zip pinu."""
import json
import zipfile

import pytest

from backend.brain.store import Store
from backend.integrations.gitio import git

SKILL = "---\nname: a\ndescription: x\n---\nTělo\n"


def test_write_commits_once_and_reads_each_version(tmp_path):
    store = Store(tmp_path)
    assert store.version("p") is None
    first = store.write("p", {".claude-plugin/plugin.json": '{"name": "p"}\n', "skills/a/SKILL.md": SKILL}, "první")
    assert len(first) == 40 and store.version("p") == first
    assert store.write("p", {"skills/a/SKILL.md": SKILL}, "beze změny") == first  # stejný obsah = žádný commit
    second = store.write("p", {"skills/a/SKILL.md": SKILL + "Víc\n"}, "druhá")
    assert second != first and store.version("p") == second
    assert store.read("p", "skills/a/SKILL.md", first) == SKILL
    assert store.read("p", "skills/a/SKILL.md", second) == SKILL + "Víc\n"
    assert git(tmp_path / "brain", "log", "-1", "--format=%an") == "OPORA Brain"
    other = store.write("q", {"skills/b/SKILL.md": SKILL}, "jiný plugin")
    assert store.version("p") == second and store.version("q") == other  # verze = poslední commit pluginu
    market = json.loads((tmp_path / "brain" / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert market["name"] == "opora-brain"
    assert market["plugins"] == [{"name": "p", "source": "./plugins/p"}, {"name": "q", "source": "./plugins/q"}]


def test_export_zips_the_plugin_root_once(tmp_path):
    store = Store(tmp_path)
    first = store.write("p", {".claude-plugin/plugin.json": '{"name": "p"}\n', "skills/a/SKILL.md": SKILL}, "první")
    store.write("p", {"skills/a/SKILL.md": "jiné\n"}, "druhá")
    path = store.export("p", first)
    assert path == tmp_path / "brain-pins" / f"p@{first[:12]}.zip"
    with zipfile.ZipFile(path) as archive:
        assert {".claude-plugin/plugin.json", "skills/a/SKILL.md"} <= set(archive.namelist())
        assert archive.read("skills/a/SKILL.md").decode("utf-8") == SKILL  # zip nese verzi pinu, ne poslední
    stamp = path.stat().st_mtime_ns
    assert store.export("p", first) == path and path.stat().st_mtime_ns == stamp


def test_rejects_paths_outside_the_plugin(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(ValueError):
        store.write("p", {"../mimo.md": "x"}, "ne")
    with pytest.raises(ValueError):
        store.write("../p", {"a.md": "x"}, "ne")
    with pytest.raises(ValueError):
        store.read("p", "a.md", "HEAD; rm")
