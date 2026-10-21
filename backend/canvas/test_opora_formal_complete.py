"""Lean evidence with axiom audit, trusted CI provenance, counterexample -> fix proposal, proof ledger."""
import json

import pytest

from backend.canvas import opora_formal_check_poll as formal_poll
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_execution_pr_manager import ExecutionPullRequestManager
from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks
from backend.canvas.opora_formal_followup import propose
from backend.canvas.opora_formal_ledger import catalog, ledger
from backend.canvas.opora_formal_profiles import LEAN_MODULES, lean_audit
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_verifications import OporaVerifications
from backend.canvas.test_opora_execution_pull_requests import SHA, Reader
from backend.canvas.test_opora_formal_checks import VIOLATION, check, ingest, snapshot
from backend.canvas.test_opora_formal_checks import linked as linked  # noqa: PLC0414
from backend.canvas.test_opora_formal_checks import world_fixture as world_fixture  # noqa: PLC0414

THEOREMS = [["OporaHub.Votes.no_repost", ["Classical.choice", "Quot.sound", "propext"]],
            ["OporaHub.AcceptedHead.stale_never_advances", ["propext"]],
            ["OporaHub.FieldMerge.merged_comm", ["Quot.sound", "propext"]]]


def audit_note(theorems=None, ok=True):
    payload = {"toolchain": "leanprover/lean4:v4.22.0", "trusted": False, "ok": ok, "theorems": theorems or THEOREMS}
    return {"title": "formal/lean audit", "message": json.dumps(payload)}


class Formal:
    """Offline GitHub reader for the loop: configurable checks, annotations and provenance."""

    def __init__(self, checks, notes=None, provenance=None):
        self.list, self.notes, self.origin, self.calls = checks, notes or {}, provenance, []

    def checks(self, repository, sha):
        self.calls.append("checks")
        return [{**item, "headSha": sha} for item in self.list]

    def annotations(self, repository, check_id):
        self.calls.append(f"annotations:{check_id}")
        return self.notes.get(check_id, [])

    def provenance(self, repository, item):
        self.calls.append(f"provenance:{item['id']}")
        return self.origin


def poll(service, reader):
    manager = ExecutionPullRequestManager(service, ExecutionPullRequestLinks(service, Reader()), clock=lambda: 1000.0)
    formal_poll.register_reader(manager, reader)
    manager.run_once()
    manager.close()


def records(service, scope):
    return OporaVerifications(service).history(**scope)["requests"]


def test_lean_audit_parsing_rejects_malformed_payloads():
    assert lean_audit([audit_note()])["theorems"]["OporaHub.AcceptedHead.stale_never_advances"] == ["propext"]
    assert lean_audit([{"title": "formal/lean audit", "message": "{"}]) is None
    assert lean_audit([{"title": "formal/lean audit", "message": '{"theorems": [["x"]]}'}]) is None
    assert lean_audit([]) is None


def test_lean_pass_requires_clean_complete_axiom_audit(linked):
    service, scope, _ = linked
    poll(service, Formal([check(41, conclusion="success", name="formal/lean")], {41: [audit_note()]}))
    [item] = records(service, scope)
    assert item["verification"]["tool"]["name"] == "lean" and item["report"]["outcome"] == "passed"
    assert [claim["id"] for claim in item["verification"]["claims"]] == [f"OporaHub-{name}" for name in LEAN_MODULES]
    assert item["verification"]["configuration"]["axiomAudit"]["OporaHub.Votes.no_repost"] == [
        "Classical.choice", "Quot.sound", "propext"]
    assert item["verification"]["configuration"]["auditComplete"] is True
    assert item["trust"] == "agent-reported" and item["origin"]["evidenceKind"] == "lean"


@pytest.mark.parametrize("notes,expected", [
    ([], "inconclusive"),
    ([audit_note([["OporaHub.Votes.no_repost", ["sorryAx"]]])], "inconclusive"),
    ([audit_note(ok=False)], "inconclusive")])
def test_green_lean_build_without_clean_audit_is_not_passed(linked, notes, expected):
    service, scope, _ = linked
    poll(service, Formal([check(42, conclusion="success", name="formal/lean")], {42: notes}))
    assert records(service, scope)[0]["report"]["outcome"] == expected


def test_failed_lean_audit_is_failed_with_kinds(linked):
    service, scope, _ = linked
    bad = {"title": "formal/lean nonstandard_axiom",
           "message": '{"kind":"nonstandard_axiom","theorem":"OporaHub.Votes.x","axioms":["sorryAx"]}'}
    poll(service, Formal([check(43, name="formal/lean")], {43: [audit_note(), bad]}))
    [item] = records(service, scope)
    assert item["report"]["outcome"] == "failed" and item["origin"]["failureKinds"] == ["nonstandard_axiom"]


