"""Agent-state document: stable shape, deterministic ids and every documented health rule."""
import json
import time

import pytest

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_agent_state_rules import ACCEPTANCE_WAIT_SECONDS, STAGES
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import SCOPE, accept, baseline, legacy_save, propose
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_execution_budgets import configure, v2
from backend.canvas.test_opora_executions import claim, credentials
from backend.canvas.test_opora_process_sync import route


@pytest.fixture(autouse=True)
def no_pull_module():
    pulls.register(None)
    original = pulls.source
    pulls.source = lambda: pulls._override  # The real link module must not leak into these tests.
    yield
    pulls.source = original
    pulls.register(None)


def read(service, offset=0.0):
    return AgentState(service, clock=lambda: time.time() + offset).read(**SCOPE)


def stage(document, name):
    return next(item for item in document["stages"] if item["id"] == name)


def verbs(document, verb):
    return [item for item in document["actions"] if item["verb"] == verb]


@pytest.fixture
def planned(service):
    legacy_save(service, goal="Read accepted task")
    baseline(service)
    return ExecutionResults(service)


def test_shape_snapshot_and_stage_order(service):
    document = read(service)
    assert list(document) == ["schemaVersion", "generatedAt", "projectId", "workspaceId", "heads", "stages",
                              "riskMix", "decisions", "actions", "gaps", "cards", "truncated", "cardsTotal",
                              "cardsNextOffset", "eventsCursor", "mapGaps", "mapGapsTotal", "guards", "autonomy"]
    assert document["autonomy"] == {"full": False}
    assert document["schemaVersion"] == 1 and document["projectId"] == "draft" and document["workspaceId"] == "draft"
    assert list(document["heads"]) == ["acceptedHead", "acceptedRevision", "graphDigest", "workingDiffers",
                                       "contextVersion", "budgetPolicyHead"]
    assert [item["id"] for item in document["stages"]] == list(STAGES)
    assert all(list(item) == ["id", "count", "health", "reason"] for item in document["stages"])
    assert all(item["health"] in {"ok", "waiting", "blocking", "not_connected"} for item in document["stages"])
    assert document["riskMix"] == {"low": 0, "elevated": 0, "critical": 0}
    assert [item["id"] for item in document["gaps"]] == ["ai_review", "lean_verification", "pull_request_link"]


def test_empty_project_is_waiting_without_actions(tmp_path):
    instance = CanvasService(tmp_path / "data")
    try:
        document = AgentState(instance).read(**SCOPE)
    finally:
        instance.close()
    assert stage(document, "plan") == {"id": "plan", "count": 0, "health": "waiting", "reason": "empty_plan"}
    assert document["heads"]["acceptedHead"] is None
    assert document["actions"] == [] and document["decisions"] == []


def test_missing_baseline_blocks_plan_and_is_a_human_only_decision(service):
    legacy_save(service)
    document = read(service)
    assert stage(document, "plan")["health"] == "blocking"
    assert stage(document, "acceptance")["reason"] == "baseline_awaiting_human"
    [action] = verbs(document, "accept_baseline")
    assert action["status"] == "blocked" and action["blockReason"] == "human_only"
    assert action["preconditions"]["expectedGraphDigest"] == document["heads"]["graphDigest"]
    assert document["decisions"][0]["kind"] == "accept_baseline"
    assert document["decisions"][0]["actionId"] == action["id"]


def test_accept_is_human_only_and_overdue_proposal_waits(planned, service):
    proposal = propose(service)
    fresh = read(service)
    assert stage(fresh, "acceptance") == {"id": "acceptance", "count": 1, "health": "ok",
                                          "reason": "awaiting_human_within_window"}
    [action] = verbs(fresh, "accept")
    assert action["targetId"] == proposal["id"] and action["status"] == "blocked"
    assert action["blockReason"] == "human_only"
    assert action["preconditions"] == {"expectedAcceptedHead": fresh["heads"]["acceptedHead"]}
    assert fresh["riskMix"] == {"low": 0, "elevated": 1, "critical": 0}
    assert fresh["decisions"][0]["kind"] == "accept_elevated"
    late = read(service, ACCEPTANCE_WAIT_SECONDS + 60)
    assert stage(late, "acceptance")["health"] == "waiting" and stage(late, "acceptance")["reason"] == "acceptance_overdue"


def test_stale_proposal_waits_and_offers_ready_rebase(planned, service):
    head = read(service)["heads"]["acceptedHead"]
    first, second = propose(service), propose(service, ("b",), "Other goal")
    accept(service, first, head)
    document = read(service)
    assert stage(document, "proposal") == {"id": "proposal", "count": 1, "health": "waiting", "reason": "stale_proposals"}
    [rebase] = verbs(document, "rebase")
    assert rebase["targetId"] == second["id"] and rebase["status"] == "ready"
    assert rebase["path"] == f"/api/oporahub/changesets/{second['id']}/rebase"
    assert not verbs(document, "accept")


def test_action_ids_are_deterministic_and_change_with_the_head(planned, service):
    head = read(service)["heads"]["acceptedHead"]
    first, _ = propose(service), propose(service, ("b",), "Other goal")
    one, two = read(service), read(service, 5)
    assert [item["id"] for item in one["actions"]] == [item["id"] for item in two["actions"]]
    assert one["decisions"] == two["decisions"]
    assert [(item["verb"], item["targetId"]) for item in one["actions"]] == sorted(
        (item["verb"], item["targetId"]) for item in one["actions"])
    before = {item["targetId"]: item["id"] for item in one["actions"]}
    accept(service, first, head)
    after = {item["targetId"]: item["id"] for item in read(service)["actions"]}
    assert not set(before.values()) & set(after.values())


