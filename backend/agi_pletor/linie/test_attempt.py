"""Pokus: evidence bez zdvojení, ověření báze a cizí větve, zotavení po pádu, publikace po report."""
import pytest

from backend.agi_pletor.linie import attempt, idempotency, journal, work
from backend.agi_pletor.linie.test_branches import run
from backend.agi_pletor.linie.test_work import NOW, agent_commit, refused, setup  # noqa: F401 (fixture)
from database.repositories.tickets import TicketStore


def attempts(service, tid):
    return work.get(service, "draft", tid)["work"]["attempts"]


def test_attempt_records_offered_base_and_never_takes_foreign_branch(setup):
    service, repo, tid = setup
    shown = attempt.attempt(service, "draft", tid, {"branch": "feat/uzel"}, "agent:dev", NOW)
    [made] = shown["work"]["attempts"]
    assert made["baseRef"] == "develop" and made["baseSha"] == run(repo, "rev-parse", "develop")  # rodič ze jména
    assert (made["createdBy"], made["agent"], made["published"]) == ("agent", "dev", False)
    assert run(repo, "branch", "--list", "feat/uzel") == ""  # služba větev nezakládá
    attempt.attempt(service, "draft", tid, {"branch": "feat/uzel", "baseRef": "develop"}, "human", NOW)
    assert len(attempts(service, tid)) == 1  # stejná větev = týž pokus
    tip = run(repo, "rev-parse", "feat/a")
    foreign = refused(lambda: attempt.attempt(service, "draft", tid, {"branch": "feat/a", "baseRef": "items/1-t"},
                                              "agent:dev", NOW))
    assert foreign.code == "branch_foreign" and run(repo, "rev-parse", "feat/a") == tip  # nepřepsáno
    assert refused(lambda: attempt.attempt(service, "draft", tid, {"branch": "feat/b", "baseRef": "develop",
                                                                   "baseSha": run(repo, "rev-parse", "items/1-t")},
                                           "agent:dev", NOW)).code == "base_mismatch"
    assert refused(lambda: attempt.attempt(service, "draft", tid, {"branch": "feat/b", "baseRef": "nic"},
                                           "agent:dev", NOW)).code == "base_missing"
    assert [e["kind"] for e in journal.read(service, "draft")["events"]].count("linie.attempt") == 1


def test_crash_between_branch_and_evidence_recovers_without_duplicate(setup, monkeypatch):
    service, repo, tid = setup
    head = agent_commit(repo)  # agent založil větev feat/uzel z develop
    original, calls = TicketStore.set_work, []

    def crash_once(self, *args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("pád služby před zápisem evidence")
        return original(self, *args)
    monkeypatch.setattr(TicketStore, "set_work", crash_once)
    payload = {"branch": "feat/uzel", "baseRef": "develop", "ticket": tid}

    def act(ident):
        return attempt.attempt(service, "draft", tid, payload, "agent:dev", NOW, "at_" + ident)
    with pytest.raises(RuntimeError):
        idempotency.once(service, "draft", "attempt", "klic-1", payload, act)
    assert attempts(service, tid) == [] and run(repo, "rev-parse", "feat/uzel") == head
    again = idempotency.once(service, "draft", "attempt", "klic-1", payload, act)
    idempotency.once(service, "draft", "attempt", "klic-1", payload, act)
    assert [a["attemptId"] for a in again["work"]["attempts"]] == ["at_" + idempotency.ident("attempt", "klic-1")]
    assert len(attempts(service, tid)) == 1 and run(repo, "rev-parse", "feat/uzel") == head
    conflict = refused(lambda: idempotency.once(service, "draft", "attempt", "klic-1", {**payload, "branch": "feat/x"},
                                                act))
    assert (conflict.status, conflict.code) == (409, "idempotency_conflict")


def test_publish_after_push(setup):
    service, repo, tid = setup
    attempt.attempt(service, "draft", tid, {"branch": "feat/uzel"}, "agent:dev", NOW)
    agent_commit(repo)
    assert attempt.publish(service, "draft", tid, NOW) is None  # jen lokální větev
    run(repo, "push", "-q", "origin", "feat/uzel")
    run(repo, "update-ref", "-d", "refs/remotes/origin/feat/uzel")  # publikaci ověří až fetch
    [made] = attempt.publish(service, "draft", tid, NOW)["work"]["attempts"]
    assert made["published"] is True and made["publishedSha"] == run(repo, "rev-parse", "feat/uzel")
