"""One accepted task changes multiple typed elements under one execution identity."""
from copy import deepcopy

import pytest

from backend.canvas.execution_write_set import affected_ids
from backend.canvas.opora_execution_context import prepare
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import baseline, service
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_graph_card import node

SCOPE = {"project": "draft", "workspace": "draft"}


def configure(service, affected=None):
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    graph["nodes"].extend([{**node(identifier), "element": {"kind": kind}}
                           for identifier, kind in (("login", "page"), ("identity", "service"), ("tenant", "entity"))])
    graph["edges"].append({"id": "identity_tenant", "source": "identity", "target": "tenant", "port": "rule",
                           "relation": "requires", "requirement": {"readiness": "design", "revision": 0}})
    service.save_graph("draft", "draft", graph, view["digest"])
    service.node_spec("draft", "draft", "a", {**SCOPE, "node": "a", "expected_revision": 0,
        "fields": {"goal": "Functional login across UI, API and data", "non_goals": "", "acceptance": "Isolation works",
                   "affectedNodeIds": affected if affected is not None else ["login", "identity", "tenant"]}})
    baseline(service)
    graphs = OporaGraphProposals(service)
    accept(graphs, proposal(graphs))
    return ExecutionResults(service)


def start(authority, protocol):
    if protocol == 2:
        context = prepare(authority, {**SCOPE, "nodeId": "a", "contextProtocolVersion": 2})
    else:
        context = authority.context(**SCOPE, node="a")
    return authority.claim({**SCOPE, "nodeId": "a", "requestId": "one-task", "ttlSeconds": 60,
        "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"],
        **({"contextProtocolVersion": 2} if protocol == 2 else {})}, "agent:builder")


@pytest.mark.parametrize("protocol", [1, 2])
def test_one_execution_pins_three_affected_elements_and_exact_result(service, protocol):
    authority = configure(service)
    before = service.view("draft", "draft")["graph"]
    execution = start(authority, protocol)
    assignment = execution["assignment"]
    assert [item["nodeId"] for item in assignment["affectedElements"]] == ["identity", "login", "tenant"]
    assert {item["nodeId"] for item in assignment["documents"]} >= {"a", "identity", "login", "tenant"}
    assert assignment["requiredInputs"][0]["nodeId"] == "tenant"
    assert all(item["documentDigest"] for item in assignment["affectedElements"])
    if protocol == 2:
        assert len(assignment["specification"]["affectedScopes"]) == 3
    receipt = authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
        "requestId": "delivered", "result": {"summary": "UI, API and data changed together"}})
    assert receipt["executionId"] == execution["executionId"]
    assert receipt["acceptedRevision"] == execution["acceptedRevision"]
    assert receipt["assignmentDigest"] == execution["assignmentDigest"]
    db = service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_executions").fetchone()[0] == 1
    assert service.view("draft", "draft")["graph"] == before


@pytest.mark.parametrize("protocol", [1, 2])
def test_changed_affected_contract_rejects_result_without_mutating_pin(service, protocol):
    authority = configure(service)
    execution = start(authority, protocol)
    saved = deepcopy(execution["assignment"])
    service.node_spec("draft", "draft", "tenant", {**SCOPE, "node": "tenant", "expected_revision": 0,
        "fields": {"goal": "Changed tenant model", "non_goals": "", "acceptance": ""}})
    with pytest.raises(ValueError):
        authority.submit(execution["executionId"], {**SCOPE, "token": execution["token"], "epoch": execution["epoch"],
            "requestId": "stale", "result": {"summary": "Old contract"}})
    assert authority.read_assignment(execution["executionId"], **SCOPE, token=execution["token"])["assignment"] == saved


@pytest.mark.parametrize("value", [[], ["a", "a"], ["bad/id"], [None], "a"])
def test_invalid_affected_identity_set(value):
    with pytest.raises(ValueError):
        affected_ids({"affectedNodeIds": value})


@pytest.mark.parametrize("protocol", [1, 2])
def test_unknown_affected_element_cannot_start_execution(service, protocol):
    authority = configure(service, ["missing"])
    with pytest.raises(ValueError):
        start(authority, protocol)
    assert service.db_for("draft").execute("SELECT COUNT(*) FROM opora_executions").fetchone()[0] == 0
