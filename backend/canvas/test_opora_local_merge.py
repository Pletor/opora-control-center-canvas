"""Lokální sloučení (docs/lokalni-slouceni.md): režim `local` se odvodí, commit ověří git, brána čte kontroly."""
import pytest

from backend.canvas import opora_folder_repository as folder_repository
from backend.canvas.opora_card_done import card_done_state, facts, local_checks_passed, local_mode
from backend.canvas.opora_local_merge import CommitOffBranch, InvalidCommit, LocalMerge, verify_commit
from backend.canvas.test_opora_folder_repository import BIND, checkout, folder_project, git
from backend.canvas.test_opora_review_fixtures import HUMAN

CARD = {"steps": {"total": 1, "done": 1}, "acceptanceEvidence": True}
LINK = {"cardId": "a", "state": "merged", "executionId": "1", "planWrittenBack": True, "mergeSha": "a" * 40}


def test_local_gate_is_merge_plus_checks_on_the_merged_commit():
    assert card_done_state(facts(CARD, LINK, None, local_checks=True)) == {
        "done": False, "missing": ["human_close"], "gate": "local"}
    assert card_done_state(facts(CARD, LINK, None, local_checks=False))["missing"] == ["gate_ready", "human_close"]
    assert card_done_state(facts(CARD, None, None, local_checks=True))["missing"] == [
        "gate_ready", "merged", "plan_written_back", "human_close"]
    # Karta bez kontrol: brána = sloučení; s deklarovanými kontrolami je potřeba zelený běh na tomto commitu.
    assert local_checks_passed({}, None, LINK)
    assert not local_checks_passed({"checks": [{"id": "t", "command": "pytest"}]}, None, LINK)
    assert local_checks_passed({}, {"status": "green", "sha": "a" * 7}, LINK)
    assert not local_checks_passed({}, {"status": "red", "sha": "a" * 40}, LINK)
    assert not local_checks_passed({}, {"status": "green", "sha": "b" * 40}, LINK)


def test_mode_is_derived_from_the_github_binding(tmp_path):
    service, scope = folder_project(tmp_path)
    try:
        assert local_mode(service, "draft") and local_mode(service, scope["project"])
        folder_repository.bind(service, {"project": scope["project"], **BIND}, HUMAN)
        assert not local_mode(service, scope["project"])
        with pytest.raises(ValueError, match="GitHub"):
            LocalMerge(service).merge("x", {**scope, "commit": "a" * 40}, "human")
    finally:
        service.close()


def test_commit_must_exist_and_be_on_the_branch(tmp_path):
    repo = checkout(tmp_path, origin=None)
    full, branch = verify_commit(repo, git_head(repo)[:12])
    assert full == git_head(repo) and branch == "main"
    with pytest.raises(InvalidCommit):
        verify_commit(repo, "0" * 40)
    git(repo, "checkout", "-q", "dev")
    (repo / "x.txt").write_text("x", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "dev")
    aside = git_head(repo)
    git(repo, "checkout", "-q", "main")
    with pytest.raises(CommitOffBranch):
        verify_commit(repo, aside)


def git_head(repo):
    import subprocess
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()
