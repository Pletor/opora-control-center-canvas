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
    assert first["summary"]["key"] == "accepted" and first["allowed"][0] == "merge" and first["block"] is None
    assert found["snapshot"]["sources"]["prs"]["ok"] is True and first["incomplete"] == ["deploy"]
    assert first["links"] == [{"to": "develop", "kind": "planned"}]  # druhá větev má vlastní řádek, bez follows
    assert follow["rowId"] != first["rowId"] and follow["ticketId"] == second
    assert first["counts"] == {"commits": 1, "prs": None, "merges": 0} and first["mergedAt"] is None
    assert follow["title"] == "Proč a k čemu." and kinds(follow) == ["planned"] and lone["links"] == [{"to": "main", "kind": "planned"}]  # target výchozí = baseBranch
    assert all("merged" not in kinds(ball) for ball in found["balls"])  # plán nikdy jako merged (bod 12)
    assert [m for m in found["realMerges"] if m["parents"]] == []  # špičky větví z gitu nejsou merge

    merge.merge(service, "draft", tid, NOW)
    found = board.board(service, "draft", "main", repo, pr_lookup=lambda root: {"feat/uzel": {"number": 3}})
    first = found["balls"][0]
    tip = run(repo, "rev-parse", "develop")
    assert first["state"] == "merged" and first["mergedAt"] == NOW
    assert first["links"] == [{"to": "develop", "kind": "merged", "sha": tip}]
    assert first["counts"] == {"commits": 1, "prs": 1, "merges": 1}
    assert [(m["target"], m["sha"]) for m in found["realMerges"] if m["parents"]] == [("develop", tip)]
    assert kinds(found["balls"][1]) == ["planned"]  # nezačleněná kulička dál jen plán
    assert first["evidence"][-1] == {"kind": "pr", "ref": "#3", "url": None, "at": None, "src": "GitHub"}

    def down(root):
        raise OSError("GitHub neodpovídá")

    found = board.board(service, "draft", "main", repo, pr_lookup=down)  # výpadek PR nezneplatní merge log
    first = found["balls"][0]
    assert found["snapshot"]["sources"]["prs"]["ok"] is False and "prs" in first["incomplete"]
    assert first["summary"]["key"] == "merged" and first["axes"]["integration"]["sha"] == tip


def test_pr_outage_keeps_last_known_state():
    good = ({"feat/x": {"number": 5, "state": "OPEN"}}, "2026-11-07T10:00:00Z")
    prs, source = board._read_prs(None, lambda root: None, good)
    assert prs == {"feat/x": {"number": 5, "state": "OPEN", "unconfirmed": True}}
    assert source["ok"] is False and source["lastSuccessAt"] == good[1] != source["attemptedAt"]
    prs, source = board._read_prs(None, lambda root: {"feat/x": {"number": 5, "state": "MERGED"}}, good)
    assert prs["feat/x"]["state"] == "MERGED" and source["ok"] and source["lastSuccessAt"] == source["attemptedAt"]


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


def test_board_rows_carry_parent_and_depth(setup):
    service, repo, tid = setup
    found = board.board(service, "draft", "main", repo, pr_lookup=lambda root: {})
    by_id = {row["id"]: row for row in found["rows"]}
    assert [(by_id[n]["parent"], by_id[n]["depth"]) for n in ("main", "develop")] == [(None, 0), ("main", 1)]
    uzel = by_id[work.get(service, "draft", tid)["work"]["rowId"]]
    assert (uzel["parent"], uzel["depth"]) == ("develop", 2)


