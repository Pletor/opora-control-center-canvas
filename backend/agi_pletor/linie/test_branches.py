"""Větve z dočasného repozitáře: role z předpony, rodič, ahead/behind, server, diff vůči cíli."""
import subprocess

import pytest

from backend.agi_pletor.linie import branches


def run(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, name, text="x"):
    (repo / name).write_text(text, encoding="utf-8")
    run(repo, "add", name)
    run(repo, "commit", "-q", "-m", f"přidán {name}")
    return run(repo, "rev-parse", "HEAD")


def make_repo(path):
    """main s jedním commitem, develop z něj, items/1-t z develop s commitem, feat/a z develop se dvěma."""
    path.mkdir(exist_ok=True)
    run(path, "init", "-q", "-b", "main")
    commit(path, "a.txt")
    run(path, "branch", "develop")
    run(path, "checkout", "-q", "-b", "items/1-t", "develop")
    commit(path, "b.txt")
    run(path, "checkout", "-q", "-b", "feat/a", "develop")
    commit(path, "c.txt")
    commit(path, "d.txt")
    run(path, "checkout", "-q", "main")
    return path


@pytest.mark.parametrize("name, role", [
    ("main", "main"), ("develop", "develop"), ("items/1-x", "items"), ("topic/1-x", "other"), ("feat/x", "feat"),
    ("experiment/x", "experiment"), ("fix/x", "fix"), ("hotfix/1", "hotfix"), ("chore/x", "other"),
    ("feat", "other"),
])
def test_role(name, role):
    assert branches.role(name) == role


def test_summary(tmp_path):
    repo = make_repo(tmp_path / "r")
    run(repo, "branch", "experiment/v", "main")
    run(repo, "branch", "hotfix/1", "main")
    run(repo, "branch", "chore/x", "main")
    found = branches.summary(repo)
    rows = {b["name"]: b for b in found["branches"]}
    assert found["main"] == {"sha": run(repo, "rev-parse", "main"), "remote": None}
    assert found["develop"]["sha"] == found["main"]["sha"]
    assert found["server"] == {"branch": "main", "sha": found["main"]["sha"], "dirty": False}
    assert {n: r["parent"] for n, r in rows.items()} == {
        "main": None, "develop": "main", "items/1-t": "develop", "feat/a": "develop",
        "experiment/v": "develop", "hotfix/1": "main", "chore/x": "develop"}
    assert (rows["feat/a"]["ahead"], rows["feat/a"]["behind"]) == (2, 0)
    assert (rows["items/1-t"]["ahead"], rows["items/1-t"]["behind"]) == (1, 0)
    assert rows["feat/a"]["role"] == "feat" and rows["feat/a"]["sha"] == run(repo, "rev-parse", "feat/a")
    (repo / "a.txt").write_text("změna", encoding="utf-8")
    assert branches.summary(repo)["server"]["dirty"] is True


def test_nested_feat_parent_and_depth(tmp_path):
    repo = make_repo(tmp_path / "r")
    run(repo, "branch", "feat/a-b", "feat/a")
    run(repo, "branch", "feat/a-b-c", "feat/a-b")
    run(repo, "branch", "feat/a-x-y", "feat/a")  # mezičlánek feat/a-x chybí
    rows = {b["name"]: b for b in branches.summary(repo)["branches"]}
    assert [(rows[n]["parent"], rows[n]["depth"]) for n in ("feat/a", "feat/a-b", "feat/a-b-c", "feat/a-x-y")] == [
        ("develop", 2), ("feat/a", 3), ("feat/a-b", 4), ("feat/a", 3)]
    assert (rows["main"]["depth"], rows["develop"]["depth"], rows["items/1-t"]["depth"]) == (0, 1, 2)


def test_diff(tmp_path):
    repo = make_repo(tmp_path / "r")
    found = branches.diff(repo, "feat/a", "develop")
    assert [c["title"] for c in found["commits"]] == ["přidán d.txt", "přidán c.txt"]
    assert all(len(c["sha7"]) >= 7 for c in found["commits"])
    assert found["files"] == 2 and "2 files changed" in found["stat"]
    with pytest.raises(ValueError, match="neexistuje"):
        branches.diff(repo, "feat/nic", "develop")
    with pytest.raises(ValueError):
        branches.diff(repo, "--output=x", "develop")


def test_not_a_repo(tmp_path):
    with pytest.raises(ValueError):
        branches.summary(tmp_path)
