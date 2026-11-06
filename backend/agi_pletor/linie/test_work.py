"""Práce ticketu na Linii nad dočasným repozitářem s bare originem (kontrakt §7 body 2, 3, 5, 6, 10 a brána deliver)."""
import pytest

from backend.agi_pletor.linie import rows, work
from backend.agi_pletor.linie.test_branches import commit, make_repo, run
from backend.brain_opora.determinism import gate, kinds
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService

NOW = "2026-11-06T10:00:00Z"
BODY = {"essence": "Proč a k čemu.", "build": "Datový uzel.", "doneCriteria": ["npm test projde"]}


def cloned(path):
    """Repozitář z `make_repo` s bare originem (main, develop, items/1-t nahoře), bez sítě."""
    path.mkdir(parents=True, exist_ok=True)
    origin = path / "origin.git"
    run(path, "init", "-q", "--bare", "-b", "main", str(origin))
    repo = make_repo(path / "repo")
    run(repo, "remote", "add", "origin", str(origin))
    run(repo, "push", "-q", "origin", "main", "develop", "items/1-t")
    run(repo, "fetch", "-q", "origin")
    return repo


def agent_commit(repo, branch="feat/uzel", base="develop", name="u.txt"):
    """Agent založí větev z báze (pokud ještě není), commitne a vrátí se na main."""
    exists = run(repo, "branch", "--list", branch)
    run(repo, "checkout", "-q", *([branch] if exists else ["-b", branch, base]))
    sha = commit(repo, name)
    run(repo, "checkout", "-q", "main")
    return sha


@pytest.fixture
def setup(tmp_path):
    repo = cloned(tmp_path / "git")
    service = CanvasService(tmp_path / "data")
    row = rows.add(service.root, "draft", "Datový uzel", "work")
    ticket = work.create(service, "draft", "main", BODY, {"rowId": row["id"], "title": "Uzel", "branch": "feat/uzel",
                                                          "baseBranch": "develop", "target": "develop"}, NOW, root=repo)
    yield service, repo, ticket["ticketId"]
    service.close()


def refused(act):
    with pytest.raises(GateError) as caught:
        act()
    return caught.value


def test_create_does_not_make_branch(setup):
    service, repo, tid = setup
    found = work.get(service, "draft", tid)
    assert found["status"] == "issued" and found["state"] == "open" and found["stateLabel"] == "nezačato"
    assert found["summary"]["key"] == "todo" and found["incomplete"] == ["prs", "deploy"]
    assert found["work"]["baseSha"] == run(repo, "rev-parse", "develop") and found["work"]["headSha"] is None
    assert run(repo, "branch", "--list", "feat/uzel") == ""
    assert refused(lambda: work.create(service, "draft", "main", BODY, {"rowId": "row_nic", "branch": "feat/x",
                                                                        "baseBranch": "develop"}, NOW)).status == 404
    assert refused(lambda: work.create(service, "draft", "main", BODY, {"rowId": "main", "branch": "feat x",
                                                                        "baseBranch": "develop"}, NOW)).status == 422


def test_report_checks_sha_on_branch(setup):
    service, repo, tid = setup
    other = run(repo, "rev-parse", "feat/a")  # existuje, ale na jiné větvi
    for sha in (other, "abc1234", "nehex"):
        assert refused(lambda: work.report(service, "draft", tid, sha, [], None, NOW, "agent:t")).code == "work_mismatch"
    head = agent_commit(repo)
    done = work.report(service, "draft", tid, head[:9], [{"name": "npm test", "status": "green"}], "/wt", NOW, "agent:t")
    assert done["work"]["headSha"] == head and done["work"]["worktree"] == "/wt"
    assert done["state"] == "open" and done["work"]["merged"] is None  # commit kuličku neuzavírá (bod 2)
    again = work.report(service, "draft", tid, head, [{"name": "npm test", "status": "green"}], None, NOW, "agent:t")
    assert len(again["work"]["checks"]) == 1  # opakovaný report bez duplicit (bod 10)


