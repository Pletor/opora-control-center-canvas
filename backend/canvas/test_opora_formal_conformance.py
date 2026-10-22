"""`formal/conformance` check runs become execution-bound `conformance` evidence (never ci-verified)."""
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_execution_conformance import INVARIANTS
from backend.canvas.opora_formal_checks import CHECKS, EVIDENCE_KINDS, needs_annotations
from backend.canvas.opora_formal_ledger import ledger
from backend.canvas.opora_formal_profiles import CONFORMANCE_INVARIANTS
from backend.canvas.test_opora_execution_pull_requests import SHA
from backend.canvas.test_opora_formal_checks import check, ingest, snapshot
from backend.canvas.test_opora_formal_checks import linked as linked  # noqa: PLC0414
from backend.canvas.test_opora_formal_checks import world_fixture as world_fixture  # noqa: PLC0414
from backend.canvas.test_opora_formal_complete import Formal, poll, records
from backend.integrations.github_formal_check_reader import CHECK_NAMES

NAME = "formal/conformance"


def investigations(service, scope):
    return [item for item in AgentState(service).read(**scope)["actions"] if item["verb"] == "verification.investigate"]


def test_conformance_is_a_connected_kind_without_trusted_twin():
    assert CONFORMANCE_INVARIANTS == tuple(INVARIANTS)
    assert CHECKS[NAME] == ("conformance", False) and NAME in CHECK_NAMES
    assert EVIDENCE_KINDS["conformance"] == {"check": NAME, "trustedCheck": None, "status": "connected"}
    assert not needs_annotations(check(name=NAME)) and not needs_annotations(check(name=NAME, conclusion="success"))


def test_evidence_import_records_conformance_bound_to_execution_and_sha(linked):
    service, scope, record = linked
    assert len(ingest(service, scope, snapshot(check(41, conclusion="success", name=NAME)))) == 1
    [item] = records(service, scope)
    assert item["executionId"] == record["executionId"] and item["nodeId"] == "card"
    assert item["acceptedRevision"] == record["acceptedRevision"]
    assert item["verification"]["tool"]["name"] == "conformance"
    assert item["verification"]["source"] == {"repository": "owner/repo", "commitSha": SHA}
    assert item["origin"]["checkName"] == NAME and item["origin"]["evidenceKind"] == "conformance"
    assert item["trust"] == "agent-reported" and item["independentlyVerified"] is False
    assert item["report"]["outcome"] == "passed"
    assert set(item["report"]["checkedClaims"]) == set(INVARIANTS)


def test_failed_conformance_needs_attention_until_conformance_passes_again(linked):
    service, scope, record = linked
    ingest(service, scope, snapshot(check(42, name=NAME)))
    [action] = investigations(service, scope)
    assert action["targetId"] == record["executionId"] and action["preconditions"]["outcome"] == "failed"
    ingest(service, scope, snapshot(check(43, conclusion="success", sha="d" * 40)))  # A TLC pass is another kind.
    assert len(investigations(service, scope)) == 1
    ingest(service, scope, snapshot(check(44, conclusion="success", sha="d" * 40, name=NAME)))
    assert investigations(service, scope) == []


def test_loop_records_conformance_without_annotations_or_provenance(linked):
    service, scope, _ = linked
    reader = Formal([check(51, name=NAME)])
    poll(service, reader)
    assert reader.calls == ["checks"]
    [item] = records(service, scope)
    assert item["report"]["outcome"] == "failed" and item["origin"]["observedVia"] == "execution-pr-loop"
    assert item["trust"] == "agent-reported" and item["origin"]["provenance"] is None


def test_ledger_lists_conformance_invariants(linked):
    service, scope, _ = linked
    rows = {row["id"]: row for row in ledger(service, **scope)["entries"]}
    assert {rows[f"conformance:{name}"]["status"] for name in INVARIANTS} == {"unchecked"}
    ingest(service, scope, snapshot(check(61, conclusion="success", name=NAME)))
    rows = {row["id"]: row for row in ledger(service, **scope)["entries"]}
    row = rows["conformance:OneActiveOwner"]
    assert row["status"] == "checked" and row["declared"] is True and row["commitSha"] == SHA
    assert row["tool"] == "conformance" and row["checkName"] == NAME
    assert rows["tlc:OneActiveOwner"]["status"] == "unchecked"
