"""Known regressions suppress reuse only through an exact merged-run association."""
import json

import pytest

from backend.canvas.test_opora_changesets import accept
from backend.canvas.test_opora_execution_context import claimed
from backend.library.harness_learning_rates import read
from backend.library.test_harness_kit import kit, propose_kit
from backend.library.test_harness_learning import merged_link
from database.repositories.opora_review_insights import ReviewInsights


def cases(world, **overrides):
    db = world[0].db_for("draft")
    content = {"headSha": "a" * 40, "mergeSha": "b" * 40, "revertNumber": 8, "revertSha": "c" * 40}
    content.update(overrides)
    store = ReviewInsights(db, "draft")
    db.execute("BEGIN IMMEDIATE")
    store.insert_incident("draft", "incident1", "owner/repo", 7, "https://incident/1", "Regression", "agent:fixture", "now")
    store.insert_revert("owner/repo", 7, 8, "c" * 40, "now")
    store.insert_case("draft", "case1", "owner/repo", 7, "incident", "incident1", content, "now")
    store.insert_case("draft", "case2", "owner/repo", 7, "revert", "#8", content, "now")
    db.commit()


def rows(world, **filters):
    return read(world[0].db_for("draft"), "draft", "draft", **filters)["cohorts"]


def test_guardrails_count_runs_once_and_never_assert_success_or_causality(learning_run):
    assert rows(learning_run)[0]["guardrails"]["affectedExecutions"] == 0
    merged_link(learning_run)
    cases(learning_run)
    guard = rows(learning_run)[0]["guardrails"]
    assert guard == {"source": "native-review-eval-cases", "affectedExecutions": 1,
                     "incidentReportExecutions": 1, "revertedExecutions": 1,
                     "productionExposure": "unknown", "causalAttribution": False}
    assert rows(learning_run)[0]["rate"]["unknown"] == 1, "negative reports never fabricate a verified failure"
    assert rows(learning_run, node="foreign") == []
    assert rows(learning_run, resource="foreign") == []
    assert read(learning_run[0].db_for("draft"), "draft", "foreign")["cohorts"] == []


@pytest.mark.parametrize("column,value", [("head_sha", "d" * 40), ("merge_sha", "d" * 40),
    ("accepted_revision", "foreign"), ("node_id", "foreign"), ("repository", "foreign/repo"),
    ("number", 999), ("workspace_id", "foreign"), ("state", "open")])
def test_mismatched_merged_run_cannot_flag_a_tool(learning_run, column, value):
    merged_link(learning_run)
    cases(learning_run)
    db = learning_run[0].db_for("draft")
    db.execute(f"UPDATE opora_execution_pull_requests SET {column}=?", (value,))
    assert rows(learning_run)[0]["guardrails"]["affectedExecutions"] == 0


def test_cases_need_their_own_native_source_and_immutable_head(learning_run):
    merged_link(learning_run)
    cases(learning_run, headSha="different")
    db = learning_run[0].db_for("draft")
    assert rows(learning_run)[0]["guardrails"]["affectedExecutions"] == 0
    db.execute("UPDATE opora_review_eval_cases SET content=?", (json.dumps({"headSha": "a" * 40, "mergeSha": "b" * 40}),))
    db.execute("DELETE FROM opora_review_incidents")
    assert rows(learning_run)[0]["guardrails"]["affectedExecutions"] == 0


def test_same_text_in_a_new_requirement_configuration_does_not_inherit_a_regression(learning_run, learning_plan):
    merged_link(learning_run)
    cases(learning_run)
    _, authority, _, record = learning_run
    authority.release(record["executionId"], {"project": "draft", "workspace": "draft", "token": record["token"], "epoch": record["epoch"]})
    updated = kit()
    updated["resources"][0]["requires"] = ["command:other"]
    proposal, head = propose_kit(learning_plan, updated, {"steps": record["assignment"]["steps"]})
    accept(learning_run[0], proposal, head)
    claimed(learning_plan, request="new-guardrail-config")
    versions = {row["versionDigest"]: row["guardrails"]["affectedExecutions"] for row in rows(learning_run)}
    assert len(versions) == 2 and sorted(versions.values()) == [0, 1]
