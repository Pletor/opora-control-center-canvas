"""Eval set: reverts and incidents of reviewed PRs create one immutable case each; recurring misses → checks."""
import json

import pytest

from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_review_evals import ReviewEvals, parse_revert
from backend.canvas.opora_review_insight_common import InsightMissing
from backend.canvas.opora_review_recurring import (
    bug_class,
    detect,
    min_prs,
    promote,
    read_recurring,
)
from backend.canvas.test_opora_execution_pull_requests import pr
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_metrics import seed_pr


class Recent:
    def __init__(self, items):
        self.items, self.calls = items, []

    def recent(self, repository):
        self.calls.append(repository)
        return self.items


def revert_pr(number, body, state="merged"):
    return {**pr(number, state=state, body=body), "headSha": "9" * 40}


def test_parse_revert_trailer():
    assert parse_revert("Revert.\n\nOpora-Revert-Of: #7\n", "owner/repo") == 7
    assert parse_revert("Opora-Revert-Of: Owner/Repo#7", "owner/repo") == 7
    assert parse_revert("Opora-Revert-Of: 7", "owner/repo") == 7
    assert parse_revert("Opora-Revert-Of: other/repo#7", "owner/repo") is None
    assert parse_revert("Opora-Revert-Of: #7\nOpora-Revert-Of: #8", "owner/repo") is None
    assert parse_revert("Opora-Revert-Of: owner/repo7", "owner/repo") is None
    assert parse_revert("mentions Opora-Revert-Of: #7 inline", "owner/repo") is None
    assert parse_revert(None, "owner/repo") is None


def test_revert_and_incident_create_one_case_each_idempotently(world):  # noqa: F811
    service, scope, _ = world
    project = scope["project"]
    seed_pr(service, scope, 7, rounds=2, rejected=1, security=1,
            findings=[("src/a.py:null-deref:user", "important", "fixed"), ("src/b.py:style:x", "nit", "resolved")])
    reader = Recent([revert_pr(9, "Opora-Revert-Of: #7"),            # Merged revert of a reviewed PR.
                     revert_pr(10, "Opora-Revert-Of: #7", "open"),   # Not merged yet.
                     revert_pr(11, "Opora-Revert-Of: #404"),          # Not a reviewed PR.
                     revert_pr(12, "no trailer")])
    evals = ReviewEvals(service, reader)
    first = evals.sync_reverts({"project": project})
    [case_id] = first["created"]
    assert first["reverts"] == [{"number": 7, "revertNumber": 9, "caseId": case_id}]
    again = evals.sync_reverts({"project": project})
    assert again["created"] == [] and again["reverts"][0]["caseId"] == case_id and reader.calls == ["owner/repo"] * 2
    [case] = evals.list(project)["items"]
    assert {key: case[key] for key in ("caseId", "kind", "repository", "number", "baseSha", "revertSha",
                                       "revertNumber", "rounds", "incident", "rejectedFingerprints")} == {
        "caseId": case_id, "kind": "revert", "repository": "owner/repo", "number": 7, "baseSha": "b" * 40,
        "revertSha": "9" * 40, "revertNumber": 9, "rounds": 2, "incident": None, "rejectedFingerprints": ["x:rej0"]}
    assert case["headSha"] == case["diffRef"]["head"] and case["diffRef"]["range"] == f"{'b' * 40}..{case['headSha']}"
    assert [(item["fingerprint"], item["status"], item["path"]) for item in case["findings"]] == [
        ("src/a.py:null-deref:user", "fixed", "a.py"), ("src/b.py:style:x", "resolved", "a.py")]
    incident = {**scope, "repository": "Owner/Repo", "number": 7, "reference": "INC-42", "summary": "Login outage."}
    linked = evals.link_incident(incident, "human")
    assert linked["created"] is True and evals.link_incident(incident, "agent:w") == {**linked, "created": False}
    with pytest.raises(InsightMissing):
        evals.link_incident({**incident, "number": 404}, "human")
    with pytest.raises(ValueError):
        evals.link_incident({**incident, "summary": " "}, "human")
    lines = evals.export_jsonl(project).splitlines()
    assert [json.loads(line)["kind"] for line in lines] == ["revert", "incident"]
    assert json.loads(lines[1])["incident"] == {"reference": "INC-42", "summary": "Login outage."}
    assert evals.export_jsonl(project) == evals.export_jsonl(project)


def test_recurring_bug_class_becomes_a_promote_to_check_action(world, monkeypatch):  # noqa: F811
    service, scope, _ = world
    project = scope["project"]
    assert bug_class("src/a.py:Null-Deref:user") == "null-deref" and bug_class("fp-00000001") == "fp-00000001"
    for number in (1, 2, 3):
        seed_pr(service, scope, number, findings=[(f"src/m{number}.py:null-deref:v", "important", "open")])
    seed_pr(service, scope, 4, findings=[("src/z.py:sql-injection:q", "important", "open")])
    assert read_recurring(service, project) == {"minPrs": 3, "items": [{
        "bugClass": "null-deref", "prCount": 3, "prs": ["owner/repo#1", "owner/repo#2", "owner/repo#3"],
        "fingerprints": 3, "severities": ["important"]}]}
    state = AgentState(service).read(**scope)
    [action] = [item for item in state["actions"] if item["verb"] == "review.promote_to_check"]
    assert action["targetId"] == "null-deref" and action["attention"] is True and action["status"] == "ready"
    assert action["preconditions"] == {"bugClass": "null-deref", "prCount": 3, "minPrs": 3}
    assert action["path"] == "/api/oporahub/review-recurring/promote"
    payload = {"project": project, "bugClass": "Null-Deref", "checkRef": "backend/lint/test_null_guard.py"}
    recorded = promote(service, payload, "agent:w")
    assert recorded["bugClass"] == "null-deref" and promote(service, payload, "human") == recorded
    with pytest.raises(ValueError, match="jinou kontrolu"):
        promote(service, {**payload, "checkRef": "other"}, "human")
    assert detect(service.db_for(project), project) == []
    assert not [item for item in AgentState(service).read(**scope)["actions"]
                if item["verb"] == "review.promote_to_check"]
    monkeypatch.setenv("OPORA_REVIEW_RECURRING_MIN_PRS", "1")
    with pytest.raises(ValueError):
        min_prs()
    monkeypatch.setenv("OPORA_REVIEW_RECURRING_MIN_PRS", "2")
    assert min_prs() == 2
