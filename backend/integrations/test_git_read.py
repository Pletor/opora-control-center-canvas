from backend.integrations.git_read import (
    blob_sha,
    commit_info,
    commits_between,
    head,
    is_ancestor,
    recent,
    rename_of,
)
from backend.integrations.gitio import git

IDENTITY = (
    "-c",
    "user.name=Test",
    "-c",
    "user.email=test@example.com",
    "-c",
    "commit.gpgsign=false",
)


def run(root, *args):
    return git(root, *IDENTITY, *args, timeout=30)


def repo(tmp_path, name="repo"):
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    run(root, "init", "-q", "-b", "main")
    return root


def commit(root, message, files):
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", message)
    return head(root)


def test_head_reads_existing_ref_and_skips_missing(tmp_path):
    root = repo(tmp_path)
    sha = commit(root, "zaklad", {"a.txt": "a\n"})
    assert isinstance(sha, str) and len(sha) == 40
    assert head(root, "main") == sha
    assert head(root, "neexistujici-vetev") is None


def test_is_ancestor_says_true_and_false(tmp_path):
    root = repo(tmp_path)
    first = commit(root, "zaklad", {"a.txt": "a\n"})
    second = commit(root, "druhy", {"a.txt": "b\n"})
    run(root, "checkout", "-q", "-b", "vedle", first)
    side = commit(root, "vedle", {"c.txt": "c\n"})
    assert is_ancestor(root, first, second) is True
    assert is_ancestor(root, first, side) is True
    assert is_ancestor(root, second, side) is False
    assert is_ancestor(root, first, "0" * 40) is False


def test_commits_between_is_newest_first_and_excludes_base(tmp_path):
    root = repo(tmp_path)
    base = commit(root, "zaklad", {"a.txt": "a\n"})
    middle = commit(root, "druhy", {"a.txt": "b\n"})
    top = commit(root, "treti", {"a.txt": "c\n"})
    assert commits_between(root, base, top) == [top, middle]
    assert commits_between(root, top, top) == []
    assert commits_between(root, base, top, limit=1) == [top]
    assert commits_between(root, "0" * 40, top) == []


def test_commit_info_reads_trailers_and_changed_paths(tmp_path):
    root = repo(tmp_path)
    commit(root, "zaklad", {"a.txt": "a\n"})
    message = "feat: karta\n\nOpora-Node: node-1@2\nOpora-Node: node-9@1\nRef: OP-7\n"
    sha = commit(root, message, {"a.txt": "b\n", "sub/b.txt": "b\n"})
    info = commit_info(root, sha)
    assert info["sha"] == sha
    assert info["author"] == "Test"
    assert info["subject"] == "feat: karta"
    assert info["date"][:2] == "20" and "T" in info["date"]
    assert info["trailers"]["Opora-Node"] == ["node-1@2", "node-9@1"]
    assert info["trailers"]["Ref"] == ["OP-7"]
    assert sorted(info["paths"]) == ["a.txt", "sub/b.txt"]
    assert commit_info(root, "0" * 40) is None


def test_commit_info_of_merge_has_no_paths(tmp_path):
    root = repo(tmp_path)
    base = commit(root, "zaklad", {"a.txt": "a\n"})
    commit(root, "hlavni", {"a.txt": "b\n"})
    run(root, "checkout", "-q", "-b", "vetev", base)
    commit(root, "vetev", {"c.txt": "c\n"})
    run(root, "checkout", "-q", "main")
    run(root, "merge", "-q", "--no-ff", "-m", "spojeni", "vetev")
    info = commit_info(root, head(root))
    assert info["subject"] == "spojeni"
    assert info["paths"] == []


def test_rename_of_finds_new_name_after_git_mv(tmp_path):
    root = repo(tmp_path)
    commit(root, "zaklad", {"stare.txt": "radek\n" * 20})
    run(root, "mv", "stare.txt", "nove.txt")
    run(root, "commit", "-q", "-m", "prejmenovani")
    commit(root, "dalsi", {"jiny.txt": "x\n"})
    assert rename_of(root, "stare.txt") == "nove.txt"
    assert rename_of(root, "nikdy-nebyl.txt") is None
    assert rename_of(root, "jiny.txt") is None


def test_blob_sha_for_known_and_missing_path(tmp_path):
    root = repo(tmp_path)
    sha = commit(root, "zaklad", {"a.txt": "a\n"})
    blob = blob_sha(root, sha, "a.txt")
    assert isinstance(blob, str) and len(blob) == 40
    assert blob_sha(root, "main", "a.txt") == blob
    assert blob_sha(root, sha, "chybi.txt") is None
    assert blob_sha(root, "0" * 40, "a.txt") is None


def test_missing_repository_never_raises(tmp_path):
    root = tmp_path / "zadny-repozitar"
    assert head(root) is None
    assert is_ancestor(root, "HEAD", "HEAD") is False
    assert commits_between(root, "a", "b") == []
    assert commit_info(root, "0" * 40) is None
    assert rename_of(root, "a.txt") is None
    assert blob_sha(root, "HEAD", "a.txt") is None


def test_recent_returns_newest_first_and_respects_limit(tmp_path):
    root = repo(tmp_path)
    first = commit(root, "prvni", {"a.txt": "a\n"})
    second = commit(root, "druhy", {"b.txt": "b\n"})
    third = commit(root, "treti", {"c.txt": "c\n"})
    assert recent(root, "main") == [third, second, first]
    assert recent(root, "main", limit=2) == [third, second]
    assert recent(root, "neznama-vetev") == []
    assert recent(tmp_path / "zadny-repozitar") == []
