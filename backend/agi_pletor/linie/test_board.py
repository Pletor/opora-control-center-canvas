"""Board editoru: řádky, kuličky, spojnice follows / planned / merged a skutečné merge z gitu (kontrakt §7 bod 12)."""
import os
import time
import subprocess

from backend.agi_pletor.linie import board, merge, rows, work
from backend.agi_pletor.linie.test_branches import run
from backend.agi_pletor.linie.test_merge import GREEN, ready
from backend.agi_pletor.linie.test_work import BODY, NOW, agent_commit, refused, setup  # noqa: F401 (fixture)
from backend.brain_opora.determinism import tokens


def kinds(ball):
    return [link["kind"] for link in ball["links"]]


def prs(found):
    return lambda root: {"prs": found, "ok": True, "error": None}


NO_PR = prs({})  # repozitář bez PR: úspěšné čtení, ne výpadek


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

    found = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)
    assert [row["id"] for row in found["rows"]][:2] == ["main", "develop"] and found["mapping"]["develop"] == "develop"
    first, follow, lone = found["balls"]
    assert first["ticketId"] == tid and first["title"] == "Uzel" and first["state"] == "accepted_unmerged"
    assert first["summary"]["key"] == "accepted" and first["allowed"][0] == "merge" and first["block"] is None
    assert found["snapshot"]["sources"]["prs"]["ok"] is True and first["incomplete"] == []
    assert first["links"] == [{"to": "develop", "kind": "planned"}]  # druhá větev má vlastní řádek, bez follows
    assert follow["rowId"] != first["rowId"] and follow["ticketId"] == second
    assert first["counts"] == {"commits": 1, "prs": 0, "merges": 0} and first["mergedAt"] is None  # bez PR = 0, ne neznámo
    assert follow["title"] == "Proč a k čemu." and kinds(follow) == ["planned"] and lone["links"] == [{"to": "main", "kind": "planned"}]  # target výchozí = baseBranch
    assert all("merged" not in kinds(ball) for ball in found["balls"])  # plán nikdy jako merged (bod 12)
    assert [m for m in found["realMerges"] if m["parents"]] == []  # špičky větví z gitu nejsou merge
    assert all("closed" in row and row["closed"] is None for row in found["rows"])  # nic začleněno, pevné nikdy (§10.2)

    merge.merge(service, "draft", tid, NOW)
    found = board.board(service, "draft", "main", repo, pr_lookup=prs({"feat/uzel": {"number": 3}}))
    first = found["balls"][0]
    tip = run(repo, "rev-parse", "develop")
    assert first["state"] == "merged" and first["mergedAt"] == NOW
    assert first["links"] == [{"to": "develop", "kind": "merged", "sha": tip}]
    assert first["counts"] == {"commits": 1, "prs": 1, "merges": 1}
    shut = {row["branch"]: row["closed"] for row in found["rows"] if row["closed"]}
    assert shut == {"feat/uzel": {"at": NOW, "sha": tip, "target": "develop", "by": "merge", "balls": 1}}  # §10.2
    assert [m for m in found["realMerges"] if m["parents"]] == []  # feat/* squashem: v develop žádný merge commit
    assert kinds(found["balls"][1]) == ["planned"]  # nezačleněná kulička dál jen plán
    assert first["evidence"][-1] == {"kind": "pr", "ref": "#3", "url": None, "at": None, "src": "GitHub"}
    assert first["pr"]["ticketIds"] == [tid]  # commity bez Opora-Mark: jen úkol větve
    integration = first["axes"]["integration"]
    assert (integration["src"], integration["mode"], integration["sha"]) == ("merge log", "squash", tip)

    def down(root):
        raise OSError("GitHub neodpovídá")

    found = board.board(service, "draft", "main", repo, pr_lookup=down)  # výpadek PR nezneplatní merge log
    first = found["balls"][0]
    source = found["snapshot"]["sources"]["prs"]
    assert source["ok"] is False and "prs" in first["incomplete"] and source["lastSuccessAt"]
    assert first["pr"]["number"] == 3 and first["pr"]["unconfirmed"] is True  # poslední známý stav, zastaralý
    assert first["summary"]["key"] == "merged" and first["axes"]["integration"] == integration