def test_ready_claim_echoes_exact_execution_context(planned, service):
    route(service)
    document = read(service)
    [action] = verbs(document, "claim")
    context = planned.context(**SCOPE, node="a")
    assert action["status"] == "ready" and action["targetId"] == "a"
    assert action["preconditions"] == {"expectedAcceptedHead": context["acceptedHead"],
                                       "expectedContextVersion": context["contextVersion"]}
    assert stage(document, "claim") == {"id": "claim", "count": 1, "health": "ok", "reason": "cards_ready"}


def test_exhausted_budget_blocks_claim(planned, service):
    configure(planned, limits={"maxRunSeconds": 60, "maxAttempts": 1, "maxRepairRounds": 0})
    first = v2(planned)
    planned.release(first["executionId"], credentials(first))
    document = read(service)
    assert stage(document, "claim")["health"] == "blocking" and stage(document, "claim")["reason"] == "budget_exhausted"
    [action] = verbs(document, "claim")
    assert action["status"] == "blocked" and action["blockReason"] == "budget_exhausted"
    assert action["budget"] == {"remainingAttempts": 0, "remainingRepairRounds": 0}
    assert document["heads"]["budgetPolicyHead"] == {"a": action["preconditions"]["expectedBudgetPolicyHead"]}


def test_lease_past_deadline_blocks_work(planned, service):
    claim(planned)
    assert stage(read(service), "work") == {"id": "work", "count": 1, "health": "ok", "reason": "runs_active"}
    late = stage(read(service, 120), "work")
    assert late == {"id": "work", "count": 0, "health": "blocking", "reason": "lease_past_deadline"}


def test_reported_result_needs_human_review_and_pr_link_is_not_connected(planned, service):
    record = claim(planned)
    planned.submit(record["executionId"], {**credentials(record), "requestId": "r", "result": {"summary": "done"}})
    document = read(service)
    assert stage(document, "evidence")["count"] == 1 and stage(document, "evidence")["health"] == "ok"
    assert stage(document, "review") == {"id": "review", "count": 1, "health": "waiting", "reason": "human_review_required"}
    assert all(stage(document, name)["health"] == "not_connected" for name in ("pull_request", "merge", "plan_writeback"))
    [review] = verbs(document, "review")
    assert review["blockReason"] == "human_only" and review["targetId"] == record["executionId"]
    [link] = verbs(document, "link_pull_request")
    assert link["status"] == "blocked" and link["blockReason"] == "not_implemented"
    assert record["token"] not in json.dumps(document)


def test_pull_request_seam_drives_pr_merge_and_writeback(planned, service):
    record = claim(planned)
    planned.submit(record["executionId"], {**credentials(record), "requestId": "r", "result": {"summary": "done"}})
    pulls.register(lambda project, workspace: [])
    document = read(service)
    assert stage(document, "pull_request")["reason"] == "results_without_pull_request"
    assert stage(document, "pull_request")["health"] == "blocking"
    assert verbs(document, "link_pull_request")[0]["status"] == "ready"
    assert "pull_request_link" not in [item["id"] for item in document["gaps"]]
    pulls.register(lambda canvas, project, workspace: {"items": [{"executionId": record["executionId"], "state": "open"}]})
    document = read(service)
    assert stage(document, "pull_request")["health"] == "ok" and not verbs(document, "link_pull_request")
    assert stage(document, "merge")["reason"] == "pull_requests_open"
    pulls.register(lambda p, w: [{"executionId": record["executionId"], "state": "merged", "planWrittenBack": False}])
    assert stage(read(service), "plan_writeback")["reason"] == "merged_without_plan_writeback"
    pulls.register(lambda p, w: [{"executionId": record["executionId"], "state": "merged"}])
    assert stage(read(service), "plan_writeback")["health"] == "not_connected"
    pulls.register(lambda p, w: [{"executionId": record["executionId"], "state": "merged", "planWrittenBack": True}])
    assert stage(read(service), "plan_writeback") == {"id": "plan_writeback", "count": 1, "health": "ok",
                                                     "reason": "plan_written_back"}


def test_read_has_no_sql_writes(planned, service):
    propose(service)
    db = service.db_for("draft")
    sql = []
    db.set_trace_callback(sql.append)
    try:
        read(service)
    finally:
        db.set_trace_callback(None)
    assert not any(command.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "BEGIN", "CREATE")) for command in sql)


def test_action_priority_is_one_list_matching_the_documented_table():
    import re
    from pathlib import Path

    from backend.canvas import opora_agent_state_rules as rules
    doc = (Path(__file__).resolve().parents[2] / "docs" / "oporahub-agent-state.md").read_text(encoding="utf-8")
    section = doc.split("## Rozhodnutí a akce", 1)[1].split("\n## ", 1)[0]
    verbs = re.findall(r"^\| `([a-z_.]+)` \|", section, flags=re.MULTILINE)
    assert tuple(verb for verb in verbs if verb != "verb") == rules.VERB_ORDER
    shuffled = [{"verb": verb, "targetId": target} for verb in reversed(rules.VERB_ORDER) for target in ("b", "a")]
    assert [(item["verb"], item["targetId"]) for item in rules.ordered(shuffled)] == [
        (verb, target) for verb in rules.VERB_ORDER for target in ("a", "b")]
