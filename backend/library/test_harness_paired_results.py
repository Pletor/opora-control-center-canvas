import copy
import uuid

import pytest

from backend.library.harness_invocations import EXECUTION_KEYS
from backend.library.harness_paired_plan import accepted_plan
from backend.library.harness_paired_results import COVERAGE, OUTPUT, validate_report
from backend.library.test_harness_paired_plan import fixture


def valid_report(outcomes=None):
    record, reference = fixture({"schema": "harness.paired-node/1", "problem": "numeric.identity",
        "baseline": "script:base", "candidate": "script:candidate", "cases": [
            {"id": "case:a", "args": ["-1"], "expectedStdout": "-1\n"},
            {"id": "case:b", "args": ["-2"], "expectedStdout": "-2\n"},
            {"id": "case:c", "args": ["-4"], "expectedStdout": "4\n"}]})
    record.update(executionId="exec-1", epoch=3, project="p", workspace="draft", nodeId="node-1",
                  acceptedRevision="a" * 40, assignmentDigest="b" * 64)
    pinned = accepted_plan(record, reference)
    outcomes = outcomes or {("case:a", "baseline"): "fail", ("case:a", "candidate"): "pass",
                            ("case:b", "baseline"): "fail", ("case:b", "candidate"): "pass",
                            ("case:c", "baseline"): "pass", ("case:c", "candidate"): "fail"}
    observations, trials = [], []
    order = 0
    for index, case in enumerate(pinned["plan"]["cases"]):
        for side in (("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")):
            order += 1
            outcome = outcomes[(case["id"], side)]
            identifier = str(uuid.uuid4())
            resource = pinned[side]
            observations.append({"schema": "harness.invocation-metadata/1", "invocationId": identifier,
                "execution": {key: record[key] for key in EXECUTION_KEYS}, "resource": {"id": resource["id"], "digest": resource["digest"]},
                "adapter": "node-readonly/1", "nodeVersion": "v22.13.1", "exitCode": 0, "reason": "completed",
                "durationMs": 3.5, "outputBytes": 4, "outcome": "pass", "authorityCurrentAtCompletion": True,
                "cleanupComplete": True, "evidence": "worker-observed", "independentlyVerified": False,
                "causalContribution": False, "promotionAllowed": False, "tokens": None, "cost": None})
            trials.append({"case": case["id"], "side": side, "order": order, "outcome": outcome,
                "reason": "output-mismatch" if outcome == "fail" else "expected-output", "invocationId": identifier})
    count = lambda side, outcome: sum(t["side"] == side and t["outcome"] == outcome for t in trials)
    base, cand = {"id": pinned["baseline"]["id"], "digest": pinned["baseline"]["digest"]}, {"id": pinned["candidate"]["id"], "digest": pinned["candidate"]["digest"]}
    base.update(planned=3, **{x: count("baseline", x) for x in ("pass", "fail", "unknown")})
    cand.update(planned=3, **{x: count("candidate", x) for x in ("pass", "fail", "unknown")})
    improvements = sum(outcomes[(c["id"], "baseline")] == "fail" and outcomes[(c["id"], "candidate")] == "pass" for c in pinned["plan"]["cases"])
    regressions = sum(outcomes[(c["id"], "baseline")] == "pass" and outcomes[(c["id"], "candidate")] == "fail" for c in pinned["plan"]["cases"])
    report = {"schema": "harness.paired-result/1", "evaluationId": str(uuid.uuid4()),
        "execution": {key: record[key] for key in EXECUTION_KEYS}, "plan": reference,
        "problem": pinned["plan"]["problem"], "nativeProblem": "evaluation:paired-node", "baseline": base, "candidate": cand,
        "status": "complete", "authorityCurrentAtCompletion": True,
        "comparison": {"improvements": improvements, "regressions": regressions, "incomparable": 0,
            "passDifference": cand["pass"] - base["pass"], "conclusion": "regression-on-fixtures" if regressions else "candidate-better-on-fixtures" if improvements else "no-improvement-on-fixtures"},
        "plannedInvocations": 6, "observedInvocations": 6, "trials": trials, "harnessInvocations": copy.deepcopy(observations),
        "evidence": "worker-observed", "independentlyVerified": False, "causalContribution": False, "promotionAllowed": False,
        "coverage": COVERAGE, "outputComparison": OUTPUT, "durationMs": 20, "tokens": None, "cost": None}
    return record, {"harnessPairedEvaluation": report, "harnessInvocations": observations}


