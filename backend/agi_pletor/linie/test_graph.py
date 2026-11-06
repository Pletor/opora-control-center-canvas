"""Graf Linie z dočasného repozitáře: které větve mají linii, odbočení, commity nejstarší první, přijetí, PR."""
import pytest

from backend.agi_pletor.linie import graph
from backend.agi_pletor.linie.test_branches import commit, make_repo, run

OLD, NEW, NEWEST = "2026-01-01T10:00:00+01:00", "2026-02-01T10:00:00Z", "2026-03-01T10:00:00Z"


def test_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_COMMITTER_DATE", OLD)
    repo, folder = make_repo(tmp_path / "r"), tmp_path / "pletor"
    run(repo, "branch", "fix/old", "main")
    run(repo, "checkout", "-q", "fix/old")
    commit(repo, "old.txt")  # nesloučená, ale stejně stará jako main → bez linie
    run(repo, "branch", "feat/merged", "main")  # sloučená, ale s přijetím → linie
    accepted = {"feat/merged": {"sha": run(repo, "rev-parse", "main"), "by": "human"}}  # work.acceptance z ticketu
    monkeypatch.setenv("GIT_COMMITTER_DATE", NEW)
    run(repo, "checkout", "-q", "develop")
    develop_tip = commit(repo, "dev.txt")
    monkeypatch.setenv("GIT_COMMITTER_DATE", NEWEST)
    run(repo, "checkout", "-q", "feat/a")
    head = commit(repo, "e.txt")
    run(repo, "checkout", "-q", "main")

    found = graph.graph(repo, folder, accepted, pr_lookup=lambda root: {"feat/a": {"number": 7, "state": "OPEN", "url": "u",
                                                                          "base": "topic/1-t"}})
    lanes = {lane["name"]: lane for lane in found["lanes"]}
    main = run(repo, "rev-parse", "main")
    assert [lane["name"] for lane in found["lanes"]] == ["main", "develop", "feat/a", "feat/merged", "topic/1-t"]
    assert found["active"] == "feat/a"
    assert lanes["main"]["base"] is None and lanes["main"]["parent"] is None
    assert [c["sha"] for c in lanes["main"]["commits"]] == [main]
    assert lanes["main"]["commits"][0]["at"] == "2026-01-01T09:00:00Z"
    assert lanes["develop"]["base"] == main
    assert [c["sha"] for c in lanes["develop"]["commits"]] == [main, develop_tip]
    assert lanes["develop"]["commits"][1]["parents"] == [main]
    assert lanes["topic/1-t"]["parent"] == "develop" and lanes["topic/1-t"]["base"] == main
    feat = lanes["feat/a"]
    assert feat["parent"] == "topic/1-t" and feat["sha"] == head
    assert [c["title"] for c in feat["commits"]] == ["přidán c.txt", "přidán d.txt", "přidán e.txt"]
    assert feat["commits"][-1]["sha7"] == head[:7] and feat["pr"]["number"] == 7
    assert feat["acceptance"] is None and feat["preview"] is None
    assert lanes["feat/merged"]["acceptance"]["valid"] is True and lanes["feat/merged"]["commits"] == []
    assert lanes["develop"]["pr"] is None


def test_develop_equal_to_main(tmp_path):
    repo = make_repo(tmp_path / "r")
    develop = graph.graph(repo, tmp_path / "p", pr_lookup=lambda root: {})["lanes"][1]
    assert develop["name"] == "develop" and [c["sha"] for c in develop["commits"]] == [run(repo, "rev-parse", "main")]


def test_gh_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(graph.shutil, "which", lambda name: None)
    assert graph.gh_prs(tmp_path) == {}


def test_not_a_repo(tmp_path):
    with pytest.raises(ValueError):
        graph.graph(tmp_path, tmp_path / "p", pr_lookup=lambda root: {})
