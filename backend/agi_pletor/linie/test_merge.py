"""Začlenění službou nad dočasným repozitářem s bare originem (kontrakt §7 body 4, 5, 6, 8, 10, 11)."""
from backend.agi_pletor.linie import merge, merge_log, rows, work
from backend.agi_pletor.linie.test_branches import commit, run
from backend.agi_pletor.linie.test_work import BODY, NOW, agent_commit, refused, setup  # noqa: F401 (fixture)
from backend.integrations import gitio
from database.repositories.tickets import TicketStore

GREEN = [{"name": "npm test", "status": "green"}]


def ready(service, repo, tid, checks=GREEN):
    """Commit, report, přijetí a povolení do develop."""
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, checks, None, NOW, "agent:t")
    work.accept(service, "draft", tid, head, "", NOW, untested=True)
    if checks == GREEN:
        work.allow_merge(service, "draft", tid, "develop", NOW)
    return head


def code(service, tid, **kwargs):
    return refused(lambda: merge.merge(service, "draft", tid, NOW, **kwargs)).code


def forced_accept(service, tid, sha, allow=None):
    """Přijetí (a s `allow` i povolení) zapsané mimo pravidlo L7, které by bez zelených kontrol odmítlo:
    merge.py musí ověřit sám."""
    with work.store_for(service, "draft") as store:
        found = store.get(tid)["work"]
        extra = {"mergeAllowed": {"target": "develop", "targetSha": allow, "sourceSha": sha}} if allow else {}
        store.set_work(tid, {**found, "acceptance": {"sha": sha, "by": "human", "at": NOW}, **extra}, NOW)


def test_merge_refusals(setup):
    service, repo, tid = setup
    agent_commit(repo)
    head = run(repo, "rev-parse", "feat/uzel")
    work.report(service, "draft", tid, head, [], None, NOW, "agent:t")
    assert code(service, tid) == "no_acceptance"  # bod 4
    forced_accept(service, tid, head)
    assert code(service, tid) == "not_allowed"
    work.report(service, "draft", tid, head, [{"name": "npm test", "status": "green"}], None, NOW, "agent:t")
    work.allow_merge(service, "draft", tid, "develop", NOW)
    work.report(service, "draft", tid, head, [{"name": "lint", "status": "red"}], None, NOW, "agent:t")
    assert code(service, tid) == "checks_failed"  # bod 6
    work.report(service, "draft", tid, head, [{"name": "lint", "status": "green"}], None, NOW, "agent:t")
    agent_commit(repo, name="v.txt")  # nová hlava, přijetí platí pro starou (bod 5)
    assert code(service, tid) == "head_moved"
    newer = run(repo, "rev-parse", "feat/uzel")
    work.report(service, "draft", tid, newer, [], None, NOW, "agent:t")
    assert work.get(service, "draft", tid)["summary"]["key"] == "nocheck"  # L7 §8: bez kontrol nocheck, ne stale
    forced_accept(service, tid, newer, allow=run(repo, "rev-parse", "develop"))
    assert code(service, tid) == "checks_missing"
    assert run(repo, "rev-parse", "develop") == run(repo, "rev-parse", "origin/develop")  # nic se nesloučilo


def test_target_moved(setup):
    service, repo, tid = setup
    ready(service, repo, tid)
    run(repo, "checkout", "-q", "develop")
    commit(repo, "jiny.txt")  # cíl se posunul mezi allow-merge a merge (bod 8)
    run(repo, "push", "-q", "origin", "develop")  # špička cíle = origin
    run(repo, "checkout", "-q", "main")
    assert code(service, tid) == "target_moved"