def test_trusted_check_is_ci_verified_only_with_verified_provenance(linked):
    service, scope, _ = linked
    good = {"verified": True, "reason": None, "runId": 42, "event": "pull_request_target",
            "path": ".github/workflows/formal-trusted.yml", "headBranch": "main"}
    reader = Formal([check(51, conclusion="success", name="formal-trusted/tlc")], provenance=good)
    poll(service, reader)
    [item] = records(service, scope)
    assert item["trust"] == "ci-verified" and item["sourceBinding"] == "ci-verified"
    assert item["report"]["trust"] == "ci-verified" and item["independentlyVerified"] is False
    assert item["origin"]["provenance"]["runId"] == 42 and "provenance:51" in reader.calls
    assert "annotations:51" not in reader.calls  # passing TLC needs no annotations


def test_trusted_name_without_provenance_stays_agent_reported(linked):
    service, scope, _ = linked
    poll(service, Formal([check(52, conclusion="success", name="formal-trusted/tlc")],
                         provenance={"verified": False, "reason": "untrusted_event"}))
    [item] = records(service, scope)
    assert item["trust"] == "agent-reported" and item["origin"]["provenance"]["reason"] == "untrusted_event"


def test_snapshot_import_leaves_lean_and_trusted_checks_to_the_loop(linked):
    service, scope, _ = linked
    assert ingest(service, scope, snapshot(check(61, name="formal-trusted/tlc"), check(62, name="formal/lean"))) == []


def proposals(service, scope):
    return OporaGraphProposals(service).list(**scope)["items"]


def test_counterexample_proposes_one_fix_card_with_evidence_for_human_acceptance(linked):
    service, scope, record = linked
    poll(service, Formal([check(71)], {71: [VIOLATION]}))
    [item] = records(service, scope)
    [proposal] = proposals(service, scope)
    assert proposal["by"] == {"kind": "orchestrator", "name": "system · formal verification"}
    assert item["id"][:12] in proposal["subject"] and proposal["accepted"] is False
    full = OporaGraphProposals(service).read(**scope, record_id=proposal["id"])
    [spec] = [entry for entry in full["specifications"] if entry["nodeId"] == full["refs"]["fix"]]
    assert "positive_violation" in spec["fields"]["goal"] and "/artifacts/" in spec["fields"]["goal"]
    assert propose(service, scope["project"], scope["workspace"], item["id"])["created"] is False
    assert len(proposals(service, scope)) == 1
    actions = AgentState(service).read(**scope)["actions"]
    [fix] = [action for action in actions if action["verb"] == "verification.fix"]
    assert fix["method"] == "POST" and fix["path"] == f"/api/oporahub/verifications/{item['id']}/fix-proposal"
    assert fix["targetId"] == record["executionId"] and fix["preconditions"]["headSha"] == SHA


def test_runner_error_or_pass_proposes_nothing(linked):
    service, scope, _ = linked
    runner = {"title": "formal/tlc runner_error", "message": '{"kind":"runner_error"}'}
    poll(service, Formal([check(81)], {81: [runner]}))
    [item] = records(service, scope)
    assert item["report"]["outcome"] == "failed" and proposals(service, scope) == []
    assert propose(service, scope["project"], scope["workspace"], item["id"]) is None
    assert not [a for a in AgentState(service).read(**scope)["actions"] if a["verb"] == "verification.fix"]


def test_ledger_lists_catalog_and_latest_evidence(linked):
    service, scope, _ = linked
    rows = {row["id"]: row for row in ledger(service, **scope)["entries"]}
    declared = {row["id"] for row in catalog()}
    assert set(rows) == declared and {row["status"] for row in rows.values()} == {"unchecked"}
    assert "lean:OporaHub.Votes.no_repost" in rows and "tlc:ReviewJobs-NoRepost" in rows
    poll(service, Formal([check(91, conclusion="success", name="formal/lean"), check(92, conclusion="success")],
                         {91: [audit_note()]}))
    document = ledger(service, **scope)
    rows = {row["id"]: row for row in document["entries"]}
    assert rows["lean:OporaHub.Votes.no_repost"]["status"] == "proved"
    assert rows["lean:OporaHub.Votes.no_repost"]["axioms"] == ["Classical.choice", "Quot.sound", "propext"]
    assert rows["lean:OporaHub.Votes.no_repost"]["commitSha"] == SHA
    assert rows["tlc:PrLoop-MergeOnce"]["status"] == "checked" and rows["tlc:PrLoop-MergeOnce"]["trust"] == "agent-reported"
    assert rows["lean:OporaHub.Votes.posted_iff"]["status"] == "unchecked"  # not in this (partial) audit
    assert document["counts"]["proved"] == 3 and document["allowedAxioms"] == ["Classical.choice", "Quot.sound", "propext"]
