"""Práce ticketu na Linii nad dočasným repozitářem s bare originem (kontrakt §7 body 2, 3, 5, 6, 10 a brána deliver)."""
import pytest

from backend.agi_pletor.linie import journal, previews, rows, work
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
    assert found["summary"]["key"] == "todo" and found["incomplete"] == ["prs"]
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
    accepted = work.accept(service, "draft", tid, head[:7], "ok", NOW, untested=True)
    assert accepted["work"]["acceptance"]["sha"] == head and accepted["state"] == "accepted_unmerged"
    assert accepted["allowed"] == ["allow_merge", "preview", "revoke_accept", "defer", "block"]
    allowed = work.allow_merge(service, "draft", tid, None, NOW)
    again = refused(lambda: work.allow_merge(service, "draft", tid, None, NOW))
    assert again.code == "action_not_allowed" and again.body()["error"] == "už povoleno pro HEAD"
    assert allowed["work"]["mergeAllowed"]["targetSha"] == develop and "merge" in allowed["next"]
    # přijetí ani povolení nic neslučuje (bod 3)
    assert (run(repo, "rev-parse", "develop"), run(repo, "rev-parse", "origin/develop")) == (develop, origin)
    newer = agent_commit(repo, name="v.txt")
    stale = work.report(service, "draft", tid, newer, [{"name": "npm test", "status": "green"}], None, NOW, "agent:t")
    assert stale["state"] == "stale"  # přijetí starého SHA po novém commitu (bod 5)
    # L7a: zrušení zastaralého přijetí projde (úklid); bez přijetí už není co rušit
    assert work.revoke_accept(service, "draft", tid, NOW)["state"] == "open"
    assert refused(lambda: work.revoke_accept(service, "draft", tid, NOW)).code == "action_not_allowed"


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
    assert made()["rowId"] == own["rowId"]  # druhá kulička téže větve bez rowId jde na řádek větve, ne na duplikát
    named = rows.add(service.root, "draft", "feat/ctvrta", "work")["id"]
    assert made(branch="feat/ctvrta")["rowId"] == named  # prázdný řádek se jménem větve je její řádek
    assert refused(lambda: made(rowId="row_nic")).status == 404
    assert refused(lambda: made(branch="feat/x", baseBranch="main")).code == "branch_hierarchy"  # řádek se nezaloží
    assert [r["name"] for r in rows.read(service.root, "draft")["rows"]].count("feat/x") == 0


def test_decisions_pass_without_git_and_carry_by(setup, monkeypatch):
    service, repo, tid = setup
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, [], None, NOW, "agent:t")
    strict = []

    def down(root, *args, optional=False, **kwargs):  # git nedostupný: optional = None, jinak pád
        if not optional:
            strict.append(args)
            raise ValueError("git nedostupný")
        return None
    monkeypatch.setattr(work, "git", down)
    assert work.block(service, "draft", tid, "čeká na API", NOW, "agent:dev")["work"]["blocked"]["by"] == "agent:dev"
    assert work.unblock(service, "draft", tid, NOW, "human")["work"]["decided"] == {
        "action": "unblock", "at": NOW, "by": "human"}
    assert work.defer(service, "draft", tid, NOW, "agent:dev")["work"]["decided"]["by"] == "agent:dev"
    assert work.resume(service, "draft", tid, NOW, "human")["work"]["deferred"] is False
    left = work.abandon(service, "draft", tid, head[:9], "slepá ulička", NOW, "agent:dev")["work"]["abandoned"]
    assert left == [{"sha": head, "why": "slepá ulička", "at": NOW, "by": "agent:dev"}]
    assert strict == []


def test_commit_after_merge_already_in_target_does_not_reopen(setup):
    """§10.2: další commit větve po merge kuličky, který do cíle dostala pozdější kulička, není „nová revize“."""
    _, repo, _ = setup
    first = agent_commit(repo)
    run(repo, "checkout", "-q", "develop")
    run(repo, "merge", "-q", "--no-ff", "-m", "merge 1", first)
    merge_sha = run(repo, "rev-parse", "HEAD").strip()
    run(repo, "checkout", "-q", "main")
    record = {"repository": str(repo), "branch": "feat/uzel", "headSha": first, "target": "develop",
              "merged": {"sha": merge_sha, "target": "develop"}}
    later = agent_commit(repo, name="v.txt")
    assert work.unreported(record) == (later, True)
    run(repo, "checkout", "-q", "develop")
    run(repo, "merge", "-q", "--no-ff", "-m", "merge 2", later)
    run(repo, "checkout", "-q", "main")
    assert work.unreported(record) == (None, True)


def store_for_test(service):
    return work.store_for(service, "draft")