def test_accept_states_and_no_merge(setup):
    service, repo, tid = setup
    develop, origin = run(repo, "rev-parse", "develop"), run(repo, "rev-parse", "origin/develop")
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, [], None, NOW, "agent:t")
    assert refused(lambda: work.allow_merge(service, "draft", tid, None, NOW)).code == "no_acceptance"
    assert refused(lambda: work.accept(service, "draft", tid, "abc1234", "", NOW)).code == "head_moved"
    # L7 §8: revize bez kontrol (nocheck) ani s červenými (failed) přijmout nejde; dřív se přijalo a čekalo na kontroly
    early = refused(lambda: work.accept(service, "draft", tid, head[:7], "ok", NOW))
    assert (early.status, early.code) == (409, "action_not_allowed") and "CI ověří HEAD" in early.body()["error"]
    red = work.report(service, "draft", tid, head, [{"name": "npm test", "status": "red"}], None, NOW, "agent:t")
    assert red["state"] == "awaiting_checks" and red["summary"]["key"] == "failed"
    assert refused(lambda: work.accept(service, "draft", tid, head, "ok", NOW)).code == "action_not_allowed"
    green = work.report(service, "draft", tid, head, [{"name": "npm test", "status": "green"}], None, NOW, "agent:t")
    assert green["state"] == "open" and green["allowed"][0] == "accept"
    accepted = work.accept(service, "draft", tid, head[:7], "ok", NOW)
    assert accepted["work"]["acceptance"]["sha"] == head and accepted["state"] == "accepted_unmerged"
    allowed = work.allow_merge(service, "draft", tid, None, NOW)
    assert allowed["work"]["mergeAllowed"]["targetSha"] == develop and "merge" in allowed["next"]
    # přijetí ani povolení nic neslučuje (bod 3)
    assert (run(repo, "rev-parse", "develop"), run(repo, "rev-parse", "origin/develop")) == (develop, origin)
    newer = agent_commit(repo, name="v.txt")
    stale = work.report(service, "draft", tid, newer, [{"name": "npm test", "status": "green"}], None, NOW, "agent:t")
    assert stale["state"] == "stale"  # přijetí starého SHA po novém commitu (bod 5)
    assert work.revoke_accept(service, "draft", tid, NOW)["state"] == "open"


def test_block_defer_resume(setup):
    service, _, tid = setup
    assert work.block(service, "draft", tid, "chybí klíč", NOW)["state"] == "blocked"
    assert work.defer(service, "draft", tid, NOW)["state"] == "blocked"
    assert work.resume(service, "draft", tid, NOW)["state"] == "open"
    assert work.defer(service, "draft", tid, NOW)["stateLabel"] == "odloženo"


def test_gate_deliver_goes_through_report(setup):
    service, repo, tid = setup
    office = gate.authenticate(service, gate.open_session(service, {"project": "draft", "workspace": "main",
                                                                    "worker": {"name": "office-1"}})["token"])
    kinds.run(service, office, {"kind": "ticket.claim", "body": {"ticketId": tid}})
    off = run(repo, "rev-parse", "feat/a")
    with pytest.raises(GateError) as caught:
        kinds.run(service, office, {"kind": "ticket.deliver", "body": {"ticketId": tid, "summary": "Hotovo.",
                                                                       "sha": off}})
    assert caught.value.code == "work_mismatch" and work.get(service, "draft", tid)["status"] == "claimed"
    head = agent_commit(repo)
    kinds.run(service, office, {"kind": "ticket.deliver", "body": {"ticketId": tid, "summary": "Hotovo.", "sha": head}})
    found = work.get(service, "draft", tid)
    assert found["status"] == "delivered" and found["work"]["headSha"] == head and found["state"] == "awaiting_checks"


