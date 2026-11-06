"""Začlenění službou nad dočasným repozitářem s bare originem (kontrakt §7 body 4, 5, 6, 8, 10, 11)."""
from backend.agi_pletor.linie import merge, work
from backend.agi_pletor.linie.test_branches import commit, run
from backend.agi_pletor.linie.test_work import NOW, agent_commit, refused, setup  # noqa: F401 (fixture)
from backend.integrations import gitio
from database.repositories.tickets import TicketStore

GREEN = [{"name": "npm test", "status": "green"}]


def ready(service, repo, tid, checks=GREEN):
    """Commit, report, přijetí a povolení do develop."""
    head = agent_commit(repo)
    work.report(service, "draft", tid, head, checks, None, NOW, "agent:t")
    work.accept(service, "draft", tid, head, "", NOW)
    if checks == GREEN:
        work.allow_merge(service, "draft", tid, "develop", NOW)
    return head


def code(service, tid, **kwargs):
    return refused(lambda: merge.merge(service, "draft", tid, NOW, **kwargs)).code


def test_merge_refusals(setup):
    service, repo, tid = setup
    agent_commit(repo)
    head = run(repo, "rev-parse", "feat/uzel")
    work.report(service, "draft", tid, head, [], None, NOW, "agent:t")
    assert code(service, tid) == "no_acceptance"  # bod 4
    work.accept(service, "draft", tid, head, "", NOW)
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
    assert work.get(service, "draft", tid)["state"] == "stale"
    work.accept(service, "draft", tid, newer, "", NOW)
    work.allow_merge(service, "draft", tid, "develop", NOW)
    assert code(service, tid) == "checks_missing"
    assert run(repo, "rev-parse", "develop") == run(repo, "rev-parse", "origin/develop")  # nic se nesloučilo


def test_target_moved(setup):
    service, repo, tid = setup
    ready(service, repo, tid)
    run(repo, "checkout", "-q", "develop")
    commit(repo, "jiny.txt")  # cíl se posunul mezi allow-merge a merge (bod 8)
    run(repo, "checkout", "-q", "main")
    assert code(service, tid) == "target_moved"


def test_merge_writes_from_git_and_is_idempotent(setup):
    service, repo, tid = setup
    with service.lock_for("draft"), service.db_for("draft") as db:
        db.execute("UPDATE tickets SET status='verified' WHERE id=?", (tid,))
    head = ready(service, repo, tid)
    done = merge.merge(service, "draft", tid, NOW)
    tip = run(repo, "rev-parse", "origin/develop")
    assert done["state"] == "merged" and done["work"]["merged"]["sha"] == tip and done["status"] == "closed"
    assert run(repo, "rev-parse", f"{tip}^2") == head  # merge commit --no-ff, druhý rodič je hlava úkolu
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