def test_pr_outage_keeps_last_known_state(tmp_path):
    found, source = board.read_prs(tmp_path, "repo", lambda root: {"prs": {}, "ok": False, "error": "x"})
    assert found == {} and source["ok"] is False and source["lastSuccessAt"] is None  # nikdy nečteno
    found, source = board.read_prs(tmp_path, "repo", prs({"feat/x": {"number": 5, "state": "OPEN"}}))
    good = source["lastSuccessAt"]
    assert source["ok"] and good == source["attemptedAt"]
    found, source = board.read_prs(tmp_path, "repo", lambda root: {"prs": {}, "ok": False, "error": "OSError"})
    assert found == {"feat/x": {"number": 5, "state": "OPEN", "unconfirmed": True}}
    assert (source["ok"], source["lastSuccessAt"], source["error"]) == (False, good, "OSError")
    found, source = board.read_prs(tmp_path, "repo", NO_PR)  # prázdný seznam je úspěch a přepíše cache
    assert found == {} and source["ok"]
    assert board.read_prs(tmp_path, "repo", lambda root: {"ok": False})[0] == {}


def test_board_tags_worktrees_and_deploy_are_separate(setup, tmp_path):
    """Tag (lehký i anotovaný) patří commitu a není nasazení; worktree bez vazby nemá agenta."""
    service, repo, tid = setup
    head = agent_commit(repo)
    run(repo, "tag", "lehky", head)
    run(repo, "tag", "-a", "v1", "-m", "vydání", head)
    loose = tmp_path / "volny"
    run(repo, "worktree", "add", "-q", "--detach", str(loose), "develop")
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    found = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)
    by_name = {t["name"]: t for t in found["tags"]}
    assert (by_name["lehky"]["sha"], by_name["lehky"]["annotated"]) == (head, False)
    assert (by_name["v1"]["sha"], by_name["v1"]["annotated"]) == (head, True) and by_name["v1"]["at"]
    assert "row" not in by_name["v1"]
    assert found["deploy"] == {"envs": {}} and found["balls"][0]["axes"]["deploy"]["envs"] == {}
    read = found["snapshot"]["sources"]["deploy"]  # záznam přečten teď, i když v něm nic není
    assert read["ok"] is True and read["verifiedAt"] and "deploy" not in found["balls"][0]["incomplete"]
    spare = next(w for w in found["worktrees"] if w["path"].endswith("volny"))
    assert spare["binding"] is None and spare["sha"] == run(repo, "rev-parse", "develop") and spare["branch"] is None
    main = next(w for w in found["worktrees"] if w["branch"] == "main")
    assert main["binding"] is None  # hlavní strom bez vazby relace = jen adresář
    assert found["balls"][0]["summary"]["text"] != "probíhá"


def test_board_worktree_with_run_binding_is_live(setup, tmp_path):
    service, repo, tid = setup
    place = tmp_path / "wt-agent"
    run(repo, "worktree", "add", "-q", "-b", "feat/uzel", str(place), "develop")
    work.run(service, "draft", tid, {"sessionId": "s1", "agent": "dev", "worktree": str(place)}, tokens.stamp())
    found = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)
    bound = next(w for w in found["worktrees"] if w["branch"] == "feat/uzel")["binding"]
    assert (bound["ticketId"], bound["agent"], bound["live"], bound["to"]) == (tid, "dev", True, None)
    assert found["balls"][0]["summary"]["text"] == "probíhá"  # živá relace s vazbou
    stale = work.run(service, "draft", tid, {"sessionId": "s1"}, "2026-11-06T10:00:00Z")
    assert stale["work"]["runs"][0]["worktree"] == str(place)  # opakování bez worktree vazbu drží
    assert stale["summary"]["text"] == "probíhá (neověřeno)"  # starý heartbeat = neověřeno
    bound = next(w for w in board.board(service, "draft", "main", repo, pr_lookup=NO_PR)["worktrees"]
                 if w["branch"] == "feat/uzel")["binding"]
    assert bound["live"] is False and bound["to"] == "2026-11-06T10:00:00Z"


