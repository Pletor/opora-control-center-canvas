"""Real sparse execution lifecycle, private pins, and compatibility fences."""
import copy
import json

import pytest

from backend.canvas.opora_execution_context import prepare
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_execution_lineage import graph_change
from backend.canvas.test_opora_executions import credentials
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.canvas.test_opora_graph_proposals import accept, proposal
from database.repositories import opora_execution_contexts as private


@pytest.fixture
def sparse(empty_graphs):
    graphs = empty_graphs
    item = proposal(graphs, plan={"nodes": [{"ref": "a", "kind": "node", "name": "A"},
                                           {"ref": "b", "kind": "node", "name": "B"}]})
    accept(graphs, item)
    return graphs, ExecutionResults(graphs.service), item["refs"]


def prepared(sparse, node="a"):
    _, authority, refs = sparse
    return prepare(authority, {**SCOPE, "nodeId": refs[node], "contextProtocolVersion": 2})


def claimed(sparse, node="a", request="claim", context=None, **extra):
    _, authority, refs = sparse
    context = context or prepared(sparse, node)
    return authority.claim({**SCOPE, "nodeId": refs[node], "contextProtocolVersion": 2,
                            "requestId": request, "ttlSeconds": 60,
                            "expectedAcceptedHead": context["acceptedHead"],
                            "expectedContextVersion": context["contextVersion"], **extra}, "agent:worker")


def test_prepare_has_no_lease_attempt_or_private_pin(sparse):
    _, authority, _ = sparse
    first = prepared(sparse)
    assert first["available"] and first["contextProtocolVersion"] == 2
    assert prepared(sparse) == first
    db = authority.canvas.db_for("draft")
    for table in ("opora_execution_context_pins", "opora_execution_epochs", "card_leases", "opora_executions"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_unrelated_accepted_and_live_changes_keep_origin_through_result(sparse):
    graphs, authority, refs = sparse
    first = claimed(sparse)
    origin_assignment = copy.deepcopy(first["assignment"])
    proposal = propose_spec(graphs.service, nodes=(refs["b"],))
    current = accept_spec(graphs.service, proposal, first["acceptedRevision"])
    with authority.canvas.db_for("draft") as db:
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", refs["b"], 1, "Unrelated", "now"))
    heartbeat = authority.heartbeat(first["executionId"], {**credentials(first), "ttlSeconds": 60})
    assert heartbeat["assignment"] == origin_assignment
    assert heartbeat["assignmentDigest"] == first["assignmentDigest"]
    assert heartbeat["contextValidation"]["checkedAcceptedRevision"] == current["id"]
    assert heartbeat["contextValidation"]["acceptedRevisionsChecked"] == 2
    assert heartbeat["contextValidation"]["liveTransitionsChecked"] >= 2
    payload = {**credentials(first), "requestId": "result", "result": {"summary": "Implemented"}}
    receipt = authority.submit(first["executionId"], payload)
    assert receipt["acceptedRevision"] == first["acceptedRevision"]
    assert receipt["contextProtocolVersion"] == 2
    assert receipt["contextValidation"]["checkedAcceptedRevision"] == current["id"]
    assert receipt == authority.submit(first["executionId"], payload)
    assert claimed(sparse, context=prepared(sparse), request="different")["acceptedRevision"] == current["id"]


def test_live_aba_rejects_even_when_final_projection_matches(sparse):
    _, authority, refs = sparse
    first = claimed(sparse)
    db = authority.canvas.db_for("draft")
    with db:
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", refs["a"], 1, "Changed", "now"))
        db.execute("DELETE FROM node_text_revisions WHERE node_id=?", (refs["a"],))
    with pytest.raises(ValueError, match="scope changed"):
        authority.heartbeat(first["executionId"], {**credentials(first), "ttlSeconds": 60})
    # Replay remains authenticated/history-preserving even after eligibility is revoked.
    replay = claimed(sparse, context={"acceptedHead": first["acceptedRevision"], "contextVersion": first["assignment"]["contextVersion"]})
    assert replay["executionId"] == first["executionId"] and replay["state"] == "revoked"


def test_accepted_graph_aba_rejects(sparse):
    graphs, authority, refs = sparse
    first = claimed(sparse)
    graph_change(graphs, {"updateNodes": [{"id": refs["a"], "fields": {"name": "Changed"}}]})
    graph_change(graphs, {"updateNodes": [{"id": refs["a"], "fields": {"name": "A"}}]})
    with pytest.raises(ValueError):
        authority.heartbeat(first["executionId"], {**credentials(first), "ttlSeconds": 60})


def test_token_cas_unknown_versions_and_no_implicit_context_enrollment(sparse):
    _, authority, refs = sparse
    with pytest.raises(ValueError, match="binding"):
        claimed(sparse, context={"acceptedHead": "a" * 40, "contextVersion": "b" * 64})
    context = prepared(sparse)
    with pytest.raises(ValueError, match="changed before claim"):
        claimed(sparse, context={**context, "contextVersion": "b" * 64})
    for version in (1, 3, True, "2"):
        with pytest.raises(ValueError, match="protocol version"):
            prepare(authority, {**SCOPE, "nodeId": refs["a"], "contextProtocolVersion": version})
        with pytest.raises(ValueError, match="protocol version"):
            authority.claim({**SCOPE, "contextProtocolVersion": version}, "agent:worker")
    legacy = authority.context(**SCOPE, node=refs["a"])
    record = authority.claim({**SCOPE, "nodeId": refs["a"], "requestId": "legacy", "ttlSeconds": 60,
                              "expectedAcceptedHead": legacy["acceptedHead"], "expectedContextVersion": legacy["contextVersion"]}, "agent:worker")
    assert "contextProtocolVersion" not in record


def test_private_pin_and_secret_never_enter_public_record(sparse, monkeypatch):
    _, authority, refs = sparse
    secret = "api_key=sk-" + "a" * 45
    with authority.canvas.db_for("draft") as db:
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", refs["a"], 1, secret, "now"))
    record = claimed(sparse)
    pin = private.read(db, "draft", "draft", record["executionId"])
    assert secret in json.dumps(pin)
    outputs = [record, authority.read_assignment(record["executionId"], **SCOPE, token=record["token"]),
               authority.history(**SCOPE)]
    for output in outputs:
        raw = json.dumps(output)
        assert secret not in raw
        assert "schemaDigest" not in raw and '"snapshot"' not in raw and '"binding"' not in raw
    def missing(*args):
        raise ValueError("Private context origin is missing.")
    monkeypatch.setattr(private, "read", missing)
    with pytest.raises(ValueError, match="origin"):
        authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