def test_forget_deletes_only_blocked_dead_end(setup):
    """§10.4: zapomenout jde jen blokovanou kuličku bez živého kódu mimo cíl; po merge do cíle zmizí i s deníkem."""
    service, repo, tid = setup
    assert refused(lambda: work.forget(service, "draft", tid, NOW)).code == "forget_not_blocked"
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, [], None, NOW, "agent:t")
    work.block(service, "draft", tid, "šlo se jinudy", NOW)
    assert refused(lambda: work.forget(service, "draft", tid, NOW)).code == "forget_code_alive"
    run(repo, "checkout", "-q", "develop")
    run(repo, "merge", "-q", "--no-ff", "-m", "merge", head)
    run(repo, "checkout", "-q", "main")
    with store_for_test(service) as store:  # cíl zanikl při přestavbě stromu, kód je ve develop → zapomenout jde
        store.set_work(tid, {**work.get(service, "draft", tid)["work"], "target": "topic/zanikla"}, NOW)
    assert work.forget(service, "draft", tid, NOW)["forgotten"] == tid
    assert refused(lambda: work.get(service, "draft", tid)).status == 404


class Alive:
    """Běžící proces náhledu (bez serveru)."""
    pid = 1

    def poll(self):
        return None


GREEN = [{"name": "npm test", "status": "green"}]


def preview_at(service, tid, sha, monkeypatch, state="running"):
    """Náhled kuličky v registru (`state`), jako by ho člověk spustil; `running` drží podvržený proces."""
    record = {"slug": "feat-uzel", "branch": "feat/uzel", "sha": sha, "state": state, "port": 8790,
              "url": "http://127.0.0.1:8790/?project=draft&workspace=main", "startedAt": NOW}
    previews._save(work.folder(service), {"feat-uzel": record})
    monkeypatch.setitem(previews.RUNNING, "feat-uzel", Alive())
    return work.set_preview(service, "draft", tid, record, NOW)


def started(monkeypatch, fail=False):
    """Podvržený `previews.start` (bez worktree a npm): zapíše `building` na špičku větve."""
    calls = []

    def start(folder, root, branch, project, data_root, now, **kwargs):
        if fail:
            raise OSError("worktree zamčený")
        calls.append(branch)
        record = {**previews._read(folder)["feat-uzel"], "sha": run(root, "rev-parse", branch), "state": "building"}
        previews._save(folder, {"feat-uzel": record})
        return record
    monkeypatch.setattr(work.previews, "start", start)
    return calls


def test_tried_and_accept_follow_the_trial(setup, monkeypatch):
    """§6–§8: zkouška zapíše SHA běžícího náhledu, přijetí chce vyzkoušenou hlavu, novinky od zkoušky."""
    service, repo, tid = setup
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    assert refused(lambda: work.mark_tried(service, "draft", tid, NOW)).code == "preview_not_running"
    assert work.get(service, "draft", tid)["trial"]["state"] == "none"
    assert preview_at(service, tid, head, monkeypatch, "failed")["trial"]["state"] == "failed"
    building = preview_at(service, tid, head, monkeypatch, "building")
    assert building["work"]["preview"]["state"] == "building" and building["trial"]["state"] == "building"
    assert refused(lambda: work.mark_tried(service, "draft", tid, NOW)).status == 409
    preview_at(service, tid, head, monkeypatch)
    untried = refused(lambda: work.accept(service, "draft", tid, head, "", NOW))
    assert untried.code == "not_tried" and untried.body()["error"].startswith(f"Nevyzkoušeno, hlava je {head[:7]}")
    tried = work.mark_tried(service, "draft", tid, NOW)
    assert tried["work"]["tried"] == {"sha": head, "at": NOW}
    assert tried["trial"] == {"state": "current", "url": "http://127.0.0.1:8790/?project=draft&workspace=main",
                              "sha": head, "head": head, "tried": {"sha": head, "at": NOW}, "triedCurrent": True,
                              "news": [], "newsMore": 0, "steps": []}
    events = journal.read(service, "draft", 0, 100)["events"]
    assert any(e["kind"] == "linie.preview.tried" and e["refs"]["sha"] == head for e in events)
    newer = agent_commit(repo, name="v.txt")
    started(monkeypatch)
    work.report(service, "draft", tid, newer, GREEN, None, NOW, "agent:t")
    shown = work.get(service, "draft", tid)
    assert shown["trial"]["state"] == "building" and shown["trial"]["triedCurrent"] is False
    assert shown["trial"]["news"] == [{"sha": newer, "subject": "přidán v.txt"}]
    stale = refused(lambda: work.accept(service, "draft", tid, newer, "", NOW))
    assert stale.code == "not_tried" and stale.body()["error"].startswith(
        f"Vyzkoušeno na {head[:7]}, hlava je {newer[:7]}.")
    blind = work.accept(service, "draft", tid, newer, "", NOW, untested=True)
    assert blind["work"]["acceptance"]["tested"] is None and blind["axes"]["acceptance"]["tested"] is None
    work.revoke_accept(service, "draft", tid, NOW)
    preview_at(service, tid, newer, monkeypatch)
    work.mark_tried(service, "draft", tid, NOW)
    assert work.accept(service, "draft", tid, newer, "", NOW)["work"]["acceptance"]["tested"] == newer


