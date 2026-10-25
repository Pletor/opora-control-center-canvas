"""A local-folder project bound to the GitHub repository of its origin closes the PR -> merge loop.

Real SQLite, a real git checkout on disk with a GitHub `origin`, offline GitHub reader."""
import subprocess

import pytest

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas import opora_folder_repository as folder_repository
from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_execution_pr_discovery import discover
from backend.canvas.opora_execution_pr_manager import ExecutionPullRequestManager
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_reconciliation import OporaReconciliation
from backend.canvas.opora_review_scope import configuration
from backend.canvas.test_canvas_service import managed_fixture
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_execution_pull_requests import (
    MERGE_SHA,
    SHA,
    Reader,
    claim,
    close,
    observe,
    pr,
)
from backend.canvas.test_opora_review_fixtures import HUMAN

BIND = {"repository": "Owner/Repo", "branch": "main"}


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def checkout(tmp_path, origin="https://github.com/Owner/Repo.git"):
    source = tmp_path / "ample"
    source.mkdir()
    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "Fixture")
    git(source, "config", "user.email", "fixture@example.invalid")
    (source / "README.md").write_text("base", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-m", "initial")
    git(source, "branch", "dev")
    if origin:
        git(source, "remote", "add", "origin", origin)
    return source


def folder_project(tmp_path, **options):
    service = CanvasService(tmp_path / "data")
    pid = service.project_hub.local_project({"name": "Ample", "path": str(checkout(tmp_path, **options)),
                                             "confirmed": True})["id"]
    scope = {"project": pid, "workspace": "draft"}
    service.save_graph(pid, "draft", {"nodes": [node("card")], "edges": []}, service.view(pid, "draft")["digest"])
    changesets = OporaChangesets(service)
    current = changesets.context(pid, "draft")
    changesets.baseline({**scope, "subject": "Initial specs", "expectedAcceptedHead": None,
                         "expectedGraphDigest": current["graphDigest"],
                         "expectedSpecificationsVersion": current["specificationsVersion"]}, HUMAN)
    return service, scope


@pytest.fixture(name="folder")
def folder_fixture(tmp_path):
    service, scope = folder_project(tmp_path)
    yield service, scope
    service.close()


@pytest.fixture(autouse=True)
def real_seam():
    pulls.register(None)
    yield
    pulls.register(None)


def stage(document, name):
    return next(item for item in document["stages"] if item["id"] == name)


def test_unbound_folder_project_has_no_repository_but_offers_its_origin(folder):
    service, scope = folder
    with pytest.raises(ValueError, match="nemá připojený Git repozitář"):
        configuration(service, scope["project"])
    shown = folder_repository.status(service, scope["project"], "human")
    assert shown["bindable"] and shown["canConfigure"] and shown["binding"] is None
    assert shown["detectedRepository"] == "owner/repo"
    assert not folder_repository.status(service, scope["project"], "agent")["canConfigure"]
    listing = OporaReconciliation(service).list(**scope, actor="human")
    assert listing["canConfigure"] is False and "nemá připojený Git repozitář" in listing["unavailableReason"]


def test_binding_is_validated_against_the_folder_on_disk(folder):
    service, scope = folder
    pid = scope["project"]
    for payload, message in (({**BIND, "repository": "other/repo"}, "ne na other/repo"),
                             ({**BIND, "branch": "release"}, "neexistuje"),
                             ({**BIND, "branch": "-x"}, "Neplatný název větve"),
                             ({**BIND, "repository": "https://evil.test/owner/repo"}, "owner/název"),
                             ({**BIND, "extra": 1}, "jen project")):
        with pytest.raises(ValueError, match=message):
            folder_repository.bind(service, {"project": pid, **payload}, HUMAN)
    assert folder_repository.read_binding(service, pid) is None
    bound = folder_repository.bind(service, {"project": pid, **BIND}, HUMAN)
    assert bound["binding"]["repository"] == "owner/repo" and bound["requeuedLinks"] == 0
    assert configuration(service, pid) == {"repository": "owner/repo", "branch": "main", "repoPath": "",
                                           "sourcePath": service.project_hub.source_info(pid)["sourcePath"]}
    assert folder_repository.bind(service, {"project": pid, **BIND}, HUMAN)["binding"] == bound["binding"]
    with pytest.raises(ValueError, match="Nejprve ho odpojte"):
        folder_repository.bind(service, {"project": pid, **BIND, "branch": "dev"}, HUMAN)
    assert folder_repository.unbind(service, {"project": pid}, HUMAN)["binding"] is None
    with pytest.raises(ValueError):
        configuration(service, pid)


def test_folder_without_github_origin_cannot_be_bound(tmp_path):
    service, scope = folder_project(tmp_path, origin="https://gitlab.example/owner/repo.git")
    try:
        shown = folder_repository.status(service, scope["project"], "human")
        assert not shown["canConfigure"] and "GitHub remote origin" in shown["unavailableReason"]
        with pytest.raises(ValueError, match="GitHub remote origin"):
            folder_repository.bind(service, {"project": scope["project"], **BIND}, HUMAN)
    finally:
        service.close()


def test_git_cloned_project_keeps_its_own_configuration(tmp_path):
    service, project = managed_fixture(tmp_path)
    try:
        with pytest.raises(ValueError, match="lokální složky"):
            folder_repository.bind(service, {"project": project["id"], **BIND}, HUMAN)
    finally:
        service.close()


def test_pr_linked_before_binding_enrolls_merges_and_offers_close(folder, monkeypatch):
    """The ample case: PRs were linked while the project had no repository; binding closes the loop."""
    monkeypatch.setenv("OPORA_EXECUTION_PR_DISCOVERY_SECONDS", "0")
    service, scope = folder
    executions = ExecutionResults(service)
    record = claim(executions, scope)
    executions.submit(record["executionId"], {**scope, "token": record["token"], "epoch": record["epoch"],
                                              "requestId": "result", "result": {"summary": "Done"}})
    reader = Reader()
    links = ExecutionPullRequestLinks(service, reader)
    office = {"projectId": scope["project"], "workspaceId": "draft", "token": record["token"],
              "epoch": record["epoch"], "requestId": "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
              "repository": "Pletor-free/../x", "number": 7, "headRef": "feature", "headSha": SHA}
    with pytest.raises(ValueError):
        links.link(record["executionId"], office, "agent")
    linked = links.link(record["executionId"], {**office, "repository": "owner/repo"}, "agent")
    assert linked["enrollment"] == "unavailable" and linked["enrollmentError"] == "github-not-configured"
    manager = ExecutionPullRequestManager(service, links)
    manager.run_once()
    assert reader.calls == []  # unbound: never touches the network

    assert folder_repository.bind(service, {"project": scope["project"], **BIND}, HUMAN)["requeuedLinks"] == 1
    manager.run_once()
    enrolled = links.read(**scope, execution_id=record["executionId"])
    assert enrolled["enrollment"] == "enrolled" and enrolled["bindingId"]
    assert reader.calls == [("pull", "owner/repo", 7)]
    listing = OporaReconciliation(service).list(**scope, actor="human")
    assert listing["canConfigure"] is True and [item["binding"]["id"] for item in listing["items"]] == [enrolled["bindingId"]]

    observe(service, scope, enrolled["bindingId"], "merged")
    assert close(service, links, scope) == ["execution.merged"]
    merged = AgentState(service).read(**scope)
    assert stage(merged, "pull_request") == {"id": "pull_request", "count": 1, "health": "ok", "reason": "results_linked"}
    assert stage(merged, "evidence")["health"] == "ok"
    assert stage(merged, "merge") == {"id": "merge", "count": 1, "health": "ok", "reason": "merged"}
    [action] = [item for item in merged["actions"] if item["verb"] == "close_card"]
    assert action["targetId"] == "card" and action["preconditions"]["mergeSha"] == MERGE_SHA
    assert "merged" not in action["preconditions"]["missing"]
    manager.close()


def test_binding_again_requeues_links_that_failed_without_github_access(folder):
    """Ample: links failed as `github-unavailable` (private repo, no token); binding again retries them."""
    service, scope = folder
    executions = ExecutionResults(service)
    record = claim(executions, scope)
    executions.submit(record["executionId"], {**scope, "token": record["token"], "epoch": record["epoch"],
                                              "requestId": "result", "result": {"summary": "Done"}})
    links = ExecutionPullRequestLinks(service, Reader())
    links.link(record["executionId"], {"projectId": scope["project"], "workspaceId": "draft", "token": record["token"],
                                       "epoch": record["epoch"], "requestId": "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
                                       "repository": "owner/repo", "number": 7, "headRef": "feature", "headSha": SHA},
               "agent")
    assert folder_repository.bind(service, {"project": scope["project"], **BIND}, HUMAN)["requeuedLinks"] == 1
    db = service.db_for(scope["project"])
    with db:
        db.execute("UPDATE opora_execution_pull_requests SET enrollment='failed',enrollment_error='github-unavailable'")
    assert folder_repository.bind(service, {"project": scope["project"], **BIND}, HUMAN)["requeuedLinks"] == 1
    assert links.read(**scope, execution_id=record["executionId"])["enrollment"] == "pending"
    with db:
        db.execute("UPDATE opora_execution_pull_requests SET enrollment='failed',enrollment_error='pr-closed-unmerged'")
    assert folder_repository.bind(service, {"project": scope["project"], **BIND}, HUMAN)["requeuedLinks"] == 0


def test_binding_lets_discovery_link_unlinked_results_by_trailers(folder):
    service, scope = folder
    executions = ExecutionResults(service)
    record = claim(executions, scope)
    reader = Reader([pr(9, body=f"Opora-Execution: {record['executionId']}\nOpora-Revision: {record['acceptedRevision']}")])
    links = ExecutionPullRequestLinks(service, reader)
    assert discover(service, links, scope["project"]) == [] and reader.calls == []
    folder_repository.bind(service, {"project": scope["project"], **BIND}, HUMAN)
    assert discover(service, links, scope["project"]) == [record["executionId"]]
    assert links.read(**scope, execution_id=record["executionId"])["enrollment"] == "enrolled"
