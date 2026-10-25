import copy
import hashlib
import uuid

import pytest

from backend.library.harness_invocations import validate_invocations


CONTENT = "console.log('safe')\n"
RESOURCE = "script:build"
DIGEST = hashlib.sha256(CONTENT.encode()).hexdigest()


def fixture():
    record = {"contextProtocolVersion": 2, "executionId": "exec-1", "epoch": 4,
              "project": "project-1", "workspace": "draft", "nodeId": "node-1",
              "acceptedRevision": "rev-7", "assignmentDigest": "a" * 64}
    record["assignment"] = {"documents": [{"nodeId": "node-1", "fields": {"harness": {
        "schema": "harness.kit/1", "problems": ["build"], "resources": [{
            "slot": "build", "resource": RESOURCE, "category": "scripts", "digest": DIGEST,
            "content": CONTENT, "requires": ["command:node"]}]}}}]}
    observation = {"schema": "harness.invocation-metadata/1", "invocationId": str(uuid.uuid4()),
                  "execution": {key: record[key] for key in (
                      "executionId", "epoch", "project", "workspace", "nodeId", "acceptedRevision", "assignmentDigest")},
                  "resource": {"id": RESOURCE, "digest": DIGEST}, "adapter": "node-readonly/1",
                  "nodeVersion": "v22.1.0", "exitCode": 0, "reason": "completed", "durationMs": 12.5,
                  "outputBytes": 5, "outcome": "pass", "authorityCurrentAtCompletion": True,
                  "cleanupComplete": True, "evidence": "worker-observed", "independentlyVerified": False,
                  "causalContribution": False, "promotionAllowed": False, "tokens": None, "cost": None}
    return record, observation


def test_empty_and_legacy_absence():
    record, _ = fixture()
    assert validate_invocations({}, record) == []
    assert validate_invocations({"harnessInvocations": []}, record) == []
    assert validate_invocations({"summary": "legacy", "stdout": "old output", "args": ["--x"]}, record) == []


def test_valid_exact_observation_is_returned():
    record, item = fixture()
    assert validate_invocations({"harnessInvocations": [item]}, record) == [item]


@pytest.mark.parametrize("change", [
    lambda i: i["execution"].update(executionId="other"),
    lambda i: i["execution"].update(epoch=True),
    lambda i: i["resource"].update(digest="0" * 64),
    lambda i: i.update(stdout="raw output"),
    lambda i: i.update(args=["--raw"]),
    lambda i: i.update(token="secret"),
    lambda i: i.update(durationMs=float("nan")),
    lambda i: i.update(durationMs=10 ** 10000),
    lambda i: i.update(outputBytes=True),
    lambda i: i["resource"].update(id=[]),
    lambda i: i.update(reason=[]),
    lambda i: i.update(invocationId=i["invocationId"].upper()),
    lambda i: i.update(independentlyVerified=True),
    lambda i: i.update(causalContribution=True),
    lambda i: i.update(promotionAllowed=True),
    lambda i: i.update(outcome="fail"),
])
def test_rejects_invalid_observation(change):
    record, item = fixture()
    change(item)
    with pytest.raises(ValueError, match="Invalid Harness invocation metadata"):
        validate_invocations({"harnessInvocations": [item]}, record)


def test_rejects_wrong_context_target_duplicates_and_legacy_record():
    record, item = fixture()
    legacy = copy.deepcopy(record)
    legacy["contextProtocolVersion"] = 1
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [item]}, legacy)
    wrong = copy.deepcopy(record)
    wrong["nodeId"] = "neighbor"
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [item]}, wrong)
    duplicate = copy.deepcopy(item)
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [item, duplicate]}, record)


def test_rejects_bad_pinned_resource_and_outcome_claim():
    record, item = fixture()
    record["assignment"]["documents"][0]["fields"]["harness"]["resources"][0]["content"] = "changed"
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [item]}, record)
    record, item = fixture()
    item.update(reason="timeout", outcome="pass")
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [item]}, record)


def test_rejects_oversized_array_and_extra_metadata_fields():
    record, item = fixture()
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [item] * 33}, record)
    item["trace"] = "extra metadata"
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [item]}, record)
