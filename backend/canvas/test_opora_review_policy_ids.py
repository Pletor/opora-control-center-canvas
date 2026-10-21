"""Unrepresentable provider IDs cannot support policy approval or check success."""
import pytest

from backend.canvas.opora_review_policy_ids import safe_id
from backend.canvas.test_opora_review_policy_evaluator import evaluate
from backend.canvas.test_opora_review_policy_evaluator import (
    inputs as inputs,  # noqa: PLC0414 - shared pytest fixture
)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, "1", None, 9007199254740992])
def test_unsafe_identity_rejected(value):
    assert not safe_id(value)


def test_maximum_safe_integer_is_valid():
    assert safe_id(9007199254740991)


@pytest.mark.parametrize("value", [True, 9007199254740992])
@pytest.mark.parametrize("location,key", [
    ("pr", "id"), ("pr", "headRepoId"), ("pr", "authorId"), ("repository", "id"),
    ("reviews", "id"), ("reviews", "userId"), ("checks", "id"), ("checks", "appId"),
])
def test_all_provider_identities_fail_closed(inputs, location, key, value):
    record = inputs[1][location]
    if isinstance(record, list):
        record = record[0]
    record[key] = value
    result = evaluate(inputs)
    assert result["status"] != "satisfied"
    if location == "checks":
        assert not result["checks"]["policyVerified"]


@pytest.mark.parametrize("value", [True, 9007199254740992])
def test_attempt_sequence_cannot_pass_by_matching_unsafe_numbers(inputs, value):
    inputs[1]["attemptSequence"] = inputs[2]["sequence"] = value
    result = evaluate(inputs)
    assert result["status"] == "unknown"
    assert not result["checks"]["policyVerified"]