def test_valid_quality_mismatch_keeps_process_pass_and_projects_nested_metadata():
    record, result = valid_report()
    value = validate_report(result, record)
    assert value["comparison"]["improvements"] == 2 and value["comparison"]["regressions"] == 1
    assert value["comparison"]["passDifference"] == 1
    assert value["comparison"]["conclusion"] == "regression-on-fixtures"
    assert value["trials"][0]["outcome"] == "fail" and value["trials"][0]["reason"] == "output-mismatch"
    assert all(item["outcome"] == "pass" for item in result["harnessInvocations"])
    assert "harnessInvocations" not in value
    def keys(obj):
        if isinstance(obj, dict): return set(obj) | set().union(*(keys(v) for v in obj.values()))
        if isinstance(obj, list): return set().union(*(keys(v) for v in obj))
        return set()
    assert not keys(value).intersection({"stdout", "stderr", "expectedStdout", "args"})
    assert value["independentlyVerified"] is value["causalContribution"] is value["promotionAllowed"] is False


@pytest.mark.parametrize("mutate", [
    lambda r: r["harnessPairedEvaluation"].update(nativeProblem="numeric.identity"),
    lambda r: r["harnessPairedEvaluation"].update(independentlyVerified=True),
    lambda r: r["harnessPairedEvaluation"].update(promotionAllowed=True),
    lambda r: r["harnessPairedEvaluation"]["execution"].update(project="foreign"),
    lambda r: r["harnessPairedEvaluation"].update(coverage="all observed trials"),
    lambda r: r["harnessPairedEvaluation"].update(plan={"id": "testing:compare", "digest": "0" * 64}),
    lambda r: r["harnessPairedEvaluation"]["trials"][0].update(order=True),
    lambda r: r["harnessPairedEvaluation"]["baseline"].update({"pass": True}),
    lambda r: r["harnessPairedEvaluation"]["comparison"].update(regressions=0),
    lambda r: r["harnessPairedEvaluation"].update(raw="private output"),
    lambda r: r["harnessPairedEvaluation"]["trials"][0].update(outcome="pass", reason="expected-output"),
    lambda r: r["harnessInvocations"][0].update(exitCode=7, outcome="fail", reason="nonzero-exit"),
    lambda r: r["harnessInvocations"].__setitem__(1, {**r["harnessInvocations"][1], "invocationId": r["harnessInvocations"][0]["invocationId"]}),
    lambda r: r["harnessInvocations"].pop(),
    lambda r: r["harnessInvocations"][0]["resource"].update(id="script:candidate", digest=r["harnessInvocations"][1]["resource"]["digest"]),
    lambda r: r["harnessPairedEvaluation"]["trials"].pop(),
])
def test_rejects_forged_scope_counts_authority_and_quality(mutate):
    record, result = valid_report()
    mutate(result)
    with pytest.raises(ValueError): validate_report(result, record)


def test_unknown_trials_preserve_denominator_and_interruption_stops_observations():
    record, result = valid_report()
    value = result["harnessPairedEvaluation"]
    # First observation is retained; later planned calls remain unknown after authority interruption.
    result["harnessInvocations"][0].update(outcome="fail", reason="execution-changed", authorityCurrentAtCompletion=False)
    value["trials"][0].update(outcome="fail", reason="authority-not-current")
    value["trials"][0]["invocationId"] = result["harnessInvocations"][0]["invocationId"]
    value["trials"][1:] = [{"case": t["case"], "side": t["side"], "order": t["order"],
        "outcome": "unknown", "reason": "authority-not-current", "invocationId": None} for t in value["trials"][1:]]
    value["harnessInvocations"] = [result["harnessInvocations"][0]]
    result["harnessInvocations"] = [result["harnessInvocations"][0]]
    value["baseline"].update({"planned": 3, "fail": 1, "pass": 0, "unknown": 2})
    value["candidate"].update({"planned": 3, "fail": 0, "pass": 0, "unknown": 3})
    value["comparison"].update(improvements=0, regressions=0, incomparable=3, passDifference=0, conclusion="incomplete")
    value.update(status="incomplete", authorityCurrentAtCompletion=False, observedInvocations=1)
    # A later observation after the stop is invalid even if its metadata is otherwise valid.
    bad = copy.deepcopy(result)
    bad["harnessPairedEvaluation"]["trials"][2].update(outcome="pass", reason="expected-output", invocationId=result["harnessInvocations"][0]["invocationId"])
    with pytest.raises(ValueError): validate_report(bad, record)
    assert validate_report(result, record)["observedInvocations"] == 1


def test_stored_plan_digest_and_version_are_revalidated():
    record, result = valid_report()
    resource = record["assignment"]["documents"][1]["fields"]["harness"]["resources"][0]
    resource["content"] = resource["content"].replace('harness.paired-node/1', 'harness.paired-node/2')
    with pytest.raises(ValueError): validate_report(result, record)
    record, result = valid_report()
    resource = record["assignment"]["documents"][1]["fields"]["harness"]["resources"][0]
    resource["content"] = resource["content"].replace('harness.paired-node/1', 'harness.paired-node/2')
    import hashlib
    resource["digest"] = hashlib.sha256(resource["content"].encode()).hexdigest()
    result["harnessPairedEvaluation"]["plan"]["digest"] = resource["digest"]
    with pytest.raises(ValueError): validate_report(result, record)
