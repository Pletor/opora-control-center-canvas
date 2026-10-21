"""Observed `formal/tlc` check runs become execution-bound evidence and agent-state attention."""
import re
from pathlib import Path

import pytest

from backend.canvas import opora_formal_check_poll as formal_poll
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_execution_pr_manager import ExecutionPullRequestManager
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.canvas.opora_formal_checks import CLAIMS, EVIDENCE_KINDS, failures, ingest_snapshot, outcome
from backend.canvas.opora_review_evidence import OporaReviewEvidence
from backend.canvas.opora_verifications import OporaVerifications
from backend.canvas.test_opora_execution_pull_requests import SHA, Reader, body, claim
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world_fixture  # noqa: PLC0414
from backend.canvas.test_opora_review_fixtures import AGENT
from backend.canvas.test_opora_review_fixtures import Reader as EvidenceReader
from backend.integrations.github_review_transport import GitHubReadError

ROOT = Path(__file__).resolve().parents[2]
VIOLATION = {"title": "formal/tlc positive_violation",
             "message": '{"model":"oporahub-execution","case":"positive","config":"ExecutionAuthority.cfg",'
                        '"expect":"pass","expectedInvariant":null,"kind":"positive_violation",'
                        '"violated":"OneActiveOwner"}'}


def check(identifier=11, conclusion="failure", sha=SHA, name="formal/tlc", status="completed"):
    return {"id": identifier, "appId": 15368, "name": name, "headSha": sha, "status": status,
            "conclusion": conclusion}


def snapshot(*checks, number=7):
    return {"complete": True, "configuredRepository": "owner/repo", "prNumber": number, "checks": list(checks)}


def ingest(service, scope, data):
    db = service.db_for(scope["project"])
    with db:
        db.execute("BEGIN IMMEDIATE")
        return ingest_snapshot(db, scope["project"], scope["workspace"], data)


@pytest.fixture
def linked(world):
    service, scope, executions = world
    record = claim(executions, scope)
    ExecutionPullRequestLinks(service, Reader()).link(record["executionId"], body(record), "agent")
    return service, scope, record


def history(service, scope):
    return OporaVerifications(service).history(**scope)["requests"]


def test_claims_mirror_the_positive_config_and_lean_is_not_connected():
    cfg = (ROOT / "tools/formal/oporahub-execution/ExecutionAuthority.cfg").read_text(encoding="utf-8")
    invariants = re.search(r"^INVARIANTS (.+)$", cfg, re.MULTILINE).group(1).split()
    properties = re.search(r"^PROPERTY (.+)$", cfg, re.MULTILINE).group(1).split()
    assert sorted(CLAIMS) == sorted([(name, "invariant") for name in invariants]
                                    + [(name, "temporal-property") for name in properties])
    assert EVIDENCE_KINDS["lean"]["status"] == "not_connected"


def test_outcome_mapping_from_conclusion_and_runner_annotations():
    assert outcome(check(conclusion="success"), []) == "passed"
    assert outcome(check(), failures([VIOLATION])) == "counterexample"
    vacuous = {"title": "formal/tlc negative_not_detected", "message": '{"kind":"negative_not_detected"}'}
    assert outcome(check(), failures([vacuous, {"title": "other", "message": "{}"}])) == "failed"
    assert outcome(check(), []) == "failed"
    assert outcome(check(conclusion="timed_out"), []) == "inconclusive"
    assert outcome(check(conclusion="cancelled"), []) == "cancelled"
    assert failures([{"title": "formal/tlc runner_error", "message": "not json"}]) == []


def test_linked_check_is_recorded_once_bound_to_execution_and_sha(linked):
    service, scope, record = linked
    stored = ingest(service, scope, snapshot(check(conclusion="success"), check(12, name="tests")))
    assert len(stored) == 1
    assert ingest(service, scope, snapshot(check(conclusion="success"))) == []
    [item] = history(service, scope)
    assert item["executionId"] == record["executionId"] and item["nodeId"] == "card"
    assert item["epoch"] == record["epoch"] and item["acceptedRevision"] == record["acceptedRevision"]
    assert item["verification"]["source"] == {"repository": "owner/repo", "commitSha": SHA}
    assert item["origin"]["checkRunId"] == 11 and item["origin"]["observedVia"] == "github-evidence"
    assert item["trust"] == "agent-reported" and item["independentlyVerified"] is False
    assert item["report"]["outcome"] == "passed"
    assert set(item["report"]["checkedClaims"]) == {name for name, _ in CLAIMS}
    assert all(artifact["available"] for artifact in item["report"]["artifacts"])