def test_abandon_keeps_head_and_axes(setup):
    service, repo, tid = setup
    first = agent_commit(repo)
    head = agent_commit(repo, name="v.txt")
    before = work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    after = work.abandon(service, "draft", tid, first[:9], "slepá ulička", NOW, "human")
    assert after["work"]["headSha"] == head and after["summary"] == before["summary"] and after["axes"] == before["axes"]
    assert after["work"]["abandoned"] == [{"sha": first, "why": "slepá ulička", "at": NOW, "by": "human"}]
    ball = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)["balls"][0]
    marks = {c["sha"]: c["abandoned"] for c in ball["commits"]}
    assert marks == {first: {"why": "slepá ulička", "at": NOW, "by": "human"}, head: None}
    assert ball["summary"] == before["summary"] and ball["headSha7"] == head[:7]
    assert refused(lambda: work.abandon(service, "draft", tid, run(repo, "rev-parse", "feat/a"), "x", NOW,
                                        "human")).code == "work_mismatch"


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
    found = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)
    extra = [row for row in found["rows"] if row.get("git") and row["branch"] == "feat/sirotek"]
    assert [(r["id"], r["type"], r["base"]["branch"], r["target"], r["ahead"]) for r in extra] ==         [("git:feat/sirotek", "work", "develop", "develop", 1)]
    tip = run(repo, "rev-parse", "feat/sirotek")
    assert [(m["target"], m["sha"], m["title"]) for m in found["realMerges"] if m["target"] == "feat/sirotek"] ==         [("feat/sirotek", tip, "sirotek")]
    assert not any(row.get("git") and row["branch"] in ("develop", "feat/uzel") for row in found["rows"])  # kulička už je
    assert not any(row["branch"] == "feat/stara" for row in found["rows"])  # starší než špička main = není rozpracovaná


def test_board_rows_carry_parent_and_depth(setup):
    service, repo, tid = setup
    found = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)
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
    found = board.board(service, "draft", "main", repo, pr_lookup=NO_PR)
    # řádky z gitu (feat/a z fixture) závisí na sekundě commitu vůči main; test sleduje jen ruční a automatické řádky
    listed = [(r["id"], r["branch"], r["depth"], r["planned"], r["auto"]) for r in found["rows"] if not r.get("git")]
    assert listed == [("main", "main", 0, False, False), ("develop", "develop", 1, False, False), ("items", None, 2, False, False),
                      (shared, "feat/uzel", 2, False, False), ("auto:feat/velin", "feat/velin", 2, False, True),
                      ("auto:feat/velin-linie", "feat/velin-linie", 3, False, True), (empty, None, 2, True, False)]
    assert {b["branch"]: b["rowId"] for b in found["balls"]} == {
        "feat/uzel": shared, "feat/velin": "auto:feat/velin", "feat/velin-linie": "auto:feat/velin-linie"}
    assert next(r for r in found["rows"] if r["id"] == "auto:feat/velin-linie")["parent"] == "feat/velin"


def test_with_tree_drops_empty_duplicate_row_of_claimed_branch():
    """Druhý ruční řádek se jménem větve a bez kuliček je duplikát, ne plánovaný řádek."""
    rows = [{"id": "main", "branch": "main"}, {"id": "develop", "branch": "develop"},
            {"id": "r1", "name": "feat/velin", "branch": None, "base": {"branch": "develop"}, "order": 1},
            {"id": "r2", "name": "feat/velin", "branch": None, "base": {"branch": "develop"}, "order": 2},
            {"id": "r3", "name": "Nápad", "branch": None, "base": None, "order": 3}]
    balls = [{"rowId": "r1", "branch": "feat/velin"}, {"rowId": "r2", "branch": "feat/velin"}]  # druhá kulička na duplikátu
    found = board.with_tree(rows, balls, {"main", "develop", "feat/velin"})
    assert [(r["id"], r["planned"]) for r in found] == [("main", False), ("develop", False), ("r1", False), ("r3", True)]


def test_board_repeat_spawns_nothing_and_ref_change_rebuilds(setup, monkeypatch):
    service, repo, _ = setup
    at = tokens.stamp()  # PR jako by je pozadí už přečetlo: gh se v testu nespouští
    monkeypatch.setitem(board.PR_SEEN, str(repo), (time.monotonic(), {}, {
        "verifiedAt": at, "lastSuccessAt": at, "attemptedAt": at, "ok": True, "error": None}))
    first = board.board(service, "draft", "main", repo)
    spawned, real = [], subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: spawned.append(a) or real(*a, **k))
    assert board.board(service, "draft", "main", repo) is first and spawned == []  # za tepla žádný subproces
    run(repo, "tag", "v1")  # nová reference = jiný otisk gitu
    again = board.board(service, "draft", "main", repo)
    assert again is not first and [t["name"] for t in again["tags"]] == ["v1"] and spawned
