import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.completion_evidence import evidence_ready, validate_evidence
from backend.editor.agent_memory.test_agent_output import ORIGIN, SCOPE, prepared, send
from backend.editor.agent_memory.test_versioned_output import brief, result_request


def evidence():
    return {"tests": {"status": "passed", "url": "https://ci.example/run/1", "note": "Unit tests"},
            "review": {"status": "passed", "url": "https://git.example/pr/1", "note": "Approved"},
            "merge": {"status": "not_applicable", "url": "", "note": "Research task; no code changes"},
            "checksRun": [{"checkId": "unit", "command": "uv run pytest", "exitCode": 0,
                           "logUrl": "https://ci.example/run/1/log", "at": "2026-10-07T12:00:00Z"}]}


def test_structured_evidence_roundtrips_in_brief_and_immutable_result(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assignment = brief(client)
        request = result_request(assignment)
        request["output"]["evidence"] = evidence()
        response = send(client, request)
        assert response.status_code == 200, response.text
        assert response.json()["acceptedResult"]["output"]["evidence"] == evidence()
        current = brief(client)
        assert current["evidence"] == evidence()
        assert current["contextVersion"] == assignment["contextVersion"]
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert brief(client)["evidence"] == evidence()


@pytest.mark.parametrize("mutate", [
    lambda v: v["tests"].update(url="javascript:alert(1)"),
    lambda v: v["review"].update(url=""),
    lambda v: v["merge"].update(note=""),
    lambda v: v["checksRun"][0].update(exitCode=True),
    lambda v: v["checksRun"].append(copy.deepcopy(v["checksRun"][0])),
])
def test_invalid_evidence_rejects_entire_output(tmp_path, mutate):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        request = result_request(brief(client))
        request["output"]["evidence"] = evidence()
        mutate(request["output"]["evidence"])
        before = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert send(client, request).status_code == 409
        assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before


def test_readiness_requires_all_proofs_and_successful_checks():
    value = evidence()
    validate_evidence(value)
    assert evidence_ready(value)
    value["checksRun"][0]["exitCode"] = 1
    assert not evidence_ready(value)
    value["checksRun"] = []
    assert not evidence_ready(value)
    assert not evidence_ready(None)


def test_local_test_run_without_log_url_is_valid_evidence():
    """Kritika #31 (hodný agent): lokální `uv run pytest` nemá URL logu; stačí běh s exitCode 0."""
    from backend.editor.agent_memory.completion_evidence import evidence_ready
    local = evidence()
    local["tests"]["url"] = ""
    local["checksRun"][0]["logUrl"] = ""
    assert evidence_ready(local)
    local["checksRun"] = []
    assert not evidence_ready(local)


def test_task_card_cannot_skip_tests_or_merge_as_not_applicable():
    """Kritika #31 (vyčuraný agent): N/A s poznámkou „x“ neuzavře [task] kartu ani kartu s kontrolami."""
    from backend.editor.agent_memory.completion_evidence import evidence_ready
    lazy = evidence()
    lazy["tests"] = {"status": "not_applicable", "url": "", "note": "x"}
    lazy["checksRun"] = []
    assert evidence_ready(lazy, {"name": "[research] Volba úložiště"})
    assert not evidence_ready(lazy, {"name": "[task] Pipeline"})
    assert not evidence_ready(evidence(), {"name": "Karta", "checks": [{"id": "unit", "command": "uv run pytest"}]})
