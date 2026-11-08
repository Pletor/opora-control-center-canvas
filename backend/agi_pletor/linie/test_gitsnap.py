"""Snímek gitu v požadavku odpovídá stejně jako git a po novém commitu nevrací starou špičku."""
import itertools

from backend.agi_pletor.linie import gitsnap
from backend.agi_pletor.linie.test_branches import commit, make_repo, run


def _from_git(repo):
    """Odpovědi mimo scope = přímo z gitu."""
    refs = ["main", "develop", "feat/a", "items/1-t", "nic", run(repo, "rev-parse", "feat/a~1")]
    return ({ref: gitsnap.rev(repo, ref) for ref in refs},
            {(a, b): gitsnap.ancestor(repo, a, b) for a, b in itertools.product(refs, repeat=2)},
            {(a, b): gitsnap.range_tip(repo, a, b) for a, b in itertools.product(refs, repeat=2)})


def test_scope_answers_like_git_and_sees_new_commit(tmp_path):
    repo = make_repo(tmp_path / "r")
    expected = _from_git(repo)
    with gitsnap.scope():
        assert _from_git(repo) == expected
    run(repo, "checkout", "-q", "feat/a")
    tip = commit(repo, "e.txt")  # ref se pohne: další požadavek musí vidět novou špičku
    with gitsnap.scope():
        assert gitsnap.rev(repo, "feat/a") == tip
        assert gitsnap.range_tip(repo, "develop", "feat/a") == tip
        assert gitsnap.ancestor(repo, "main", "feat/a") and not gitsnap.ancestor(repo, "feat/a", "develop")
        assert _from_git(repo)[0]["feat/a"] == tip


def test_frozen_remembers_only_sha_arguments(tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "r")
    base, head = run(repo, "rev-parse", "develop"), run(repo, "rev-parse", "feat/a")
    calls = []
    real = gitsnap.git
    monkeypatch.setattr(gitsnap, "git", lambda *a, **k: calls.append(a) or real(*a, **k))
    for _ in range(2):
        assert len(gitsnap.frozen(repo, "log", "--format=%H", f"{base}..{head}").split()) == 2
        gitsnap.frozen(repo, "log", "--format=%H", "develop..feat/a")  # jména se mění, pamatovat nesmí
    assert len(calls) == 3


def test_state_moves_with_commit_and_snapshot_survives_requests(tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "r")
    before = gitsnap.state(repo)
    assert before is not None and gitsnap.state(repo) == before
    with gitsnap.scope():
        tip = gitsnap.rev(repo, "feat/a")
    calls = []
    real = gitsnap.git
    monkeypatch.setattr(gitsnap, "git", lambda *a, **k: calls.append(a) or real(*a, **k))
    with gitsnap.scope():  # další požadavek bez změny: snímek z paměti, žádný git
        assert gitsnap.rev(repo, "feat/a") == tip and calls == []
    run(repo, "checkout", "-q", "feat/a")
    moved = commit(repo, "f.txt")
    assert gitsnap.state(repo) != before
    with gitsnap.scope():
        assert gitsnap.rev(repo, "feat/a") == moved and calls
