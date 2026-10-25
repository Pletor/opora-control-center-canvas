import copy
import hashlib
import json
from importlib.util import find_spec
from types import SimpleNamespace

import pytest

from backend.library import harness_adapter_kit as adapter
from backend.library.harness_invocations import validate_invocations
from backend.library.harness_paired_plan import accepted_plan
from backend.library.harness_paired_results import validate_report
from backend.library.test_harness_invocations import fixture as invocation_fixture
from backend.library.test_harness_paired_plan import fixture as paired_fixture
from backend.library.test_harness_paired_results import valid_report


def select(record):
    kit = next(d for d in record["assignment"]["documents"] if d["nodeId"] == record["nodeId"])["fields"]["harness"]
    kit["schema"] = "harness.kit/2"
    entries = []
    for order, resource in enumerate(kit["resources"]):
        version = {key: resource[key] for key in ("category", "digest", "requires", "resource")}
        entries.append({"resource": resource["resource"], "digest": resource["digest"], "order": order,
                        "reason": "explicit-assignment", "assignments": [
                            {"slot": resource["slot"], "scope": "global", "node": None}],
                        "versionDigest": hashlib.sha256(json.dumps(version, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
    kit["selection"] = {"schema": "harness.selection/1", "policy": "harness.recommendation/1",
                        "problem": kit["problems"][0], "profileRevision": 1,
                        "declaredCapabilities": ["command:node"], "evidence": "caller-declared-selection", "entries": entries}
    return kit


@pytest.mark.parametrize("kind", ["missing", "missing-export", "old"])
def test_optional_validator_failures_refuse_v2_and_preserve_v1(monkeypatch, kind):
    def load(_name):
        if kind == "missing":
            raise ModuleNotFoundError("optional module")
        if kind == "missing-export":
            return SimpleNamespace()
        def old(kit):
            assert kit["schema"] == "harness.kit/2" and "selection" in kit
            raise ValueError("Unsupported Harness kit schema.")
        return SimpleNamespace(validate_kit=old)
    monkeypatch.setattr(adapter, "import_module", load)
    record, observation = invocation_fixture()
    assert validate_invocations({"harnessInvocations": [observation]}, record) == [observation]
    select(record)
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [observation]}, record)
    record, reference = paired_fixture()
    assert accepted_plan(record, reference)["resource"] == reference
    select(record)
    with pytest.raises(ValueError):
        accepted_plan(record, reference)


def test_unknown_schema_never_reaches_optional_validator(monkeypatch):
    def never(_name):
        pytest.fail("unknown schema must not import a validator")
    monkeypatch.setattr(adapter, "import_module", never)
    with pytest.raises(ValueError, match="Unsupported"):
        adapter.validate_adapter_kit({"schema": "harness.kit/99"})


@pytest.mark.skipif(find_spec("backend.library.harness_kit") is None, reason="Composed full validator required")
def test_composed_invocation_and_paired_validation_preserve_provenance():
    record, observation = invocation_fixture()
    kit = select(record)
    before = copy.deepcopy(record)
    assert validate_invocations({"harnessInvocations": [observation]}, record) == [observation]
    assert record == before
    kit["selection"]["entries"][0]["versionDigest"] = "0" * 64
    with pytest.raises(ValueError):
        validate_invocations({"harnessInvocations": [observation]}, record)

    record, result = valid_report()
    kit = select(record)
    before = copy.deepcopy(record)
    assert len(validate_invocations(result, record)) == 6
    accepted_plan(record, result["harnessPairedEvaluation"]["plan"])
    report = validate_report(result, record)
    assert report["comparison"]["regressions"] == 1
    assert report["promotionAllowed"] is False
    assert record == before
    kit["selection"]["entries"].reverse()
    with pytest.raises(ValueError):
        accepted_plan(record, result["harnessPairedEvaluation"]["plan"])
