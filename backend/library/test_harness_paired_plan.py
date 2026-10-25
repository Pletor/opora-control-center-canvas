import copy
import hashlib
import json

import pytest

from backend.library.harness_paired_plan import accepted_plan


def _resource(slot, resource, category, content, requires):
    return {"slot": slot, "resource": resource, "category": category, "content": content,
            "digest": hashlib.sha256(content.encode()).hexdigest(), "requires": requires}


def fixture(plan=None):
    plan = plan or {"schema": "harness.paired-node/1", "problem": "numeric.identity",
                    "baseline": "script:base", "candidate": "script:candidate",
                    "cases": [{"id": "negative", "args": ["-2"], "expectedStdout": "-2\n"}]}
    content = json.dumps(plan, separators=(",", ":"))
    plan_resource = _resource("testing.paired", "testing:compare", "testing", content, [])
    base = _resource("scripts.base", "script:base", "scripts", "console.log('base')", ["command:node"])
    candidate = _resource("scripts.candidate", "script:candidate", "scripts", "console.log('candidate')", ["command:node"])
    record = {"contextProtocolVersion": 2, "executionId": "exec-1", "epoch": 3, "project": "p", "workspace": "draft",
              "nodeId": "node-1", "assignment": {"documents": [{"nodeId": "other", "fields": {"harness": {}}},
              {"nodeId": "node-1", "fields": {"harness": {"schema": "harness.kit/1",
               "problems": ["evaluation:paired-node"], "resources": [plan_resource, base, candidate]}}}]}}
    return record, {"id": plan_resource["resource"], "digest": plan_resource["digest"]}


def test_reads_own_accepted_testing_plan_and_projects_metadata():
    record, reference = fixture()
    prepared = accepted_plan(record, reference)
    assert prepared["plan"]["problem"] == "numeric.identity"
    assert prepared["baseline"]["id"] == "script:base"
    assert prepared["candidate"]["id"] == "script:candidate"
    assert prepared["resource"] == reference
    assert "slot" not in prepared["baseline"] and "slot" not in prepared["resource"]
    prepared["plan"]["cases"][0]["args"].append("mutated")
    assert record["assignment"]["documents"][1]["fields"]["harness"]["resources"][0]["content"] == json.dumps(
        {"schema": "harness.paired-node/1", "problem": "numeric.identity", "baseline": "script:base",
         "candidate": "script:candidate", "cases": [{"id": "negative", "args": ["-2"], "expectedStdout": "-2\n"}]}, separators=(",", ":"))


def test_rejects_foreign_missing_or_non_evaluation_context():
    record, reference = fixture()
    foreign = copy.deepcopy(record); foreign["nodeId"] = "other"
    with pytest.raises(ValueError): accepted_plan(foreign, reference)
    with pytest.raises(ValueError): accepted_plan(record, {"id": "testing:absent", "digest": reference["digest"]})
    old = copy.deepcopy(record); old["contextProtocolVersion"] = 1
    with pytest.raises(ValueError): accepted_plan(old, reference)
    for problems in ([], ["numeric.identity"], ["evaluation:paired-node", "numeric.identity"]):
        mixed = copy.deepcopy(record); mixed["assignment"]["documents"][1]["fields"]["harness"]["problems"] = problems
        with pytest.raises(ValueError): accepted_plan(mixed, reference)


def test_rejects_digests_categories_requirements_and_duplicate_resources():
    record, reference = fixture()
    for change in ("plan-digest", "script-digest", "plan-category", "script-requires", "duplicate"):
        changed = copy.deepcopy(record); resources = changed["assignment"]["documents"][1]["fields"]["harness"]["resources"]
        if change == "plan-digest": reference_bad = {**reference, "digest": "0" * 64}
        else: reference_bad = reference
        if change == "script-digest": resources[1]["digest"] = "0" * 64
        if change == "plan-category": resources[0]["category"] = "scripts"
        if change == "script-requires": resources[1]["requires"] = ["command:node", "command:node"]
        if change == "duplicate": resources.append(copy.deepcopy(resources[1]))
        with pytest.raises(ValueError): accepted_plan(changed, reference_bad)


@pytest.mark.parametrize("plan", [
    {"schema": "harness.paired-node/2", "problem": "x", "baseline": "script:base", "candidate": "script:candidate", "cases": []},
    {"schema": "harness.paired-node/1", "problem": "x", "baseline": "script:base", "candidate": "script:candidate", "extra": True, "cases": [{"id": "x", "args": [], "expectedStdout": ""}]},
    {"schema": "harness.paired-node/1", "problem": "x", "baseline": "script:base", "candidate": "script:candidate", "cases": [{"id": "x", "args": [], "expectedStdout": ""}, {"id": "x", "args": [], "expectedStdout": ""}]},
    {"schema": "harness.paired-node/1", "problem": "x", "baseline": "script:base", "candidate": "script:candidate", "cases": [{"id": "x", "args": ["\ud800"], "expectedStdout": ""}]},
    {"schema": "harness.paired-node/1", "problem": "x", "baseline": "script:base", "candidate": "script:candidate", "cases": [{"id": "x", "args": [], "expectedStdout": "\0"}]},
    {"schema": "harness.paired-node/1", "problem": "x", "baseline": "script:base", "candidate": "script:candidate", "cases": [{"id": str(i), "args": [], "expectedStdout": ""} for i in range(9)]},
    {"schema": "harness.paired-node/1", "problem": "x", "baseline": "script:base", "candidate": "script:candidate", "cases": [{"id": "x", "args": [str(i) for i in range(33)], "expectedStdout": ""}]},
    {"schema": "harness.paired-node/1", "problem": "x", "baseline": "script:base", "candidate": "script:candidate", "cases": [{"id": "x", "args": [], "expectedStdout": "a" * 8193}]},
])
def test_rejects_invalid_plan_shapes_and_case_values(plan):
    record, reference = fixture(plan)
    with pytest.raises(ValueError): accepted_plan(record, reference)