def test_unlinked_pr_incomplete_or_running_checks_and_lean_are_not_recorded(linked):
    service, scope, _ = linked
    assert ingest(service, scope, snapshot(check(), number=99)) == []
    assert ingest(service, scope, {**snapshot(check()), "complete": False}) == []
    assert ingest(service, scope, snapshot(check(status="in_progress", conclusion=None))) == []
    assert ingest(service, scope, snapshot(check(name="formal/lean"))) == []
    assert history(service, scope) == []


def test_failing_check_becomes_attention_and_a_later_pass_clears_it(linked):
    service, scope, record = linked
    ingest(service, scope, snapshot(check()))
    document = AgentState(service).read(**scope)
    [action] = [item for item in document["actions"] if item["verb"] == "verification.investigate"]
    assert action["status"] == "ready" and action["targetId"] == record["executionId"]
    assert action["path"].startswith("/api/oporahub/verifications/")
    assert action["preconditions"]["headSha"] == SHA and action["preconditions"]["outcome"] == "failed"
    assert document["decisions"][0] == {"id": "dec_" + action["id"][4:], "kind": "verification_failed",
                                        "targetId": record["executionId"],
                                        "title": "Formální kontrola selhala: card", "actionId": action["id"]}
    assert AgentState(service).read(**scope)["actions"] == document["actions"]
    ingest(service, scope, snapshot(check(13, conclusion="success", sha="d" * 40)))
    cleared = AgentState(service).read(**scope)
    assert not [item for item in cleared["actions"] if item["verb"] == "verification.investigate"]


def test_evidence_import_maps_formal_check_automatically(world):
    service, scope, executions = world
    record = claim(executions, scope)
    ExecutionPullRequestLinks(service, Reader()).link(record["executionId"], body(record, number=1), "agent")
    payload = {**scope, "expectedAcceptedHead": OporaChangesets(service).context(scope["project"], scope["workspace"])["acceptedHead"],
               "prNumber": 1}
    reader = EvidenceReader(payload)
    sha = reader.result["pr"]["headSha"]
    reader.result["checks"].append(check(21, sha=sha))
    OporaReviewEvidence(service, reader).observe(payload, AGENT)
    [item] = history(service, scope)
    assert item["report"]["outcome"] == "failed" and item["verification"]["source"]["commitSha"] == sha


class FormalReader:
    def __init__(self, conclusion="failure", error=None):
        self.calls, self.conclusion, self.error = [], conclusion, error

    def checks(self, repository, sha):
        self.calls.append(("checks", repository, sha))
        if self.error:
            raise self.error
        return [check(31, conclusion=self.conclusion, sha=sha)]

    def annotations(self, repository, check_id):
        self.calls.append(("annotations", repository, check_id))
        return [VIOLATION]


def test_execution_pr_loop_polls_linked_heads_and_records_counterexample(linked, monkeypatch):
    service, scope, record = linked
    monkeypatch.setenv("OPORA_EXECUTION_PR_DISCOVERY_SECONDS", "0")
    now = [1000.0]
    manager = ExecutionPullRequestManager(service, ExecutionPullRequestLinks(service, Reader()), clock=lambda: now[0])
    reader = FormalReader()
    formal_poll.register_reader(manager, reader)
    manager.run_once()
    [item] = history(service, scope)
    assert item["report"]["outcome"] == "counterexample" and item["origin"]["observedVia"] == "execution-pr-loop"
    assert item["origin"]["failureKinds"] == ["positive_violation"]
    assert any(artifact["role"] == "counterexample" for artifact in item["report"]["artifacts"])
    decision = AgentState(service).read(**scope)["decisions"][0]
    assert decision["kind"] == "verification_counterexample" and decision["targetId"] == record["executionId"]
    manager.run_once()  # Interval not elapsed: no new GitHub read.
    now[0] += 301
    manager.run_once()  # Known check run: no annotation re-read, no duplicate record.
    assert [call[0] for call in reader.calls] == ["checks", "annotations", "checks"]
    assert len(history(service, scope)) == 1
    manager.close()


def test_rate_limited_poll_pauses_the_loop(linked):
    service, scope, _ = linked
    manager = ExecutionPullRequestManager(service, ExecutionPullRequestLinks(service, Reader()), clock=lambda: 50.0)
    formal_poll.register_reader(manager, FormalReader(error=GitHubReadError(status=429)))
    assert formal_poll.poll(manager, scope["project"]) == 0
    assert manager.cooldown_until == 50.0 + formal_poll.RATE_LIMIT_PAUSE
    manager.close()


def test_offline_manager_without_registered_reader_never_reads_github(linked):
    service, scope, _ = linked
    manager = ExecutionPullRequestManager(service, ExecutionPullRequestLinks(service, Reader()))
    assert formal_poll.poll(manager, scope["project"]) == 0
    manager.close()
