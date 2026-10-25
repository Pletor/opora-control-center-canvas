"""Aggregation tests use native-reader stubs; retained integration proves the real boundary."""
import copy
import json

import pytest

from backend.canvas.graph import digest
from backend.library import harness_transfer as transfer
from backend.library.test_harness_stability import prepared as prepared  # noqa: PLC0414
from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414


@pytest.fixture
def configured(monkeypatch):
    item = {"id": "public-tool", "problem": "numeric.identity", "candidate": {"id": "script:shared", "digest": "a" * 64},
            "sources": [{"project": f"project-{i}", "workspace": "draft", "verificationId": f"verify-{i}"} for i in range(3)]}
    config = {"schema": "harness.transfer-policy/1", "publications": [item]}
    monkeypatch.setenv("OPORA_HARNESS_TRANSFER", json.dumps(config))
    images = ["node@sha256:" + c * 64 for c in "bbc"]
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps({"schema": "harness.scopes/1", "scopes": [
        {"project": s["project"], "workspace": s["workspace"], "image": image, "maxExperiments": 1}
        for s, image in zip(item["sources"], images)]}))
    calls = []
    def assess(self, source):
        calls.append(dict(source))
        return {"eligible": True, "candidate": item["candidate"],
                "scope": {"project": source["project"], "workspace": source["workspace"], "problem": item["problem"]},
                "source": {"reportDigest": "d" * 64}, "evidenceDigest": "e" * 64,
                "execution": {"token": "PRIVATE_MARKER", "assignment": "PRIVATE_CONTENT"}}
    monkeypatch.setattr(transfer.RetainedStability, "assess", assess)
    return transfer.SharedEligibility(None), item, config, calls


def test_three_projects_two_images_provenance_only_and_rechecked(configured):
    reader, _, _, calls = configured
    result = reader.assess({"publication": "public-tool"})
    assert result["eligible"] is True and (result["verifiedProjects"], result["verifiedImages"]) == (3, 2)
    assert len(calls) == 6
    assert result["promotionAllowed"] is result["executionAuthority"] is result["reservation"] is False
    assert result["evidenceBasis"]["causalBenefitEstablished"] is False
    assert result["evidenceDigest"] == digest({k: v for k, v in result.items() if k != "evidenceDigest"})
    assert "PRIVATE_" not in json.dumps(result) and "assignment" not in result


@pytest.mark.parametrize("change", ["ineligible", "version", "problem", "unavailable", "changed-proof"])
def test_any_bad_or_changed_source_blocks_transfer(configured, monkeypatch, change):
    reader, _, _, _ = configured
    original = reader.reader.assess
    count = 0
    def altered(source):
        nonlocal count
        count += 1
        value = copy.deepcopy(original(source))
        if source["project"] == "project-1":
            if change == "unavailable": raise ValueError("private failure")
            if change == "ineligible": value["eligible"] = False
            if change == "version": value["candidate"]["digest"] = "f" * 64
            if change == "problem": value["scope"]["problem"] = "other"
            if change == "changed-proof" and count > 3: value["evidenceDigest"] = "f" * 64
        return value
    monkeypatch.setattr(reader.reader, "assess", altered)
    result = reader.assess({"publication": "public-tool"})
    assert result["eligible"] is False and result["reasons"]
    assert "private failure" not in json.dumps(result)


def test_same_image_does_not_satisfy_environment_diversity(configured, monkeypatch):
    reader, item, _, _ = configured
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps({"schema": "harness.scopes/1", "scopes": [
        {"project": s["project"], "workspace": s["workspace"], "image": "node@sha256:" + "b" * 64, "maxExperiments": 1}
        for s in item["sources"]]}))
    result = reader.assess({"publication": "public-tool"})
    assert result["eligible"] is False and "fewer-than-two-pinned-images" in result["reasons"]


def test_withdrawn_publication_and_caller_evidence_never_authorize(configured, monkeypatch):
    reader, _, _, calls = configured
    for payload in [{"publication": "public-tool", "eligible": True}, {"publication": "public-tool", "sources": []}]:
        with pytest.raises(ValueError): reader.assess(payload)
    assert calls == []
    original = reader.reader.assess
    def withdraw(source):
        monkeypatch.delenv("OPORA_HARNESS_TRANSFER", raising=False)
        return original(source)
    monkeypatch.setattr(reader.reader, "assess", withdraw)
    with pytest.raises(ValueError): reader.assess({"publication": "public-tool"})


def test_real_native_single_project_proof_does_not_become_global_success(prepared, monkeypatch):
    live, _, record, report = prepared
    native = transfer.RetainedStability(live.canvas).assess({"project": record["project"], "workspace": record["workspace"], "verificationId": report["id"]})
    item = {"id": "public-tool", "candidate": native["candidate"], "problem": native["scope"]["problem"],
            "sources": [{"project": record["project"], "workspace": record["workspace"], "verificationId": report["id"]}]}
    monkeypatch.setenv("OPORA_HARNESS_TRANSFER", json.dumps({"schema": "harness.transfer-policy/1", "publications": [item]}))
    result = transfer.SharedEligibility(live.canvas).assess({"publication": "public-tool"})
    assert result["eligible"] is False and result["verifiedProjects"] == result["verifiedImages"] == 1
    assert result["sources"][0]["reportDigest"] == report["report"]["reportDigest"]
    assert record["token"] not in json.dumps(result)


def test_shared_http_actor_bounds_and_reference_only_input(configured):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from backend.api.editor.harness_verifier_routes import create_harness_verifier_router

    app = FastAPI()
    @app.middleware("http")
    async def actor(request: Request, next_call):
        request.state.actor = request.headers.get("x-fixture-actor", "anonymous")
        return await next_call(request)
    app.include_router(create_harness_verifier_router(None))
    with TestClient(app) as client:
        url = "/api/oporahub/harness-verifier/eligibility/shared"
        assert client.post(url, json={"publication": "public-tool"}).status_code == 428
        headers = {"x-fixture-actor": "agent"}
        assert client.post(url, content=b" " * 4097, headers=headers).status_code == 413
        assert client.post(url, json={"publication": "public-tool", "image": "node:latest"}, headers=headers).status_code == 409
        result = client.post(url, json={"publication": "public-tool"}, headers=headers)
        assert result.status_code == 200 and result.json()["eligible"] is True
        assert "PRIVATE_" not in result.text


def test_multiple_workspaces_of_one_project_do_not_count_as_multiple_projects(configured, monkeypatch):
    reader, item, config, _ = configured
    for index, source in enumerate(item["sources"]):
        source.update(project="same-project", workspace=f"workspace-{index}")
    monkeypatch.setenv("OPORA_HARNESS_TRANSFER", json.dumps(config))
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps({"schema": "harness.scopes/1", "scopes": [
        {"project": s["project"], "workspace": s["workspace"], "image": "node@sha256:" + c * 64, "maxExperiments": 1}
        for s, c in zip(item["sources"], "bcd")]}))
    result = reader.assess({"publication": "public-tool"})
    assert result["eligible"] is False and result["verifiedProjects"] == 1 and result["verifiedImages"] == 3
