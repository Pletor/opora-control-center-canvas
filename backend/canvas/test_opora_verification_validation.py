"""Hostile imported metadata fails closed before any execution mutation."""
import copy

import pytest

from backend.canvas import opora_verification_validation as validation
from backend.canvas.test_opora_verifications import artifact, verification


@pytest.mark.parametrize("path", ["/main.lean", "../main.lean", "a/../main.lean", "a//b", "a\\b", "C:/a", "a/./b", "a/", "a\0b", "x" * 241])
def test_paths_are_bounded_relative_posix(path):
    value = verification()
    value["artifacts"][0]["path"] = path
    with pytest.raises(ValueError):
        validation.verification(value)


@pytest.mark.parametrize("mutation", [
    lambda v: v.update(trust="independent"),
    lambda v: v.update(independentlyVerified=True),
    lambda v: v["tool"].update(name="shell"),
    lambda v: v["tool"].update(distributionSha256="A" * 64),
    lambda v: v["tool"].update(name={}),
    lambda v: v["source"].update(repository="https://github.com/owner/repo"),
    lambda v: v["source"].update(commitSha="a" * 64),
    lambda v: v["source"].update(repository="owner/.."),
    lambda v: v["claims"][0].update(kind="invariant"),
    lambda v: v["claims"].append(copy.deepcopy(v["claims"][0])),
    lambda v: v["claims"][0].update(statement="x" * 4001),
    lambda v: v["claims"][0].update(statementDigest="a" * 64),
    lambda v: v.update(claims=[]),
    lambda v: v.update(assumptions=[""]),
    lambda v: v.update(configuration=[]),
    lambda v: v["configuration"].update(limit=float("nan")),
    lambda v: v["configuration"].update(limit=float("inf")),
    lambda v: v["configuration"].update(a="x" * 4001),
    lambda v: v["configuration"].update(a=["x" * 4000] * 5),
    lambda v: v["artifacts"][0].update(dataBase64="!bad!"),
    lambda v: v["artifacts"][0].update(sha256="b" * 64),
    lambda v: v["artifacts"][0].update(role={}),
    lambda v: v["artifacts"].append(copy.deepcopy(v["artifacts"][0])),
    lambda v: v.update(artifacts=[]),
    lambda v: v.update(artifacts=[artifact(str(i)) for i in range(33)]),
])
def test_strict_metadata_rejects_invalid_or_forged_values(mutation):
    value = verification()
    mutation(value)
    with pytest.raises(ValueError):
        validation.verification(value)


def test_configuration_depth_and_byte_hashes():
    value = verification()
    current = value["configuration"]
    for _ in range(9):
        current["next"] = {}
        current = current["next"]
    with pytest.raises(ValueError, match="depth"):
        validation.verification(value)
    value = verification()
    value["artifacts"] = [artifact(data=b"line\r\n"), artifact("other.lean", data=b"line\n")]
    normalized, blobs = validation.verification(value)
    assert len(blobs) == 2
    assert all("dataBase64" not in item for item in normalized["artifacts"])


def test_file_and_message_limits(monkeypatch):
    monkeypatch.setattr(validation, "FILE_LIMIT", 4)
    value = verification()
    value["artifacts"] = [artifact(data=b"12345")]
    with pytest.raises(ValueError):
        validation.verification(value)
    monkeypatch.setattr(validation, "FILE_LIMIT", 100)
    monkeypatch.setattr(validation, "RUN_LIMIT", 4)
    with pytest.raises(ValueError, match="8 MiB"):
        validation.verification(value)


@pytest.mark.parametrize("changes", [
    {"checkedClaims": []}, {"checkedClaims": ["unknown"]}, {"checkedClaims": ["identity", "identity"]},
    {"checkedClaims": [{}]}, {"outcome": {}}, {"outcome": "independently-verified"},
    {"trust": "independent"}, {"artifacts": []}, {"outcome": "counterexample", "artifacts": []},
])
def test_report_requires_declared_claims_and_evidence(changes):
    value = {"outcome": "passed", "checkedClaims": ["identity"], "summary": "Reported check",
             "artifacts": [artifact("stdout.txt", "stdout", b"ok")]}
    value.update(changes)
    with pytest.raises(ValueError):
        validation.report(value, verification()["claims"])


def test_tlc_requires_model_and_configuration_and_matching_claims():
    value = verification()
    value["tool"]["name"] = "tlc"
    value["claims"][0]["kind"] = "invariant"
    value["artifacts"] = [artifact("Model.tla", "model")]
    with pytest.raises(ValueError, match="required"):
        validation.verification(value)
    value["artifacts"].append(artifact("Model.cfg", "configuration", b"INIT Init"))
    assert validation.verification(value)[0]["tool"]["name"] == "tlc"


def test_report_preserves_run_metadata_and_rejects_unknown_roles():
    value = {"outcome": "passed", "checkedClaims": ["identity"], "summary": "Reported check",
             "artifacts": [artifact("run-metadata.json", "run-metadata", b'{"exitCode":0,"termination":"completed"}')]}
    normalized, blobs = validation.report(value, verification()["claims"])
    assert normalized["artifacts"][0]["role"] == "run-metadata"
    assert next(iter(blobs.values())) == b'{"exitCode":0,"termination":"completed"}'
    value["artifacts"][0]["role"] = "unknown-output"
    with pytest.raises(ValueError, match="role"):
        validation.report(value, verification()["claims"])
    value["artifacts"] = []
    with pytest.raises(ValueError, match="output evidence"):
        validation.report(value, verification()["claims"])
    value["artifacts"] = [artifact("run-metadata.json", "run-metadata", b"{}")]
    value["checkedClaims"] = []
    with pytest.raises(ValueError, match="every claim"):
        validation.report(value, verification()["claims"])
