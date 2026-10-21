"""Pre-PR self-check evidence: deterministic shape validation and the gate rule for the current head."""
import pytest

from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_review_self_checks import SelfCheckAddenda, evaluate, validate_self_checks
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import (
    agent_state,
    config,
    gate_item,
    run_round,
    use,
)
from backend.canvas.test_opora_review_jobs import push
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401

REQUIRED = config(self_checks={"required": ["tests", "build"]})


def ran(name, code=0, **extra):
    return {"name": name, "command": f"run {name}", "exitCode": code, "status": "passed" if code == 0 else "failed",
            **extra}


def evidence(head=SHA, *checks):
    return {"headSha": head, "checks": list(checks) or [ran("tests"), ran("build")]}


def test_valid_evidence_is_normalized():
    value = validate_self_checks(evidence(SHA, ran("tests", summary="12 passed", output="ok", durationSeconds=3.5),
                                          {"name": "lint", "command": "ruff", "exitCode": None, "status": "skipped"}))
    assert value["checks"][0] == {"name": "tests", "command": "run tests", "exitCode": 0, "status": "passed",
                                  "summary": "12 passed", "output": "ok", "durationSeconds": 3.5}
    assert value["checks"][1]["status"] == "skipped" and value["checks"][1]["summary"] is None


@pytest.mark.parametrize("value", [
    None, {}, {"headSha": SHA}, {"headSha": SHA, "checks": [], "extra": 1},
    evidence("C" * 40), evidence("c" * 39), {"headSha": SHA, "checks": []},
    evidence(SHA, {**ran("tests"), "status": "failed"}),          # status must match the exit code
    evidence(SHA, {**ran("tests", 2), "status": "passed"}),
    evidence(SHA, {**ran("tests"), "exitCode": True}),
    evidence(SHA, {"name": "tests", "command": "x", "exitCode": 0, "status": "skipped"}),
    evidence(SHA, ran("Tests")), evidence(SHA, ran("tests"), ran("tests")),
    evidence(SHA, {**ran("tests"), "unknown": 1}), evidence(SHA, {**ran("tests"), "command": " "}),
    evidence(SHA, ran("tests", output="x" * 4001)), evidence(SHA, *[ran(f"c{index}") for index in range(31)]),
])
def test_invalid_evidence_is_rejected(value):
    with pytest.raises(ValueError):
        validate_self_checks(value)


def test_evaluation_needs_every_required_check_passed_on_exactly_this_head():
    required = ["tests", "build"]
    assert evaluate([], SHA, [])["status"] == "off"
    assert evaluate([], SHA, required) == {"status": "missing", "source": None, "missing": required, "failed": [],
                                           "invalid": 0}
    assert evaluate([("result", evidence(NEXT_SHA))], SHA, required)["status"] == "missing"
    assert evaluate([("result", evidence())], SHA, required)["status"] == "ok"
    partial = evaluate([("result", evidence(SHA, ran("tests")))], SHA, required)
    assert (partial["status"], partial["missing"]) == ("missing", ["build"])
    failed = evaluate([("result", evidence(SHA, ran("tests", 1), ran("build")))], SHA, required)
    assert (failed["status"], failed["failed"]) == ("failed", ["tests"])
    newest = evaluate([("result", evidence(SHA, ran("tests", 1), ran("build"))), ("addendum", evidence()),
                       ("addendum", {"headSha": SHA})], SHA, required)
    assert (newest["status"], newest["source"], newest["invalid"]) == ("ok", "addendum", 1)


def report(review, self_checks):  # noqa: F811
    record = review["record"]
    return ExecutionResults(review["service"]).submit(record["executionId"], {
        **review["scope"], "token": record["token"], "epoch": record["epoch"], "requestId": "result",
        "result": {"summary": "Done.", "selfChecks": self_checks}})


def test_gate_reads_the_execution_result_then_per_head_addenda(review):  # noqa: F811
    use(review, REQUIRED)
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "pending" and item["reviewGate"]["reasons"] == ["self_checks_missing"]
    stage = next(value for value in agent_state(review)["stages"] if value["id"] == "review")
    assert stage["reason"] == "self_checks_missing"
    [action] = [value for value in agent_state(review)["actions"] if value["verb"] == "review.self_checks"]
    assert action["preconditions"] == {"executionId": review["record"]["executionId"], "headSha": SHA,
                                       "required": ["tests", "build"]}
    report(review, evidence())
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "ready" and item["mergeReadiness"]["selfChecks"]["source"] == "result"
    # Review fixes move the head: the result's evidence no longer counts, an addendum for the new head does.
    push(review, NEXT_SHA, "push")
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    assert gate_item(review)["reviewGate"]["reasons"] == ["self_checks_missing"]
    addenda = SelfCheckAddenda(review["jobs"])
    payload = {**review["scope"], "executionId": review["record"]["executionId"]}
    with pytest.raises(ValueError, match="current head"):
        addenda.submit({**payload, "selfChecks": evidence(SHA)}, "agent:w")
    receipt = addenda.submit({**payload, "selfChecks": evidence(NEXT_SHA)}, "agent:w")
    assert receipt["status"]["status"] == "ok"
    assert addenda.submit({**payload, "selfChecks": evidence(NEXT_SHA)}, "agent:w") == receipt  # idempotent
    with pytest.raises(ValueError, match="different content"):
        addenda.submit({**payload, "selfChecks": evidence(NEXT_SHA, ran("tests", 1), ran("build"))}, "agent:w")
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "ready" and item["mergeReadiness"]["selfChecks"]["source"] == "addendum"


def test_failed_required_self_check_blocks(review):  # noqa: F811
    use(review, REQUIRED)
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    report(review, evidence(SHA, ran("tests", 1), ran("build")))
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "blocked" and item["reviewGate"]["reasons"] == ["self_checks_failed"]
    assert next(value for value in agent_state(review)["stages"] if value["id"] == "review")["reason"] == \
        "self_checks_failed"


def test_invalid_result_evidence_never_counts(review):  # noqa: F811
    use(review, REQUIRED)
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    report(review, {"headSha": SHA, "checks": [{"name": "tests", "status": "passed"}]})
    readiness = gate_item(review)["mergeReadiness"]["selfChecks"]
    assert (readiness["status"], readiness["invalid"]) == ("missing", 1)
