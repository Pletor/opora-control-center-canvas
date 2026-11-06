"""Board editoru: řádky, kuličky, spojnice follows / planned / merged a skutečné merge z gitu (kontrakt §7 bod 12)."""
import os
import subprocess

from backend.agi_pletor.linie import board, merge, rows, work
from backend.agi_pletor.linie.test_branches import run
from backend.agi_pletor.linie.test_merge import ready
from backend.agi_pletor.linie.test_work import BODY, NOW, setup  # noqa: F401 (fixture)


def kinds(ball):
    return [link["kind"] for link in ball["links"]]


def test_board_links_and_real_merges(setup):
    service, repo, tid = setup
    row_id = work.get(service, "draft", tid)["work"]["rowId"]
    second = work.create(service, "draft", "main", BODY, {"rowId": row_id, "branch": "feat/dalsi",
                                                          "baseBranch": "develop", "target": "develop"}, NOW,
                         root=repo)["ticketId"]
    other_row = rows.add(service.root, "draft", "Pokus", "experiment")["id"]
    work.create(service, "draft", "main", BODY, {"rowId": other_row, "branch": "experiment/x",
                                                 "baseBranch": "main"}, NOW, root=repo)
    ready(service, repo, tid)

    found = board.board(service, "draft", "main", repo, pr_lookup=lambda root: {})
    assert [row["id"] for row in found["rows"]][:2] == ["main", "develop"] and found["mapping"]["develop"] == "develop"
    first, follow, lone = found["balls"]
    assert first["ticketId"] == tid and first["title"] == "Uzel" and first["state"] == "accepted_unmerged"
    assert first["links"] == [{"to": second, "kind": "follows"}, {"to": "develop", "kind": "planned"}]
    assert first["counts"] == {"commits": 1, "prs": None, "merges": 0} and first["mergedAt"] is None
    assert follow["title"] == "Proč a k čemu." and kinds(follow) == ["planned"] and lone["links"] == []
    assert all("merged" not in kinds(ball) for ball in found["balls"])  # plán nikdy jako merged (bod 12)
    assert [m for m in found["realMerges"] if m["parents"]] == []  # špičky větví z gitu nejsou merge

    merge.merge(service, "draft", tid, NOW)
    found = board.board(service, "draft", "main", repo, pr_lookup=lambda root: {"feat/uzel": {"number": 3}})
    first = found["balls"][0]
    tip = run(repo, "rev-parse", "develop")
    assert first["state"] == "merged" and first["mergedAt"] == NOW
    assert first["links"][1] == {"to": "develop", "kind": "merged", "sha": tip}
    assert first["counts"] == {"commits": 1, "prs": 1, "merges": 1}
    assert [(m["target"], m["sha"]) for m in found["realMerges"] if m["parents"]] == [("develop", tip)]
    assert kinds(found["balls"][1]) == ["planned"]  # nezačleněná kulička dál jen plán


def test_board_shows_unmerged_git_branch_without_row(setup):
    """Větev z gitu bez řádku je v editoru vidět jako řádek `git` se špičkou; po založení řádku zmizí duplicita."""
    service, repo, _ = setup
    run(repo, "checkout", "-q", "-b", "feat/stara", "develop")
    (repo / "stara.txt").write_text("x", encoding="utf-8")
    run(repo, "add", ".")
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), "commit", "-q", "-m", "stara"],
                   check=True, env={**os.environ, "GIT_COMMITTER_DATE": "2020-01-01T00:00:00"})
    run(repo, "checkout", "-q", "-b", "feat/sirotek", "develop")
    (repo / "sirotek.txt").write_text("x", encoding="utf-8")
    run(repo, "add", "."), run(repo, "commit", "-q", "-m", "sirotek")
    run(repo, "checkout", "-q", "main")
    found = board.board(service, "draft", "main", repo, pr_lookup=lambda root: {})
    extra = [row for row in found["rows"] if row.get("git") and row["branch"] == "feat/sirotek"]
    assert [(r["id"], r["type"], r["base"]["branch"], r["target"], r["ahead"]) for r in extra] ==         [("git:feat/sirotek", "work", "develop", "develop", 1)]
    tip = run(repo, "rev-parse", "feat/sirotek")
    assert [(m["target"], m["sha"], m["title"]) for m in found["realMerges"] if m["target"] == "feat/sirotek"] ==         [("feat/sirotek", tip, "sirotek")]
    assert not any(row.get("git") and row["branch"] in ("develop", "feat/uzel") for row in found["rows"])  # kulička už je
    assert not any(row["branch"] == "feat/stara" for row in found["rows"])  # starší než špička main = není rozpracovaná