def test_report_tryout_kept_and_trial_url_points_to_change(setup, monkeypatch):
    """Doplněk: report s `tryout` ho uloží, report bez něj převezme; `trial.url` míří na místo změny."""
    service, repo, tid = setup
    head = agent_commit(repo)
    tryout = {"at": "screen=pletor&project=jiny&part=linie", "steps": [" Otevři Linii ", "Uvidíš kuličku"]}
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t", tryout)
    newer = agent_commit(repo, name="v.txt")
    work.report(service, "draft", tid, newer, GREEN, None, NOW, "agent:t")
    preview_at(service, tid, newer, monkeypatch)
    shown = work.get(service, "draft", tid)
    assert shown["work"]["tryout"] == {"at": tryout["at"], "steps": ["Otevři Linii", "Uvidíš kuličku"], "sha": head}
    assert shown["trial"]["steps"] == ["Otevři Linii", "Uvidíš kuličku"]
    assert shown["trial"]["url"] == ("http://127.0.0.1:8790/?project=draft&workspace=main"
                                     "&screen=pletor&part=linie")  # `project` náhledu se nezdvojí


def test_tryout_refuses_absolute_url_and_oversize():
    for at in ("https://evil.example/?a=1", "//evil.example/?a=1", "javascript:alert(1)", "?a=1", "a=1#x",
               "a=" + "x" * 300):
        assert refused(lambda: work.tryout_of({"at": at, "steps": []}, "s")).code == "invalid_payload"
    for steps in (["x"] * 9, ["x" * 201], [""], "krok"):
        assert refused(lambda: work.tryout_of({"at": "a=1", "steps": steps}, "s")).status == 422
    assert work.tryout_of({"at": "", "steps": ["x"]}, "s") == {"at": "", "steps": ["x"], "sha": "s"}
    assert work.with_at("http://h/?project=p", "") == "http://h/?project=p" and work.with_at(None, "a=1") is None


def test_trial_stale_and_news_cap(setup, monkeypatch):
    service, repo, tid = setup
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    preview_at(service, tid, head, monkeypatch)
    work.mark_tried(service, "draft", tid, NOW)
    for index in range(12):
        tip = agent_commit(repo, name=f"n{index}.txt")
    shown = work.get(service, "draft", tid)["trial"]  # nehlášené commity: hlava = špička větve
    assert shown["state"] == "stale" and shown["head"] == tip and shown["sha"] == head
    assert len(shown["news"]) == 10 and shown["newsMore"] == 2 and shown["news"][0]["sha"] == tip


def test_report_restarts_existing_preview_only_on_new_head(setup, monkeypatch):
    """§3: náhled se drží hlavy; bez náhledu, se zastaveným nebo na téže hlavě se nic nespouští."""
    service, repo, tid = setup
    calls = started(monkeypatch)
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    assert calls == []  # bez náhledu: první spuštění je akce člověka
    preview_at(service, tid, head, monkeypatch)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    assert calls == []  # stejná hlava
    newer = agent_commit(repo, name="v.txt")
    done = work.report(service, "draft", tid, newer, GREEN, None, NOW, "agent:t")
    assert calls == ["feat/uzel"] and done["work"]["preview"]["sha"] == newer
    assert done["work"]["preview"]["state"] == "building" and done["work"]["headSha"] == newer
    preview_at(service, tid, newer, monkeypatch, "stopped")
    newest = agent_commit(repo, name="w.txt")
    work.report(service, "draft", tid, newest, GREEN, None, NOW, "agent:t")
    assert calls == ["feat/uzel"]  # zastavený náhled člověk vypnul


def test_failed_restart_keeps_report(setup, monkeypatch):
    service, repo, tid = setup
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    preview_at(service, tid, head, monkeypatch)
    started(monkeypatch, fail=True)
    newer = agent_commit(repo, name="v.txt")
    assert work.report(service, "draft", tid, newer, GREEN, None, NOW, "agent:t")["work"]["headSha"] == newer


def test_gate_deliver_restarts_preview(setup, monkeypatch):
    service, repo, tid = setup
    calls = started(monkeypatch)
    office = gate.authenticate(service, gate.open_session(service, {"project": "draft", "workspace": "main",
                                                                    "worker": {"name": "office-1"}})["token"])
    kinds.run(service, office, {"kind": "ticket.claim", "body": {"ticketId": tid}})
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    preview_at(service, tid, head, monkeypatch)
    newer = agent_commit(repo, name="v.txt")
    kinds.run(service, office, {"kind": "ticket.deliver", "body": {"ticketId": tid, "summary": "Hotovo.", "sha": newer,
                                                                   "tryout": {"at": "part=linie", "steps": ["Klikni"]}}})
    shown = work.get(service, "draft", tid)
    assert calls == ["feat/uzel"] and shown["work"]["preview"]["sha"] == newer
    assert shown["work"]["tryout"] == {"at": "part=linie", "steps": ["Klikni"], "sha": newer}  # brána tryout propustí
    assert "tryout" not in shown["delivery"]