def test_with_tree_orders_depth_first_and_chains_rows():
    def row(id, branch, base, order=0):
        return {"id": id, "branch": branch, "base": {"branch": base} if base else None, "order": order}
    rows = [row("main", "main", None), row("develop", "develop", None), row("items", None, "develop"), row("velin", None, "develop"),
            row("linie", None, "feat/velin"), row("vodotisk", None, "feat/velin-linie"), row("volny", None, None),
            row("btn", "items/btn", "develop")]
    balls = [{"rowId": "vodotisk", "branch": "feat/velin-linie-vodotisk"}, {"rowId": "velin", "branch": "feat/velin"},
             {"rowId": "linie", "branch": "feat/velin-linie"}]
    found = board.with_tree(rows, balls, {"main", "develop", "items/btn"})
    assert [(r["id"], r["depth"]) for r in found] == [  # hlavička Items hned za develop, items/<díl> pod ní
        ("main", 0), ("develop", 1), ("items", 2), ("btn", 3), ("velin", 2), ("linie", 3), ("vodotisk", 4), ("volny", 2)]
    assert {r["id"]: r["parent"] for r in found}["linie"] == "feat/velin"


def test_with_tree_skips_dead_blocked_branch_and_adds_git_parent():
    """Blokovaná kulička na smazané větvi řádek nebere; rodič jen v gitu (bez práce) dostane automatický řádek."""
    rows = [{"id": "main", "branch": "main"}, {"id": "develop", "branch": "develop"},
            {"id": "velin", "branch": None, "base": {"branch": "develop"}, "order": 1}]
    balls = [{"rowId": "velin", "branch": "topic/stara", "block": {"reason": "nahrazeno"}},
             {"rowId": "velin", "branch": "feat/velin-linie-strom"}]
    found = board.with_tree(rows, balls, {"main", "develop", "feat/velin", "feat/velin-linie"})
    assert [(r["id"], r["branch"], r["depth"]) for r in found] == [
        ("main", "main", 0), ("develop", "develop", 1), ("auto:feat/velin", "feat/velin", 2),
        ("auto:feat/velin-linie", "feat/velin-linie", 3), ("velin", "feat/velin-linie-strom", 4)]


def test_board_row_is_branch_with_manual_row_on_first_branch_and_planned_at_end(setup):
    """Tři větve na jednom ručním řádku → tři řádky ve stromovém pořadí; prázdný ruční řádek na konec jako planned."""
    service, repo, tid = setup
    run(repo, "branch", "feat/velin", "develop")
    run(repo, "branch", "feat/velin-linie", "feat/velin")
    shared = work.get(service, "draft", tid)["work"]["rowId"]
    for n, branch in enumerate(("feat/velin-linie", "feat/velin")):  # zastaralá data: víc větví na jednom řádku
        twin = f"tk_{n}" + "a" * 30
        with work.store_for(service, "draft") as store:
            store.insert(twin, "main", "issued", {"essence": "x", "build": "y", "doneCriteria": ["z"]}, {"pins": []}, NOW)
        work.attach(service, "draft", twin, {"rowId": shared, "branch": branch}, NOW, root=repo)
    empty = rows.add(service.root, "draft", "Nápad", "work")["id"]
    found = board.board(service, "draft", "main", repo, pr_lookup=lambda root: {})
    # řádky z gitu (feat/a z fixture) závisí na sekundě commitu vůči main; test sleduje jen ruční a automatické řádky
    listed = [(r["id"], r["branch"], r["depth"], r["planned"], r["auto"]) for r in found["rows"] if not r.get("git")]
    assert listed == [("main", "main", 0, False, False), ("develop", "develop", 1, False, False), ("items", None, 2, False, False),
                      (shared, "feat/uzel", 2, False, False), ("auto:feat/velin", "feat/velin", 2, False, True),
                      ("auto:feat/velin-linie", "feat/velin-linie", 3, False, True), (empty, None, 2, True, False)]
    assert {b["branch"]: b["rowId"] for b in found["balls"]} == {
        "feat/uzel": shared, "feat/velin": "auto:feat/velin", "feat/velin-linie": "auto:feat/velin-linie"}
    assert next(r for r in found["rows"] if r["id"] == "auto:feat/velin-linie")["parent"] == "feat/velin"
