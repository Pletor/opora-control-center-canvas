"""Merge-queue semantics and PR template: ready only on the current base head with required checks passed."""
import tomllib

import pytest

from backend.canvas.opora_review_risk import DEFAULT_PATH, parse
from backend.canvas.opora_review_template import filled_sections, missing_sections
from backend.canvas.test_opora_execution_pull_requests import NEXT_SHA, SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import (
    BASE_TIP,
    BaseReader,
    agent_state,
    config,
    evidence,
    gate_item,
    run_round,
    use,
)
from backend.canvas.test_opora_review_jobs import push
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401

QUEUE = config(merge_queue={"required_checks": ["tests"], "base_max_age_seconds": 600,
                            "observe_interval_seconds": 60})
TEMPLATE = config(template={"sections": ["Testing", "Risk", "Revert plan"]})


def reasons(review):  # noqa: F811
    return gate_item(review)["reviewGate"]["reasons"]


def test_ready_only_with_required_checks_on_a_head_based_on_the_current_base(review):  # noqa: F811
    reader = BaseReader()
    use(review, QUEUE, reader)
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    assert reader.calls == [("owner/repo", 7, SHA)]
    assert reasons(review) == ["required_checks_pending"]
    evidence(review, SHA, [("tests", "failure")])
    assert gate_item(review)["reviewGate"]["status"] == "blocked" and reasons(review) == ["required_checks_failed"]
    evidence(review, SHA, [("tests", "success"), ("lint", "failure")], minute=1)  # not required: ignored
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "ready" and item["mergeReadiness"]["requiredChecks"] == {"tests": "passed"}
    base = {key: value for key, value in item["mergeReadiness"]["base"].items() if key != "observedAt"}
    assert base == {"baseRef": "main", "baseSha": BASE_TIP, "mergeBaseSha": BASE_TIP, "behindBy": 0, "fresh": True}


def test_head_behind_the_current_base_is_stale_against_main_with_update_branch_action(review):  # noqa: F811
    reader = BaseReader()
    use(review, QUEUE, reader)
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    evidence(review, SHA, [("tests", "success")])
    assert gate_item(review)["reviewGate"]["status"] == "ready"
    # Main moved: checks passed on a commit whose base is no longer the base branch head.
    reader.behind = 3
    review["clock"].now += 61
    review["jobs"].sync(**review["scope"])
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "pending" and item["reviewGate"]["reasons"] == ["stale_against_main"]
    state = agent_state(review)
    assert next(value for value in state["stages"] if value["id"] == "review")["reason"] == "stale_against_main"
    [action] = [value for value in state["actions"] if value["verb"] == "pr.update_branch"]
    assert action["status"] == "ready" and action["path"] == "github:/repos/owner/repo/pulls/7/update-branch"
    assert action["preconditions"] == {"repository": "owner/repo", "number": 7, "expectedHeadSha": SHA,
                                       "baseRef": "main", "baseSha": BASE_TIP}
    # agent-office PR upkeep rebases: new head, fresh base, checks re-run.
    reader.behind = 0
    push(review, NEXT_SHA, "rebase")
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    evidence(review, NEXT_SHA, [("tests", "success")], minute=5)
    assert gate_item(review)["reviewGate"]["reasons"] == []
    assert not [value for value in agent_state(review)["actions"] if value["verb"] == "pr.update_branch"]


def test_observations_are_throttled_and_age_out_fail_closed(review):  # noqa: F811
    reader = BaseReader()
    use(review, QUEUE, reader)
    review["jobs"].sync(**review["scope"])
    review["jobs"].sync(**review["scope"])
    assert len(reader.calls) == 1  # within observe_interval_seconds
    review["clock"].now += 601
    assert "base_freshness_unobserved" in reasons(review)  # older than base_max_age_seconds
    review["jobs"].sync(**review["scope"])
    assert len(reader.calls) == 2 and "base_freshness_unobserved" not in reasons(review)
    reader.complete = False
    review["clock"].now += 61
    review["jobs"].sync(**review["scope"])
    assert "base_freshness_unobserved" in reasons(review)


def test_template_sections_are_parsed_deterministically():
    body = ("## Summary\nx\n## Testing\n<!-- hint -->\n- [ ]\n\n## Risk\nlow\n"
            "### revert   PLAN\n`git revert abc`\n")
    assert filled_sections(body) == ["summary", "risk", "revert plan"]
    assert missing_sections(filled_sections(body), ["Testing", "Risk", "Revert plan"]) == ["Testing"]
    assert filled_sections(None) == [] and filled_sections("no headings") == []


def test_incomplete_template_waits_but_never_blocks(review):  # noqa: F811
    reader = BaseReader(sections=["testing", "risk"])
    use(review, TEMPLATE, reader)
    review["jobs"].sync(**review["scope"])
    run_round(review, {})
    item = gate_item(review)
    assert item["reviewGate"]["status"] == "pending" and item["reviewGate"]["reasons"] == ["template_incomplete"]
    assert item["mergeReadiness"]["template"] == {"missing": ["Revert plan"]}
    reader.sections.append("revert plan")  # PR body edited; the next observation sees it
    review["clock"].now += 61
    review["jobs"].sync(**review["scope"])
    assert gate_item(review)["reviewGate"]["status"] == "ready"


def test_shipped_config_switches_every_gate_rule_on_and_bad_values_fail():
    with open(DEFAULT_PATH, "rb") as handle:
        shipped = parse(tomllib.load(handle))
    assert shipped["security"]["enabled"] and shipped["security"]["minTier"] == "medium"
    assert shipped["selfChecks"]["required"] == ["tests", "build"]
    assert shipped["mergeQueue"]["enabled"] and shipped["template"]["sections"] == ["Testing", "Risk", "Revert plan"]
    off = parse({})
    assert not off["security"]["enabled"] and not off["mergeQueue"]["enabled"] and off["selfChecks"]["required"] == []
    for bad in ({"security": {"min_tier": "extreme"}}, {"self_checks": {"required": ["Tests"]}},
                {"self_checks": {"required": ["tests", "tests"]}}, {"merge_queue": {"base_max_age_seconds": 0}},
                {"template": {"sections": ["# heading"]}}):
        with pytest.raises(ValueError):
            parse(bad)