def test_mark_runs_and_report_run_id(setup):
    service, repo, tid = setup
    created = work.get(service, "draft", tid)["work"]
    assert created["mark"] == "OP-" + tid[3:9].upper() and created["runs"] == []
    head = agent_commit(repo)  # větev už existuje → relace zamkne fromSha
    first = work.run(service, "draft", tid, {"sessionId": "s1", "agent": "dev"}, NOW)["work"]["runs"][0]
    assert first["fromSha"] == head and first["startedAt"] == NOW
    again = work.run(service, "draft", tid, {"sessionId": "s1", "transcriptPath": "/t.jsonl"}, "2026-11-06T11:00:00Z")
    (only,) = again["work"]["runs"]
    assert only["runId"] == first["runId"] and only["startedAt"] == NOW and only["transcriptPath"] == "/t.jsonl"
    assert only["agent"] == "dev"
    work.run(service, "draft", tid, {"sessionId": "s2", "agent": "other"}, NOW)
    head = agent_commit(repo, name="v.txt")
    done = work.report(service, "draft", tid, head, [{"name": "npm test", "status": "green"}], None, NOW, "agent:dev")
    assert done["work"]["headRunId"] == first["runId"] and done["work"]["checks"][0]["runId"] == first["runId"]
    odd = work.report(service, "draft", tid, head, [], None, NOW, "human")  # bez shodného agenta: poslední relace
    assert odd["work"]["headRunId"] == odd["work"]["runs"][-1]["runId"]


def test_mark_collision_takes_next_chars(setup):
    service, repo, tid = setup
    row = rows.add(service.root, "draft", "Druhý", "work")
    twin = "tk_" + tid[3:9] + "a" * 26  # stejných prvních 6 znaků
    with work.store_for(service, "draft") as store:
        store.insert(twin, "main", "issued", {"essence": "x", "build": "y", "doneCriteria": ["z"]}, {"pins": []}, NOW)
    found = work.attach(service, "draft", twin, {"rowId": row["id"], "branch": "feat/dva", "baseBranch": "develop"}, NOW, root=repo)
    assert found["work"]["mark"] == "OP-" + twin[9:15].upper()


def test_hierarchy_derives_parent_and_refuses_wrong_one(setup):
    service, repo, _ = setup
    row = rows.add(service.root, "draft", "Strom", "work")["id"]

    def made(branch, **extra):
        return work.create(service, "draft", "main", BODY, {"rowId": row, "branch": branch, **extra}, NOW,
                           root=repo)["work"]

    run(repo, "branch", "feat/velin", "develop")
    derived = made("feat/velin-linie")  # rodič z existujícího prefixu, cíl = rodič
    assert (derived["baseBranch"], derived["target"]) == ("feat/velin", "feat/velin")
    assert derived["baseSha"] == run(repo, "rev-parse", "feat/velin")
    assert refused(lambda: made("feat/velin-linie", baseBranch="main")).code == "branch_hierarchy"
    assert refused(lambda: made("feat/velinzzz", baseBranch="feat/velin")).code == "branch_hierarchy"
    assert refused(lambda: made("feat/velin-linie", target="develop")).code == "target_not_parent"
    assert made("items/tlacitko", target="feat/velin")["target"] == "feat/velin"  # items smí do feat
    assert made("fix/x", baseBranch="feat/velin")["target"] == "feat/velin"


def test_create_without_row_or_with_taken_row_makes_branch_row(setup):
    service, repo, tid = setup
    first_row = work.get(service, "draft", tid)["work"]["rowId"]

    def made(**extra):
        return work.create(service, "draft", "main", BODY, {"branch": "feat/dalsi", **extra}, NOW, root=repo)["work"]

    own = made()  # bez rowId: řádek větve se založí
    fresh = [r for r in rows.read(service.root, "draft")["rows"] if r["id"] == own["rowId"]][0]
    assert (fresh["name"], fresh["type"], fresh["base"]["branch"], fresh["target"]) == ("feat/dalsi", "work", "develop", "develop")
    assert made(rowId=first_row, branch="feat/treti")["rowId"] not in (first_row, own["rowId"])  # řádek drží feat/uzel
    assert work.create(service, "draft", "main", BODY, {"branch": "items/dil", "rowId": own["rowId"]}, NOW,
                       root=repo)["work"]["rowId"] != own["rowId"]
    assert made(rowId=first_row, branch="feat/uzel")["rowId"] == first_row  # tatáž větev zůstává na svém řádku
    assert refused(lambda: made(rowId="row_nic")).status == 404
    assert refused(lambda: made(branch="feat/x", baseBranch="main")).code == "branch_hierarchy"  # řádek se nezaloží
    assert [r["name"] for r in rows.read(service.root, "draft")["rows"]].count("feat/x") == 0