def test_unreported_tip_blocks_accept_of_old_revision(setup):
    """Regrese oponenta: report A (zelené) → commit B bez reportu → accept(A) = 409 head_moved, souhrn ≠ pending."""
    service, repo, tid = setup
    old = agent_commit(repo)
    work.report(service, "draft", tid, old, GREEN, None, NOW, "agent:t")
    assert work.get(service, "draft", tid)["summary"]["key"] == "pending"
    tip = agent_commit(repo, name="v.txt")
    shown = work.get(service, "draft", tid)
    assert shown["summary"]["key"] != "pending" and "accept" not in shown["allowed"]
    assert shown["axes"]["work"] == {"state": "in_progress", "sha": tip, "src": "git log · bez hlášení"}
    assert shown["axes"]["checks"]["state"] == "missing" and shown["summary"]["reason"].startswith(f"HEAD {tip[:7]}")
    assert refused(lambda: work.accept(service, "draft", tid, old, "", NOW)).code == "head_moved"
    assert work.get(service, "draft", tid)["work"]["acceptance"] is None


def test_allow_merge_recovers_after_target_moved(setup):
    service, repo, tid = setup
    ready(service, repo, tid)
    run(repo, "checkout", "-q", "develop")
    moved = commit(repo, "jiny.txt")  # cíl se posunul po allow-merge
    run(repo, "push", "-q", "origin", "develop")
    run(repo, "checkout", "-q", "main")
    shown = work.get(service, "draft", tid)
    assert "allow_merge" in shown["allowed"] and "merge" not in shown["allowed"]
    assert shown["blocked"]["merge"].startswith("cíl develop se od povolení posunul (") and moved[:7] in shown["blocked"]["merge"]
    assert shown["next"].startswith("Člověk povolí začlenění znovu")
    again = work.allow_merge(service, "draft", tid, "develop", NOW)
    assert again["work"]["mergeAllowed"]["targetSha"] == moved and "merge" in again["allowed"]
    assert merge.merge(service, "draft", tid, NOW)["summary"]["key"] == "merged"


def test_stale_local_target_uses_origin_tip(setup):
    """Lokální develop zaostává za originem (drží ho jiný strom): povolení i merge jedou z origin, push projde."""
    service, repo, tid = setup
    old = run(repo, "rev-parse", "develop")
    run(repo, "checkout", "-q", "develop")
    ahead = commit(repo, "jiny.txt")
    run(repo, "push", "-q", "origin", "develop")
    run(repo, "checkout", "-q", "main")
    run(repo, "update-ref", "refs/heads/develop", old)
    ready(service, repo, tid)
    assert work.get(service, "draft", tid)["work"]["mergeAllowed"]["targetSha"] == ahead
    done = merge.merge(service, "draft", tid, NOW)
    tip = run(repo, "rev-parse", "origin/develop")
    assert done["state"] == "merged" and done["work"]["merged"]["sha"] == tip and run(repo, "rev-parse", f"{tip}^1") == ahead


def test_merge_writes_from_git_and_is_idempotent(setup):
    service, repo, tid = setup
    with service.lock_for("draft"), service.db_for("draft") as db:
        db.execute("UPDATE tickets SET status='verified' WHERE id=?", (tid,))
    head = ready(service, repo, tid)
    done = merge.merge(service, "draft", tid, NOW)
    tip = run(repo, "rev-parse", "origin/develop")
    assert done["state"] == "merged" and done["work"]["merged"]["sha"] == tip and done["status"] == "closed"
    assert run(repo, "log", "-1", "--format=%P", tip).count(" ") == 0  # feat/* squashem: jeden rodič (§2)
    assert run(repo, "rev-parse", "develop") == tip  # lokální develop není vybraný → posunut
    assert run(repo, "worktree", "list", "--porcelain").count("worktree ") == 1
    assert not (service.root / "pletor" / "linie" / "merge" / tid).exists()
    again = merge.merge(service, "draft", tid, NOW)  # bod 10: žádný druhý merge
    assert again["work"]["merged"] == done["work"]["merged"] and run(repo, "rev-parse", "origin/develop") == tip
    assert work.report(service, "draft", tid, head, [], None, NOW, "agent:t")["work"]["merged"]["sha"] == tip


