"""Tělo `deliver` a co z něj server odvodí: 422 s polem, poznámky kroků z commitů karty, selfChecks a pořadí kontrol."""
import subprocess

import pytest

from backend.canvas import opora_execution_deliver_body as rules
from backend.canvas.payload_errors import InvalidPayload

SCOPE = {"project": "p1", "workspace": "draft"}
PINNED = [{"id": "s1"}, {"id": "s2"}]


def body(**extra):
    return rules.validate_body({**SCOPE, "summary": "Hotovo.", **extra})


@pytest.mark.parametrize("extra,field", [
    ({"summary": " "}, "summary"),
    ({"steps": [{"stepId": "s1", "status": "ok"}]}, "steps[]"),
    ({"steps": [{"stepId": "s1", "status": "done"}, {"stepId": "s1", "status": "done"}]}, "steps[]"),
    ({"commit": "HEAD"}, "commit"),
    ({"checks": [{"name": "npm test", "status": "passed"}]}, "checks[]"),
    ({"close": "yes"}, "close"),
    ({"stepz": []}, "body"),
])
def test_invalid_body_names_the_field(extra, field):
    with pytest.raises(InvalidPayload) as error:
        rules.validate_body({**SCOPE, "summary": "Hotovo.", **extra})
    assert error.value.field == field and error.value.example == rules.EXAMPLE


def test_step_without_notes_takes_commit_subjects_else_summary():
    value = body(steps=[{"stepId": "s1", "status": "done"}, {"stepId": "s2", "status": "done", "notes": "vlastní"}],
                 checks=[{"name": "npm test", "status": "green"}])
    commits = [{"sha": "a" * 40, "subject": "Komponenta"}, {"sha": "b" * 40, "subject": "Test"}]
    items = rules.step_results(value, commits, PINNED)
    assert items[0]["evidence"] == {"notes": "Komponenta; Test", "commits": ["a" * 40, "b" * 40], "checks": ["npm test"]}
    assert items[1]["evidence"]["notes"] == "vlastní"
    assert rules.step_results(value, [], PINNED)[0]["evidence"]["notes"] == "Hotovo."


def test_unknown_step_is_422():
    with pytest.raises(InvalidPayload) as error:
        rules.step_results(body(steps=[{"stepId": "s9", "status": "done"}]), [], PINNED)
    assert error.value.field == "steps[].stepId"


def test_self_checks_need_a_full_head_and_match_the_validator():
    from backend.canvas.opora_review_self_checks import validate_self_checks

    checks = body(checks=[{"name": "npm test", "status": "green", "output": "ok"},
                          {"name": "npm run build", "status": "red"}])["checks"]
    assert rules.self_checks(checks, None) is None and rules.self_checks(checks, "abc1234") is None
    value = rules.self_checks(checks, "c" * 40)
    assert validate_self_checks(value)["checks"][1]["status"] == "failed"
    assert [item["name"] for item in value["checks"]] == ["npm-test", "npm-run-build"]


def test_red_check_run_is_written_last():
    checks = [{"name": "a", "status": "red"}, {"name": "b", "status": "green"}]
    assert [item["name"] for item in rules.check_runs(checks)] == ["b", "a"]


def test_card_commits_pair_by_trailer(tmp_path):
    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, text=True).stdout

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    for name, message in (("a.txt", ["Cizí práce"]), ("b.txt", ["Modul karty", "Opora-Node: n1"])):
        (tmp_path / name).write_text(name, "utf-8")
        git("add", ".")
        git("commit", "-q", *[part for text in message for part in ("-m", text)])
    found = rules.card_commits(str(tmp_path), "n1", [{"id": "n1", "parentId": None, "kind": "node"}])
    assert [item["subject"] for item in found] == ["Modul karty"]
    assert rules.card_commits(None, "n1", []) == []
