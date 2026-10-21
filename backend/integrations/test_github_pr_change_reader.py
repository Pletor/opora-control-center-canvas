"""PR change reading is GET-only, bound to the exact head and fails closed."""
from backend.integrations.github_pr_change_reader import GitHubPullRequestChangeReader
from backend.integrations.github_review_transport import GitHubReadError

HEAD, BASE = "a" * 40, "b" * 40


def pull(head=HEAD):
    return {"head": {"sha": head}, "base": {"sha": BASE}}


def reader(responses):
    paths = []

    def transport(path, *, timeout):
        paths.append(path)
        value = responses[path]
        if isinstance(value, Exception):
            raise value
        return value, {}
    return GitHubPullRequestChangeReader(transport), paths


def test_change_lists_files_including_renames_for_the_exact_head():
    files = [{"filename": "src/a.py", "additions": 3, "deletions": 1},
             {"filename": "src/new.py", "previous_filename": "auth/old.py", "additions": 0, "deletions": 0}]
    subject, paths = reader({"/repos/owner/repo/pulls/7": pull(),
                             "/repos/owner/repo/pulls/7/files?per_page=100&page=1": files})
    change = subject.change("owner/repo", 7, HEAD)
    assert change == {"complete": True, "baseSha": BASE, "files": [
        {"path": "src/a.py", "additions": 3, "deletions": 1}, {"path": "src/new.py", "additions": 0, "deletions": 0},
        {"path": "auth/old.py", "additions": 0, "deletions": 0}]}
    assert paths == ["/repos/owner/repo/pulls/7", "/repos/owner/repo/pulls/7/files?per_page=100&page=1",
                     "/repos/owner/repo/pulls/7"]


def test_moved_head_errors_and_too_many_files_are_incomplete():
    subject, _ = reader({"/repos/owner/repo/pulls/7": pull("c" * 40)})
    assert subject.change("owner/repo", 7, HEAD)["error"] == "head-moved"
    subject, _ = reader({"/repos/owner/repo/pulls/7": GitHubReadError()})
    assert subject.change("owner/repo", 7, HEAD) == {"complete": False, "baseSha": None, "files": [],
                                                     "error": "github-unavailable"}
    page = [{"filename": f"f{index}", "additions": 1, "deletions": 0} for index in range(100)]
    subject, _ = reader({"/repos/owner/repo/pulls/7": pull(),
                         **{f"/repos/owner/repo/pulls/7/files?per_page=100&page={n}": page for n in (1, 2, 3)}})
    assert subject.change("owner/repo", 7, HEAD)["complete"] is False
    assert subject.change("../x", 7, HEAD)["error"] == "invalid-request"
