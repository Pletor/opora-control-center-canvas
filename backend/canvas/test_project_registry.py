import pytest

from backend.canvas.project_registry import ProjectRegistry, canonical_source


def test_register_creates_folder_and_lists_by_name(tmp_path):
    registry = ProjectRegistry(tmp_path / "data")
    first = registry.register("ample", "git", "https://github.com/Pletor/ample", branch="main")
    second = registry.register("Opora", "local", str(tmp_path / "opora"))
    empty = registry.register("Prázdný", "empty")
    assert registry.folder(first["id"]).exists()
    names = [item["name"] for item in registry.list()]
    assert names == ["ample", "Opora", "Prázdný"]
    assert registry.get(second["id"])["folder"] == str(registry.folder(second["id"]).path)
    assert empty["source"]["kind"] == "empty"
    registry.close()


def test_duplicates_are_refused_case_and_suffix_insensitive(tmp_path):
    registry = ProjectRegistry(tmp_path)
    registry.register("ample", "git", "https://github.com/Pletor/ample")
    with pytest.raises(ValueError, match="Duplicity"):
        registry.register("ample2", "git", "https://github.com/pletor/AMPLE.git/")
    registry.register("Local", "local", str(tmp_path / "src"))
    with pytest.raises(ValueError, match="Duplicity"):
        registry.register("Local again", "local", str(tmp_path / "SRC"))
    assert len(registry.list()) == 2
    assert registry.register("E1", "empty")["id"] != registry.register("E2", "empty")["id"]


def test_rename_archive_and_reopen(tmp_path):
    registry = ProjectRegistry(tmp_path)
    project = registry.register("Old", "empty", project_id="fixed-id")
    assert registry.rename("fixed-id", "New")["name"] == "New"
    registry.archive("fixed-id", "2026-09-14T10:00:00Z")
    assert registry.is_archived("fixed-id") and registry.list() == [] and len(registry.list(include_archived=True)) == 1
    registry.close()
    reopened = ProjectRegistry(tmp_path)
    assert reopened.get(project["id"])["name"] == "New"
    with pytest.raises(ValueError, match="neexistuje"):
        reopened.get("missing-id")


def test_canonical_source():
    assert canonical_source("git", "https://github.com/X/Y.git/") == "https://github.com/x/y"
    assert canonical_source("empty", "anything") == ""
    with pytest.raises(ValueError):
        canonical_source("svn", "x")
