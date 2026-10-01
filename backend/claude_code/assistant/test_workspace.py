import threading
from types import SimpleNamespace

import pytest

from backend.claude_code.assistant.workspace import NO_ROOT, default_workspace, project_locator


def service_for(kind, source_path=None, repo=None):
    hub = SimpleNamespace(settings=lambda project: {"project": {"sourceKind": kind, "sourcePath": source_path}})

    def location(project, workspace):
        if workspace != "main":
            raise ValueError("Pracovní prostor patří jinému projektu.")
        return repo, {}

    return SimpleNamespace(lock=threading.RLock(), project_hub=hub, location=location)


def test_default_workspace_follows_source_kind():
    assert default_workspace("git") == "main"
    assert default_workspace("local") == "draft"
    assert default_workspace("empty") == "draft"


def test_git_project_runs_in_main_worktree(tmp_path):
    workspace, root = project_locator(service_for("git", repo=tmp_path))("p1")
    assert workspace == "main" and root == tmp_path.resolve()


def test_local_project_runs_in_source_folder(tmp_path):
    workspace, root = project_locator(service_for("local", source_path=str(tmp_path)))("p1")
    assert workspace == "draft" and root == tmp_path.resolve()


def test_missing_root_has_czech_error():
    with pytest.raises(ValueError) as missing:
        project_locator(service_for("empty"))("p1")
    assert str(missing.value) == NO_ROOT
