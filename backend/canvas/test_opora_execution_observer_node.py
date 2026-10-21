"""The observer accepts the same real node identities as execution authority."""
import json

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.opora_execution_budgets import ExecutionBudgets
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_canvas_plan import ORIGIN
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import HUMAN, SCOPE, baseline
from backend.canvas.test_opora_execution_observers import CONFIG, post


def test_legal_eighty_character_leading_underscore_node_has_real_budget_two_http_intent(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_EXECUTION_OBSERVERS", json.dumps({"broker": CONFIG}))
    app = create_app(tmp_path / "data")
    canvas = app.state.service
    node_id = "_" + "n" * 79
    graph = canvas.view("draft", "draft")
    canvas.save_graph("draft", "draft", {"nodes": [node(node_id)], "edges": []}, graph["digest"])
    baseline(canvas)
    authority = ExecutionResults(canvas)
    context = authority.context(**SCOPE, node=node_id)
    policy = ExecutionBudgets(canvas).configure({**SCOPE, "nodeId": node_id, "expectedPolicyHead": None,
        "expectedAcceptedHead": context["acceptedHead"], "requestId": "policy", "limits": {
            "maxRunSeconds": 60, "maxAttempts": 3, "maxRepairRounds": 1}}, HUMAN)
    lease = authority.claim({**SCOPE, "nodeId": node_id, "requestId": "claim", "ttlSeconds": 60,
        "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"],
        "expectedBudgetPolicyHead": policy["policyHead"], "previousExecutionId": None}, "agent:worker")
    body = {**SCOPE, **{key: lease[key] for key in ("executionId", "nodeId", "epoch", "acceptedRevision", "assignmentDigest", "budget")},
            "requestId": "intent", "contextProtocolVersion": 1, "contextVersion": lease["assignment"]["contextVersion"],
            "executionProtocolVersion": 2, "authorityDeadlineAt": lease["budget"]["runDeadlineAt"],
            "provider": CONFIG["provider"], "repository": {"url": "https://github.com/example/repo", "commitSha": "a" * 40},
            "agentId": "agent", "agentVersion": 1, "environmentId": "env",
            "environmentDigest": "a" * 64, "configurationDigest": "b" * 64, "maxListCostCents": "100"}
    with TestClient(app, base_url=ORIGIN) as client:
        response = post(client, "/intents", body)
        assert response.status_code == 200, response.text
        assert response.json()["nodeId"] == node_id and response.json()["authorityActive"]
