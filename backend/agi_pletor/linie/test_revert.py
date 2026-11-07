"""Revert služby: ověřená hlava, nový commit, konflikt není `finished`; rebase jen jako evidence."""
from backend.agi_pletor.linie import journal, revert
from backend.agi_pletor.linie.test_branches import commit, run
from backend.agi_pletor.linie.test_work import NOW, agent_commit, refused, setup  # noqa: F401 (fixture)

OP = "3f2b8c1e-0000-4000-8000-000000000001"


def test_revert_makes_new_commit_and_is_idempotent(setup):
    service, repo, tid = setup
    first = agent_commit(repo, name="u.txt")
    head = agent_commit(repo, name="v.txt")
    assert refused(lambda: revert.revert(service, "draft", tid, first, first, NOW, op=OP)).code == "head_moved"
    done = revert.revert(service, "draft", tid, first, head[:9], NOW, op=OP, by="agent:dev")
    tip = run(repo, "rev-parse", "feat/uzel")
    assert done["state"] == "finished" and done["result_sha"] == tip and run(repo, "rev-parse", "feat/uzel^") == head
    assert "u.txt" not in run(repo, "ls-tree", "--name-only", "feat/uzel").split()
    assert revert.revert(service, "draft", tid, first, head, NOW, op=OP) == done  # stejné op nic neopakuje
    assert run(repo, "rev-parse", "feat/uzel") == tip
    kinds = [e["kind"] for e in journal.read(service, "draft")["events"]]
    assert kinds[-2:] == ["linie.revert.started", "linie.revert.finished"]


def test_revert_conflict_is_not_finished(setup):
    service, repo, tid = setup
    run(repo, "checkout", "-q", "-b", "feat/uzel", "develop")
    old = commit(repo, "k.txt", "první")
    head = commit(repo, "k.txt", "druhá")  # stejné řádky: revert prvního koliduje
    run(repo, "checkout", "-q", "main")
    caught = refused(lambda: revert.revert(service, "draft", tid, old, head, NOW, op=OP))
    assert (caught.status, caught.code) == (409, "revert_conflict")
    [entry] = revert.read(service.root, "draft")
    assert entry["state"] == "conflict" and entry["result_sha"] is None
    assert run(repo, "rev-parse", "feat/uzel") == head and run(repo, "worktree", "list").count("\n") == 0


def test_rebase_note_is_evidence_only(setup):
    service, repo, tid = setup
    before = run(repo, "for-each-ref")
    entry = revert.rebase_note(service, "draft", tid, "a" * 40, "b" * 7, "agent:dev", NOW)
    assert (entry["kind"], entry["from"], entry["to"]) == ("rebase", "a" * 40, "b" * 7)
    assert run(repo, "for-each-ref") == before
    assert journal.read(service, "draft")["events"][-1]["kind"] == "linie.rebase.noted"
    assert refused(lambda: revert.rebase_note(service, "draft", tid, "nehex", "b" * 7, "human", NOW)).status == 422
