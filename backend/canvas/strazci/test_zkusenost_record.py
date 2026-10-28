"""Záznam zkušenosti: kroky karty (prošlo, spadlo a čím opraveno) a segmenty dokladu cesty; čisté funkce."""
from backend.canvas.strazci import zkusenost_record as records


def test_steps_summary_tracks_failures_and_their_fix():
    steps = [(1, "step.done", "x1", "s1"), (2, "step.failed", "x1", "s2"), (3, "step.done", "x2", "s2"),
             (4, "step.failed", "x2", "s3")]
    passed, failed, order = records.steps_summary(steps)
    assert passed == ["s1", "s2"] and order == ["s1", "s2", "s3"]
    assert failed == [{"step": "s2", "failures": 1, "fixedBy": {"executionId": "x2", "eventId": 3}},
                      {"step": "s3", "failures": 1, "fixedBy": None}]


def test_new_failure_after_fix_reopens_it():
    steps = [(1, "step.failed", "x1", "s1"), (2, "step.done", "x1", "s1"), (3, "step.failed", "x1", "s1")]
    passed, failed, _ = records.steps_summary(steps)
    assert passed == [] and failed == [{"step": "s1", "failures": 2, "fixedBy": None}]


def test_card_record_links_merge_and_closing_human():
    trigger = {"id": 9, "at": "2026-10-28T09:00:00.000Z", "kind": "card.closed", "workspaceId": "draft", "nodeId": "a",
               "executionId": None, "prNumber": None, "data": {"by": "human", "at": "2026-10-28T09:00:00Z"}}
    merge = {"prNumber": 12, "data": {"repository": "o/r", "mergeSha": "abc"}}
    item = records.card_record("p", trigger, [(1, "step.done", "x1", "s1")], merge)
    assert item["card"] == "a" and item["passed"] == ["s1"] and item["steps"] == ["s1"] and item["failed"] == []
    assert item["evidence"] == {"event": "card.closed", "eventId": 9, "at": "2026-10-28T09:00:00.000Z",
                                "pullRequest": {"number": 12, "repository": "o/r", "mergeSha": "abc"},
                                "closedBy": "human"}
    assert records.card_record("p", trigger, [], merge) == item | {"passed": [], "steps": []}


def test_journey_record_marks_segments_fixed_by_this_run():
    run = {"applicationId": "app", "journeyId": "j", "command": "npm run e2e", "at": "2026-10-28T09:00:00Z",
           "passed": False, "planDigest": "sha256:" + "0" * 64, "logUrl": "http://log",
           "segments": [{"from": "a", "to": "b", "ok": True}, {"from": "b", "to": "c", "ok": False, "reason": "500"}]}
    previous = {"segments": [{"from": "a", "to": "b", "ok": False, "reason": "404"}, {"from": "b", "to": "c", "ok": True}]}
    item = records.journey_record("p", "main", "page-a", 7, run, previous)
    assert item["card"] == "page-a" and item["passed"] == ["a → b"] and item["steps"] == [1, 2]
    assert item["failed"] == [{"segment": "b → c", "reason": "500", "fixedBy": None},
                              {"segment": "a → b", "reason": "404", "fixedBy": {"journeyRun": 7}}]
    assert item["evidence"]["journeyRun"] == 7 and item["evidence"]["logUrl"] == "http://log"
    assert records.journey_record("p", "main", "page-a", 7, run, None)["failed"] == item["failed"][:1]
