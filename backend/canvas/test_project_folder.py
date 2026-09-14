import json

import pytest

from backend.canvas.project_folder import SUBFOLDERS, ProjectFolder


def test_create_makes_one_folder_with_everything_inside(tmp_path):
    folder = ProjectFolder(tmp_path, "aff4759e37cd469eb946c5ec17e41adf")
    identity = folder.create("ample", "git", "https://github.com/Pletor/ample", branch="main")
    assert folder.path == (tmp_path / "projects" / "aff4759e37cd469eb946c5ec17e41adf").resolve()
    for name in SUBFOLDERS:
        assert (folder.path / name).is_dir()
    assert json.loads(folder.identity_file.read_text(encoding="utf-8")) == identity
    assert identity["name"] == "ample" and identity["source"] == {"kind": "git", "value": "https://github.com/Pletor/ample", "branch": "main"}
    assert folder.summary() == {"id": folder.id, "name": "ample", "sourceKind": "git", "path": str(folder.path)}
    assert folder.database == folder.path / "project.sqlite"
    assert folder.node("n1") == folder.path / "nodes" / "n1"
    with pytest.raises(ValueError, match="už existuje"):
        folder.create("ample", "git")


def test_update_only_name_and_settings(tmp_path):
    folder = ProjectFolder(tmp_path, "p1")
    folder.create("Projekt", "local", str(tmp_path / "src"))
    updated = folder.update(name="Jiný", settings={"goal": "cíl"})
    assert updated["name"] == "Jiný" and updated["settings"]["goal"] == "cíl" and updated["settings"]["platform"] == "web"
    with pytest.raises(ValueError):
        folder.update(source={"kind": "git"})
    with pytest.raises(ValueError):
        folder.update(name="")


def test_ids_are_validated(tmp_path):
    for bad in ("", "../x", ".hidden", "a/b", "x" * 65):
        with pytest.raises(ValueError):
            ProjectFolder(tmp_path, bad)
    folder = ProjectFolder(tmp_path, "p1")
    with pytest.raises(ValueError):
        folder.node("../etc")
    with pytest.raises(ValueError, match="neexistuje"):
        folder.read()
    with pytest.raises(ValueError):
        folder.create("x", "svn")
