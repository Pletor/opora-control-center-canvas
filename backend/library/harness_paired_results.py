"""Reconcile worker-reported paired quality claims; this never independently observes output."""
import math
import uuid

from backend.library.harness_invocations import EXECUTION_KEYS, validate_invocations
from backend.library.harness_paired_plan import accepted_plan

KEYS = {"schema", "evaluationId", "execution", "plan", "problem", "nativeProblem", "baseline", "candidate",
        "status", "authorityCurrentAtCompletion", "comparison", "plannedInvocations", "observedInvocations",
        "trials", "evidence", "independentlyVerified", "causalContribution", "promotionAllowed", "coverage",
        "outputComparison", "durationMs", "tokens", "cost"}
TRIAL_KEYS = {"case", "side", "order", "outcome", "reason", "invocationId"}
COUNT_KEYS = {"planned", "pass", "fail", "unknown"}
COMPARISON_KEYS = {"improvements", "regressions", "incomparable", "passDifference", "conclusion"}
COVERAGE = "all predeclared fixture cases; not independent production trials"
OUTPUT = "exact adapter-normalized stdout plus successful exit, current authority and cleanup"


def _fail():
    raise ValueError("Invalid Harness paired evaluation evidence.")


def _uuid(value):
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _observed(trial, item):
    """Output match remains the worker's assertion; process failures cannot become quality passes."""
    if trial["outcome"] not in ("pass", "fail"):
        _fail()
    stop = ""
    if not item["authorityCurrentAtCompletion"] or item["reason"].startswith("execution-"):
        stop = reason = "authority-not-current"
    elif not item["cleanupComplete"]:
        stop = reason = "cleanup-incomplete"
    elif item["outcome"] == "pass":
        reason = "expected-output" if trial["outcome"] == "pass" else "output-mismatch"
    else:
        reason = item["reason"]
    if trial["reason"] != reason or (item["outcome"] != "pass" and trial["outcome"] != "fail"):
        _fail()
    return stop


def _trials(value, pinned, observations):
    planned = [(case["id"], side) for index, case in enumerate(pinned["plan"]["cases"])
               for side in (("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline"))]
    trials = value["trials"]
    if not isinstance(trials, list) or len(trials) != len(planned):
        _fail()
    by_id = {item["invocationId"]: item for item in observations}
    linked, seen, stopped = [], set(), ""
    for index, (trial, (case, side)) in enumerate(zip(trials, planned, strict=True), 1):
        if (not isinstance(trial, dict) or set(trial) != TRIAL_KEYS
                or trial["case"] != case or trial["side"] != side
                or type(trial["order"]) is not int or trial["order"] != index):
            _fail()
        identifier = trial["invocationId"]
        if identifier is None:
            if trial["outcome"] != "unknown":
                _fail()
            if stopped:
                if trial["reason"] != stopped:
                    _fail()
            elif trial["reason"] in ("launch-budget-exhausted", "adapter-error-or-authority-unavailable"):
                stopped = trial["reason"]
            else:
                _fail()
        else:
            if stopped or not _uuid(identifier) or identifier in seen or identifier not in by_id:
                _fail()
            item = by_id[identifier]
            if item["resource"] != pinned[side]:
                _fail()
            seen.add(identifier)
            linked.append(item)
            stopped = _observed(trial, item)
    return trials, linked, stopped


def _summary(value, pinned, trials, linked, stopped):
    for side in ("baseline", "candidate"):
        counts = {outcome: sum(t["side"] == side and t["outcome"] == outcome for t in trials)
                  for outcome in ("pass", "fail", "unknown")}
        expected = {**pinned[side], "planned": len(pinned["plan"]["cases"]), **counts}
        actual = value[side]
        if (not isinstance(actual, dict) or set(actual) != set(expected)
                or any(type(actual[k]) is not int for k in COUNT_KEYS) or actual != expected):
            _fail()
    improvements = regressions = incomparable = 0
    for case in pinned["plan"]["cases"]:
        pair = {t["side"]: t["outcome"] for t in trials if t["case"] == case["id"]}
        if "unknown" in pair.values():
            incomparable += 1
        elif pair == {"baseline": "fail", "candidate": "pass"}:
            improvements += 1
        elif pair == {"baseline": "pass", "candidate": "fail"}:
            regressions += 1
    complete = incomparable == 0 and value["authorityCurrentAtCompletion"] and not stopped
    conclusion = ("incomplete" if not complete else "regression-on-fixtures" if regressions else
                  "candidate-better-on-fixtures" if improvements else "no-improvement-on-fixtures")
    expected = {"improvements": improvements, "regressions": regressions, "incomparable": incomparable,
                "passDifference": value["candidate"]["pass"] - value["baseline"]["pass"], "conclusion": conclusion}
    actual = value["comparison"]
    if (not isinstance(actual, dict) or set(actual) != COMPARISON_KEYS
            or any(type(actual[k]) is not int for k in COMPARISON_KEYS - {"conclusion"}) or actual != expected
            or value["status"] != ("complete" if complete else "incomplete")
            or type(value["plannedInvocations"]) is not int or value["plannedInvocations"] != len(trials)
            or type(value["observedInvocations"]) is not int or value["observedInvocations"] != len(linked)):
        _fail()


def validate_report(result, record):
    """Return a canonical report without duplicated invocation data, or None for legacy results."""
    if not isinstance(result, dict):
        _fail()
    if "harnessPairedEvaluation" not in result:
        return None
    try:
        supplied = result["harnessPairedEvaluation"]
        if not isinstance(supplied, dict) or "harnessInvocations" not in result:
            _fail()
        value = {key: val for key, val in supplied.items() if key != "harnessInvocations"}
        if (set(value) != KEYS or value["schema"] != "harness.paired-result/1"
                or not _uuid(value["evaluationId"]) or value["evidence"] != "worker-observed"
                or any(value[k] is not False for k in ("independentlyVerified", "causalContribution", "promotionAllowed"))
                or value["tokens"] is not None or value["cost"] is not None
                or type(value["authorityCurrentAtCompletion"]) is not bool
                or value["coverage"] != COVERAGE or value["outputComparison"] != OUTPUT):
            _fail()
        duration = value["durationMs"]
        if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 <= duration <= 3600000:
            _fail()
        execution = value["execution"]
        if (not isinstance(execution, dict) or set(execution) != EXECUTION_KEYS
                or type(execution["epoch"]) is not int or execution != {k: record.get(k) for k in EXECUTION_KEYS}):
            _fail()
        pinned = accepted_plan(record, value["plan"])
        if value["problem"] != pinned["plan"]["problem"] or value["nativeProblem"] != "evaluation:paired-node":
            _fail()
        observations = validate_invocations(result, record)
        trials, linked, stopped = _trials(value, pinned, observations)
        _summary(value, pinned, trials, linked, stopped)
        if "harnessInvocations" in supplied:
            nested = validate_invocations({"harnessInvocations": supplied["harnessInvocations"]}, record)
            if nested != linked:
                _fail()
        return value
    except (KeyError, TypeError, ValueError, OverflowError):
        _fail()