def test_merge_recorded_from_git_after_lost_write(setup, monkeypatch):
    service, repo, tid = setup
    ready(service, repo, tid)
    real = merge._record

    def lost(*args):
        raise RuntimeError("zápis selhal")

    monkeypatch.setattr(merge, "_record", lost)
    try:
        merge.merge(service, "draft", tid, NOW)
    except RuntimeError:
        pass
    tip = run(repo, "rev-parse", "origin/develop")
    assert work.get(service, "draft", tid)["work"]["merged"] is None
    monkeypatch.setattr(merge, "_record", real)
    done = merge.merge(service, "draft", tid, NOW)  # bod 11: dožene se z gitu, bez druhého merge
    assert done["work"]["merged"]["sha"] == tip and run(repo, "rev-parse", "origin/develop") == tip


def test_push_failed(setup):
    service, repo, tid = setup
    ready(service, repo, tid)

    def no_push(root, *args, **kwargs):
        return None if "push" in args else gitio.git(root, *args, **kwargs)

    assert code(service, tid, git=no_push) == "push_failed"
    assert work.get(service, "draft", tid)["work"]["merged"] is None
    with service.reading("draft"):
        assert TicketStore(service.db_for("draft"), "draft").get(tid)["status"] == "issued"


def test_merge_only_into_parent(setup):
    service, repo, tid = setup
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    work.accept(service, "draft", tid, head, "", NOW, untested=True)
    work.allow_merge(service, "draft", tid, "main", NOW)  # člověk povolil cíl, který není rodič
    assert code(service, tid) == "target_not_parent"
    assert run(repo, "rev-parse", "main") == run(repo, "rev-parse", "origin/main")


def test_squash_one_commit_with_message_trailer_and_log(setup):
    """§2: feat/* jde do rodiče jedním commitem; log `squash`, uzavření a `unreported` podle logu, ne podle předků."""
    service, repo, tid = setup
    before = run(repo, "rev-parse", "origin/develop")
    first = agent_commit(repo)
    head = agent_commit(repo, name="v.txt")
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    work.accept(service, "draft", tid, head, "", NOW, untested=True)
    work.allow_merge(service, "draft", tid, "develop", NOW)
    done = merge.merge(service, "draft", tid, NOW)
    tip = run(repo, "rev-parse", "origin/develop")
    mark = done["work"]["mark"]
    assert run(repo, "log", "-1", "--format=%P", tip) == before  # jeden rodič: squash, ne merge commit
    assert run(repo, "log", "-1", "--format=%(trailers:key=Opora-Mark,valueonly)", tip) == mark
    body = gitio.git(repo, "log", "-1", "--format=%B", tip).split("\n")  # utf-8; run() čte v kódování konzole
    assert body[0] == "Uzel" and "Proč a k čemu." in body
    assert f"{first[:7]} přidán u.txt" in "\n".join(body) and f"{head[:7]} přidán v.txt" in "\n".join(body)
    entry = merge_log.read(service.root, "draft")[-1]
    started, finished = entry["started"], entry["finished"]
    assert (started["mode"], started["source_sha"], finished["result_sha"], finished["ok"]) == ("squash", head, tip, True)
    assert done["work"]["merged"]["mode"] == "squash" and done["work"]["merged"]["sha"] == tip
    shown = work.get(service, "draft", tid)
    assert work.unreported(shown["work"], shown["axes"]["integration"]) == (None, True)
    assert shown["summary"]["key"] == "merged"
    assert merge.merge(service, "draft", tid, NOW)["work"]["merged"] == done["work"]["merged"]  # idempotentní
    assert run(repo, "rev-parse", "origin/develop") == tip


def test_squash_second_ball_on_same_branch_keeps_first_merged(setup):
    """Commit po squashi kuličku znovu otevře; jakmile ho squashne další kulička téže větve, první je zase začleněná."""
    service, repo, tid = setup
    head = ready(service, repo, tid)
    merge.merge(service, "draft", tid, NOW)
    run(repo, "checkout", "-q", "feat/uzel")
    run(repo, "merge", "-q", "--no-edit", "develop")  # agent si vezme cíl, ať druhá kulička stojí na jeho špičce
    run(repo, "checkout", "-q", "main")
    row = work.get(service, "draft", tid)["work"]["rowId"]
    second = work.create(service, "draft", "main", BODY, {"rowId": row, "title": "Další", "branch": "feat/uzel",
                                                          "baseBranch": "develop", "target": "develop"}, NOW,
                         root=repo)["ticketId"]
    newer = agent_commit(repo, name="w.txt")
    assert work.get(service, "draft", tid)["summary"]["key"] != "merged"  # nový commit po squashi
    work.report(service, "draft", second, newer, GREEN, None, NOW, "agent:t")
    work.accept(service, "draft", second, newer, "", NOW, untested=True)
    work.allow_merge(service, "draft", second, "develop", NOW)
    assert merge.merge(service, "draft", second, NOW)["summary"]["key"] == "merged"
    assert work.get(service, "draft", tid)["summary"]["key"] == "merged" and head != newer


