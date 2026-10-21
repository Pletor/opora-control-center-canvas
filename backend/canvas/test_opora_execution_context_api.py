"""HTTP negotiation and independently versioned budget/sparse combinations."""
import pytest
from fastapi.testclient import TestClient

from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.app.factory import create_app
from backend.canvas.opora_execution_budgets import ExecutionBudgets
from backend.canvas.test_opora_changesets import HUMAN, SCOPE
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_execution_context import claimed, prepared
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_executions import credentials
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414

BASE = "/api/oporahub/executions"


def test_post_prepare_claim_heartbeat_result_http_and_identity(sparse, monkeypatch):
    graphs, _, refs = sparse
    app = create_app(graphs.service.root)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        payload = {**SCOPE, "nodeId": refs["a"], "contextProtocolVersion": 2}
        client.cookies.clear()
        response = client.post(BASE + "/context", json=payload, headers={"Origin": "http://127.0.0.1:8740"})
        assert response.status_code == 428, response.text
        # The legacy header parser supplies default name 'agent'; directly exercise
        # a middleware identity missing its name without changing that global contract.
        with monkeypatch.context() as patch:
            patch.setattr("backend.app.human_session.HumanSession.actor", lambda *_: ("agent", ""))
            response = client.post(BASE + "/context", json=payload, headers=AGENT)
            assert response.status_code == 409, response.text
            assert "identified" in response.json()["error"]
        response = client.post(BASE + "/context", json=payload, headers=AGENT)
        assert response.status_code == 200, response.text
        context = response.json()
        request = {**payload, "requestId": "http", "ttlSeconds": 60,
                   "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"]}
        response = client.post(BASE + "/claim", json=request, headers=AGENT)
        assert response.status_code == 200, response.text
        record = response.json()
        assert record["contextValidation"]["acceptedRevisionsChecked"] == 1
        node = refs["b"]
        with app.state.service.db_for("draft") as db:
            db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", node, 1, "Other", "now"))
        response = client.post(BASE + f'/{record["executionId"]}/heartbeat', headers=AGENT,
                               json={**credentials(record), "ttlSeconds": 60})
        assert response.status_code == 200, response.text
        assert response.json()["contextValidation"]["liveTransitionsChecked"] == 1
        result = {**credentials(record), "requestId": "http-result", "result": {"summary": "Ready"}}
        response = client.post(BASE + f'/{record["executionId"]}/results', headers=AGENT, json=result)
        assert response.status_code == 200, response.text
        assert response.json()["contextProtocolVersion"] == 2
        assert client.post(BASE + f'/{record["executionId"]}/results', headers=AGENT, json=result).json() == response.json()


@pytest.mark.parametrize("budget_v2", [False, True])
def test_context_version_independent_from_budget_and_origin_unchanged(sparse, budget_v2):
    graphs, authority, refs = sparse
    extra = {}
    if budget_v2:
        budgets = ExecutionBudgets(authority.canvas)
        accepted = authority.context(**SCOPE, node=refs["a"])["acceptedHead"]
        policy = budgets.configure({**SCOPE, "nodeId": refs["a"], "expectedPolicyHead": None,
            "expectedAcceptedHead": accepted, "requestId": "policy", "limits": {
                "maxRunSeconds": 60, "maxAttempts": 3, "maxRepairRounds": 1}}, HUMAN)
        extra = {"expectedBudgetPolicyHead": policy["policyHead"], "previousExecutionId": None}
    record = claimed(sparse, **extra)
    assert record.get("executionProtocolVersion", 1) == (2 if budget_v2 else 1)
    assert record["contextProtocolVersion"] == 2
    next_revision = accept_spec(graphs.service, propose_spec(graphs.service, nodes=(refs["b"],)), record["acceptedRevision"])
    renewed = authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 300})
    assert renewed["contextValidation"]["checkedAcceptedRevision"] == next_revision["id"]
    assert renewed["assignmentDigest"] == record["assignmentDigest"]
    assert renewed["assignment"] == record["assignment"]
    if budget_v2:
        assert renewed["budget"] == record["budget"]
        assert renewed["expiresAt"] == record["budget"]["runDeadlineAt"]
    receipt = authority.submit(record["executionId"], {**credentials(record), "requestId": "done", "result": {"summary": "Done"}})
    assert receipt["contextProtocolVersion"] == 2
    assert receipt["contextValidation"]["originAcceptedRevision"] == record["acceptedRevision"]


def test_registry_metadata_aba_revokes_original_execution(sparse):
    _, authority, _ = sparse
    record = claimed(sparse)
    canvas = authority.canvas
    with canvas.registry_lock, canvas.db:
        original = canvas.db.execute("SELECT name FROM builtin_project_metadata WHERE project_id='draft'").fetchone()[0]
        canvas.db.execute("UPDATE builtin_project_metadata SET name='Temporary' WHERE project_id='draft'")
        canvas.db.execute("UPDATE builtin_project_metadata SET name=? WHERE project_id='draft'", (original,))
    assert prepared(sparse)["contextVersion"] != record["assignment"]["contextVersion"]
    with pytest.raises(ValueError, match="binding changed"):
        authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
