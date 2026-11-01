"""PR change reading is GET-only, bound to the exact head and fails closed."""
from backend.integrations.github_pr_change_reader import (
    GitHubPullRequestChangeReader,
    patch_fingerprint,
)
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
    assert change.pop("fingerprint") is None  # Neither patch nor blob sha: content is not comparable.
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


def test_fingerprint_ignores_hunk_positions_but_not_content():
    item = {"filename": "src/a.py", "status": "modified", "patch": "@@ -1,2 +1,3 @@ def f():\n a\n+b\n c"}
    moved = {**item, "patch": "@@ -40,2 +41,3 @@ def g():\n a\n+b\n c"}
    other = {**item, "patch": "@@ -1,2 +1,3 @@ def f():\n a\n+x\n c"}
    binary = {"filename": "logo.png", "status": "added", "sha": "9" * 40}
    assert patch_fingerprint([item, binary]) == patch_fingerprint([binary, moved])
    assert patch_fingerprint([item]) != patch_fingerprint([other])
    assert patch_fingerprint([item]) != patch_fingerprint([{**item, "previous_filename": "src/old.py"}])
    assert patch_fingerprint([item, {"filename": "big.bin", "status": "added"}]) is None


def test_change_and_compare_carry_the_same_fingerprint():
    files = [{"filename": "src/a.py", "status": "modified", "additions": 1, "deletions": 0,
              "patch": "@@ -1 +1,2 @@\n a\n+b", "sha": "9" * 40}]
    compare = f"/repos/owner/repo/compare/{BASE}...{HEAD}"
    subject, paths = reader({"/repos/owner/repo/pulls/7": pull(),
                             "/repos/owner/repo/pulls/7/files?per_page=100&page=1": files,
                             compare: {"files": [{**files[0], "patch": "@@ -5 +5,2 @@\n a\n+b"}]}})
    fingerprint = subject.change("owner/repo", 7, HEAD)["fingerprint"]
    assert fingerprint == patch_fingerprint(files) and subject.fingerprint("owner/repo", BASE, HEAD) == fingerprint
    assert paths[-1] == compare
    failing, _ = reader({compare: GitHubReadError()})
    assert failing.fingerprint("owner/repo", BASE, HEAD) is None
    assert failing.fingerprint("owner/repo", "main", HEAD) is None
    truncated, _ = reader({compare: {"files": files * 300}})
    assert truncated.fingerprint("owner/repo", BASE, HEAD) is None
