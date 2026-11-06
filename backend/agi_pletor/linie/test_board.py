"""Board editoru: řádky, kuličky, spojnice follows / planned / merged a skutečné merge z gitu (kontrakt §7 bod 12)."""
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
    assert found["realMerges"] == []

    merge.merge(service, "draft", tid, NOW)
    found = board.board(service, "draft", "main", repo, pr_lookup=lambda root: {"feat/uzel": {"number": 3}})
    first = found["balls"][0]
    tip = run(repo, "rev-parse", "develop")
    assert first["state"] == "merged" and first["mergedAt"] == NOW
    assert first["links"][1] == {"to": "develop", "kind": "merged", "sha": tip}
    assert first["counts"] == {"commits": 1, "prs": 1, "merges": 1}
    assert [(m["target"], m["sha"]) for m in found["realMerges"]] == [("develop", tip)]
    assert kinds(found["balls"][1]) == ["planned"]  # nezačleněná kulička dál jen plán