def test_squash_conflict_resets_tree(setup):
    service, repo, tid = setup
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    work.accept(service, "draft", tid, head, "", NOW, untested=True)
    run(repo, "checkout", "-q", "develop")
    commit(repo, "u.txt", "jinak")  # stejný soubor jinak v cíli = konflikt
    run(repo, "push", "-q", "origin", "develop")
    run(repo, "checkout", "-q", "main")
    work.allow_merge(service, "draft", tid, "develop", NOW)
    calls = []

    def spy(root, *args, **kwargs):
        calls.append(args)
        return gitio.git(root, *args, **kwargs)

    tip = run(repo, "rev-parse", "origin/develop")
    assert code(service, tid, git=spy) == "merge_conflict"
    assert ("reset", "--hard") in calls and ("merge", "--abort") not in calls
    assert merge_log.read(service.root, "draft")[-1]["finished"]["ok"] is False
    assert run(repo, "rev-parse", "origin/develop") == tip
    assert run(repo, "worktree", "list", "--porcelain").count("worktree ") == 1


def test_develop_into_main_stays_merge_commit(setup):
    """Ostatní typy řádků (develop → main) slučují dál merge commitem."""
    service, repo, _ = setup
    run(repo, "checkout", "-q", "develop")
    head = commit(repo, "rel.txt")
    run(repo, "checkout", "-q", "main")
    row = rows.add(service.root, "draft", "Vydání", "work")
    tid = work.create(service, "draft", "main", BODY, {"rowId": row["id"], "title": "Vydání", "branch": "develop",
                                                       "baseBranch": "main", "target": "main"}, NOW, root=repo)["ticketId"]
    work.report(service, "draft", tid, head, GREEN, None, NOW, "agent:t")
    work.accept(service, "draft", tid, head, "", NOW, untested=True)
    work.allow_merge(service, "draft", tid, "main", NOW)
    done = merge.merge(service, "draft", tid, NOW)
    tip = run(repo, "rev-parse", "origin/main")
    assert done["work"]["merged"]["mode"] == "merge" and run(repo, "rev-parse", f"{tip}^2") == head
    assert merge_log.read(service.root, "draft")[-1]["started"]["mode"] == "merge"


def test_forget_blocked_ball_whose_code_was_squashed(setup):
    """Zapomenout blokovanou kuličku jde i po squashi: její commity leží pod zdrojem hotového squashe téže větve."""
    service, repo, tid = setup
    old = agent_commit(repo)
    work.report(service, "draft", tid, old, GREEN, None, NOW, "agent:t")
    work.block(service, "draft", tid, "nahrazeno", NOW)
    row = work.get(service, "draft", tid)["work"]["rowId"]
    second = work.create(service, "draft", "main", BODY, {"rowId": row, "title": "Náhrada", "branch": "feat/uzel",
                                                          "baseBranch": "develop", "target": "develop"}, NOW,
                         root=repo)["ticketId"]
    assert refused(lambda: work.forget(service, "draft", tid, NOW)).code == "forget_code_alive"
    head = agent_commit(repo, name="v.txt")
    work.report(service, "draft", second, head, GREEN, None, NOW, "agent:t")
    work.accept(service, "draft", second, head, "", NOW, untested=True)
    work.allow_merge(service, "draft", second, "develop", NOW)
    merge.merge(service, "draft", second, NOW)
    assert work.forget(service, "draft", tid, NOW)["forgotten"] == tid
