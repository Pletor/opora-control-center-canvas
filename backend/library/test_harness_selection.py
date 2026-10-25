"""Native acceptance pins selection claims without treating them as attestations."""
import copy

import pytest

from backend.canvas.test_opora_changesets import SCOPE, accept
from backend.canvas.test_opora_execution_context import claimed, prepared
from backend.library.harness_kit import kit_of_assignment, validate_kit
from backend.library.harness_learning_rates import read
from backend.library.harness_recovery import HarnessRecovery
from backend.library.harness_selection import version_digest
from backend.library.test_harness_kit import kit, propose_kit


def selected(content="Run the repository checks before reporting completion."):
    value = kit(content)
    value["schema"] = "harness.kit/2"
    resource = value["resources"][0]
    value["selection"] = {"schema": "harness.selection/1", "policy": "harness.recommendation/1",
        "problem": value["problems"][0], "profileRevision": 3, "declaredCapabilities": ["command:npm"],
        "evidence": "caller-declared-selection", "entries": [{"resource": resource["resource"],
            "digest": resource["digest"], "versionDigest": version_digest(resource), "order": 0,
            "reason": "explicit-assignment", "assignments": [{"slot": "work", "scope": "task",
                "node": "opora:project:workspace:card"}]}]}
    return value


def test_v1_stays_strict_and_v2_roundtrips_without_rewriting_claims():
    legacy, value = kit(), selected()
    before = copy.deepcopy(value)
    validate_kit(legacy)
    validate_kit(value)
    assert value == before
    with pytest.raises(ValueError):
        validate_kit({**legacy, "selection": value["selection"]})
    for schema in ([], {}, "harness.kit/3", None):
        with pytest.raises(ValueError):
            validate_kit({**legacy, "schema": schema})


@pytest.mark.parametrize("scope", ["global", "repository", "page", "layer", "area", "sector", "task"])
def test_all_hierarchy_origin_levels_are_preserved(scope):
    candidate = selected()
    origin = candidate["selection"]["entries"][0]["assignments"][0]
    origin.update(scope=scope, node=None if scope in {"global", "repository"} else "opora:p:w:n")
    before = copy.deepcopy(candidate)
    validate_kit(candidate)
    assert candidate == before


def test_version_digest_matches_existing_office_cross_language_vector():
    assert version_digest({"resource": "rule:quality", "category": "rules", "digest": "b" * 64,
        "requires": ["command:npm"]}) == "a8d79673974d61c7c701b7018a1f6e386048ad786c2ff6a14d449b4ab5313ba9"


def test_integral_json_numbers_match_office_without_normalizing_accepted_value():
    candidate = selected()
    candidate["selection"]["profileRevision"] = 3.0
    candidate["selection"]["entries"][0]["order"] = 0.0
    validate_kit(candidate)
    assert type(candidate["selection"]["profileRevision"]) is float
    assert type(candidate["selection"]["entries"][0]["order"]) is float
    for invalid in (True, .5, -1, 2**53, 10**1000, float("inf"), float("nan")):
        candidate["selection"]["profileRevision"] = invalid
        with pytest.raises(ValueError):
            validate_kit(candidate)


@pytest.mark.parametrize("key,value", [("evidence", "independently-verified"), ("policy", "unknown"),
    ("schema", "harness.selection/2"), ("problem", "other.problem"), ("profileRevision", True),
    ("profileRevision", -1), ("profileRevision", 2**53), ("profileRevision", None),
    ("declaredCapabilities", ["command:npm", "command:npm"]), ("declaredCapabilities", [{}]),
    ("entries", []), ("permissionGranted", True)])
def test_rejects_invalid_selection_metadata(key, value):
    candidate = selected()
    candidate["selection"][key] = value
    with pytest.raises(ValueError):
        validate_kit(candidate)


@pytest.mark.parametrize("key,value", [("resource", "foreign"), ("digest", "0" * 64),
    ("versionDigest", "0" * 64), ("order", 1), ("order", False), ("reason", "invented"),
    ("reason", "native-stable"), ("reason", []), ("assignments", []), ("verified", True)])
def test_rejects_wrong_version_order_reason_and_claimed_authority(key, value):
    candidate = selected()
    candidate["selection"]["entries"][0][key] = value
    with pytest.raises(ValueError):
        validate_kit(candidate)


@pytest.mark.parametrize("origin", [{"slot": "work", "scope": "global", "node": "foreign"},
    {"slot": "work", "scope": "root", "node": None}, {"slot": "work", "scope": [], "node": None},
    {"slot": "work\n", "scope": "task", "node": None}, {"slot": "work", "scope": "task", "node": "bad\n"},
    {"slot": "work", "scope": "task"}])
def test_rejects_invalid_origin(origin):
    candidate = selected()
    candidate["selection"]["entries"][0]["assignments"] = [origin]
    with pytest.raises(ValueError):
        validate_kit(candidate)


def test_version_metadata_changes_and_total_budget_cannot_reuse_old_provenance():
    candidate = selected()
    candidate["resources"][0]["requires"] = ["command:other"]
    with pytest.raises(ValueError, match="version"):
        validate_kit(candidate)
    candidate = selected("x" * (96 * 1024 - 400))
    with pytest.raises(ValueError, match="96 KiB"):
        validate_kit(candidate)
    candidate = selected()
    origins = candidate["selection"]["entries"][0]["assignments"]
    origins.append(copy.deepcopy(origins[0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate_kit(candidate)


def test_native_acceptance_context_and_learning_preserve_v2_without_verification(sparse):
    graphs, authority, refs = sparse
    value = selected()
    proposal, head = propose_kit(sparse, value)
    accept(graphs.service, proposal, head)
    current = claimed(sparse)
    assert kit_of_assignment(current["assignment"], refs["a"]) == value
    rows = read(graphs.service.db_for("draft"), "draft", "draft")["cohorts"]
    assert rows and all(row["rate"]["pass"] == 0 for row in rows)
    assert all(row["rate"]["unknown"] == 1 for row in rows)
    authority.release(current["executionId"], {**SCOPE, "token": current["token"], "epoch": current["epoch"]})
    before = prepared(sparse)
    revised = copy.deepcopy(value)
    revised["selection"]["profileRevision"] += 1
    proposal, head = propose_kit(sparse, revised)
    accept(graphs.service, proposal, head)
    after = prepared(sparse)
    assert before["contextVersion"] != after["contextVersion"]
    second = claimed(sparse, request="new-provenance")
    assert current["assignmentDigest"] != second["assignmentDigest"]
    assert kit_of_assignment(current["assignment"], refs["a"]) == value
    assert kit_of_assignment(second["assignment"], refs["a"]) == revised


def test_v2_recovery_removes_stale_claims_only_from_new_v1_proposal(learning_plan):
    graphs, authority, refs = learning_plan
    old = claimed(learning_plan)
    authority.release(old["executionId"], {**SCOPE, "token": old["token"], "epoch": old["epoch"]})
    value = selected("New candidate content")
    proposal, head = propose_kit(learning_plan, value, {"steps": old["assignment"]["steps"]})
    accept(graphs.service, proposal, head)
    current = claimed(learning_plan, request="v2-current")
    response = HarnessRecovery(graphs.service).preview({**SCOPE, "executionId": current["executionId"],
        "token": current["token"], "epoch": current["epoch"], "sourceExecutionId": old["executionId"],
        "resource": "rule:quality"})
    assert response["kit"] == kit_of_assignment(old["assignment"], refs["a"])
    assert "selection" not in response["kit"] and response["requiresAcceptance"] is True
    assert kit_of_assignment(current["assignment"], refs["a"]) == value
