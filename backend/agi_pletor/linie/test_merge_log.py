"""Merge log (L7 §5a): stejné op nic neprovede, started bez finished = unconfirmed, ověření jen z gitu."""
import uuid

import pytest

from backend.agi_pletor.linie import merge, merge_log, work
from backend.agi_pletor.linie.test_branches import run
from backend.agi_pletor.linie.test_merge import ready
from backend.agi_pletor.linie.test_work import NOW, refused, setup  # noqa: F401 (fixture)

STARTED = {"op": "op-1", "ticket": "tk_1", "repo": "/r", "source_sha": "a" * 40, "target": "develop",
           "target_sha_before": "b" * 40, "mode": "merge", "by": "human", "at": NOW}


def test_log_records_and_axis(tmp_path):
    merge_log.start(tmp_path, "p", STARTED)
    entries = merge_log.read(tmp_path, "p")
    assert merge_log.axis(entries, "tk_1")["state"] == "unconfirmed" and merge_log.axis(entries, "tk_2") is None
    assert merge_log.find(entries, source="a" * 40, target="develop")["op"] == "op-1"  # neověřená dvojice brzdí
    merge_log.finish(tmp_path, "p", "op-1", None, False, NOW)
    entries = merge_log.read(tmp_path, "p")
    assert merge_log.axis(entries, "tk_1") is None  # neúspěch nic nedokazuje
    assert merge_log.find(entries, source="a" * 40, target="develop") is None  # nový pokus smí
    merge_log.start(tmp_path, "p", {**STARTED, "op": "op-2"})
    merge_log.finish(tmp_path, "p", "op-2", "c" * 40, True, "2026-11-06T11:00:00Z")
    axis = merge_log.axis(merge_log.read(tmp_path, "p"), "tk_1")
    assert axis == {"state": "merged", "target": "develop", "sha": "c" * 40, "at": "2026-11-06T11:00:00Z",
                    "mode": "merge", "op": "op-2", "src": "merge log"}


def test_same_op_does_not_merge_again(setup, monkeypatch):
    service, repo, tid = setup
    ready(service, repo, tid)
    op = str(uuid.uuid4())
    done = merge.merge(service, "draft", tid, NOW, op=op, by="human")
    tip = run(repo, "rev-parse", "origin/develop")
    assert done["axes"]["integration"] == {"state": "merged", "target": "develop", "sha": tip, "at": NOW,
                                           "mode": "squash", "op": op, "src": "merge log"}

    def never(*args, **kwargs):
        raise AssertionError("druhý merge")

    monkeypatch.setattr(merge, "_operate", never)
    again = merge.merge(service, "draft", tid, NOW, op=op)
    assert again["axes"]["integration"] == done["axes"]["integration"] and len(merge_log.read(service.root, "draft")) == 1
    assert run(repo, "rev-parse", "origin/develop") == tip
    assert refused(lambda: merge.merge(service, "draft", tid, NOW, op="neni-uuid")).code == "invalid_payload"


def test_started_without_finished_is_unconfirmed_then_confirmed_from_git(setup, monkeypatch):
    service, repo, tid = setup
    ready(service, repo, tid)
    real, op = merge._operate, str(uuid.uuid4())

    def crash(*args):
        real(*args)  # git proběhl, služba spadla před finished
        raise RuntimeError("pád služby")

    monkeypatch.setattr(merge, "_operate", crash)
    with pytest.raises(RuntimeError):
        merge.merge(service, "draft", tid, NOW, op=op)
    shown = work.get(service, "draft", tid)
    assert shown["axes"]["integration"]["state"] == "unconfirmed" and shown["axes"]["integration"]["op"] == op
    assert shown["summary"]["key"] == "accepted" and "výsledek neověřen" in shown["summary"]["text"]
    assert "merge" in shown["allowed"]

    def never(*args, **kwargs):
        raise AssertionError("druhý merge")

    monkeypatch.setattr(merge, "_operate", never)
    done = merge.merge(service, "draft", tid, NOW)  # bez op: neověřená dvojice se jen ověří v gitu
    tip = run(repo, "rev-parse", "origin/develop")
    assert done["summary"]["key"] == "merged" and done["axes"]["integration"]["sha"] == tip
    assert done["axes"]["integration"]["op"] == op and done["work"]["merged"]["sha"] == tip


def test_started_but_not_in_git_is_recorded_as_failure(setup, monkeypatch):
    service, repo, tid = setup
    head = ready(service, repo, tid)
    merge_log.start(service.root, "draft", {**STARTED, "op": "op-x", "ticket": tid, "repo": str(repo),
                                            "source_sha": head})
    assert refused(lambda: merge.merge(service, "draft", tid, NOW, op=None)).code == "merge_not_done"
    assert merge_log.read(service.root, "draft")[0]["finished"]["ok"] is False
    assert merge.merge(service, "draft", tid, NOW)["summary"]["key"] == "merged"  # nový pokus s novým op
