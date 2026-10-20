"""Repository authority accepts only normalized configured GitHub remotes."""
import pytest

from backend.canvas.opora_review_scope import configuration, github_repository
from backend.canvas.test_opora_review_fixtures import (
    evidence_project as evidence_fixture,  # noqa: F401
)


@pytest.mark.parametrize("value", ["https://github.com/Owner/Repo", "https://github.com/Owner/Repo.git", "git@github.com:Owner/Repo.git"])
def test_github_remotes_normalize(value):
    assert github_repository(value) == "owner/repo"


@pytest.mark.parametrize("value", [None, "", "https://evil.test/owner/repo", "https://github.com.evil.test/owner/repo", "https://user:secret@github.com/owner/repo", "https://github.com/owner/repo?token=secret", "https://github.com/owner/../repo", "file:///tmp/repo", "https://github.com/owner/repo/issues/1"])
def test_untrusted_remote_is_rejected(value):
    with pytest.raises(ValueError):
        github_repository(value)


def test_registry_and_folder_remote_must_match(evidence_project):
    service, payload = evidence_project
    pid = payload["project"]
    folder = service.folder(pid)
    identity = folder.read()
    identity["source"]["value"] = "https://github.com/other/repo"
    folder._write(identity)
    with pytest.raises(ValueError, match="konzistentní"):
        configuration(service, pid)
