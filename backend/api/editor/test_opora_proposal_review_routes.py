"""Actual factory API review gates all four native acceptance routes."""
import pytest
from fastapi.testclient import TestClient

from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.canvas.test_opora_proposal_acceptance_guard import native

BASE = "/api/oporahub/proposal-reviews"


@pytest.mark.parametrize("kind", ["spec", "graph-addition", "graph-change", "content"])
def test_api_policy_event_actor_ack_native_acceptance_and_exact_receipt(sparse, kind):
    _, authority, _ = sparse
    item, _ = native(sparse, kind)
    app = create_app(authority.canvas.root)
    with TestClient(app, base_url=ORIGIN) as client:
        policy_body = {**SCOPE, "expectedPolicyHead": None, "enabled": True,
                       "rules": {"requireAcknowledgementFrom": "standard", "blockOpenFindings": True}}
        assert client.post(BASE + "/policy", headers=AGENT, json=policy_body).status_code == 409
        response = client.post(BASE + "/policy", headers=HEADERS, json=policy_body)
        assert response.status_code == 200, response.text
        policy = response.json()
        query = {**SCOPE, "proposalKind": kind, "proposalId": item["id"]}
        context = client.get(BASE, params=query, headers=HEADERS).json()
        assert not context["canAccept"] and context["canAcknowledge"] and context["canResolve"]
        assert context["risk"]["level"] in {"elevated", "critical"}
        payload = {**query, "expectedReviewHead": None, "idempotencyKey": "note",
                   "body": {"type": "comment", "message": "Read exact immutable proposal", "anchor": "/subject"}}
        note = client.post(BASE + "/events", headers=AGENT, json=payload)
        assert note.status_code == 200, note.text
        assert client.post(BASE + "/events", headers=AGENT, json=payload).json() == note.json()
        ack = {**query, "expectedReviewHead": note.json()["id"], "idempotencyKey": "risk-ack",
               "body": {"type": "ack", "policyId": policy["id"], "riskDigest": context["risk"]["digest"],
                        "parentAcceptedHead": context["acceptedHead"]}}
        assert client.post(BASE + "/events", headers=AGENT, json=ack).status_code == 409
        acknowledged = client.post(BASE + "/events", headers=HEADERS, json=ack)
        assert acknowledged.status_code == 200, acknowledged.text
        if kind == "spec":
            url = "/api/oporahub/changesets/" + item["id"] + "/accept"
            body = {**SCOPE, "expectedAcceptedHead": item["parentRevision"]}
        elif kind == "content":
            url = "/api/oporahub/content-changes/" + item["id"] + "/accept"
            body = {**SCOPE, "expectedAcceptedHead": item["parentRevision"], "reviewedProposalId": item["id"],
                    "adoptBaseContentDigest": item["baseContentDigest"] if item["requiresBaseContentAdoption"] else None}
        else:
            url = "/api/oporahub/graph-proposals/" + item["id"] + "/accept"
            body = {**SCOPE, "expectedAcceptedHead": item["parentRevision"], "expectedGraphDigest": item["graphDigest"],
                    "adoptBaseGraphDigest": item["graphDigest"] if item.get("requiresBaseAdoption") else None}
            if kind == "graph-change":
                body["reviewedChangesId"] = item["id"]
        accepted = client.post(url, headers=HEADERS, json=body)
        assert accepted.status_code == 200, accepted.text
        receipt = client.get(BASE + "/receipts/" + accepted.json()["id"], params=SCOPE, headers=HEADERS).json()["receipt"]
        assert receipt["ackId"] == acknowledged.json()["id"] and receipt["proposalKind"] == kind
        history = client.get(BASE, params=query, headers=HEADERS).json()
        assert history["acceptedRevision"] == accepted.json()["id"] and history["receipt"] == receipt
        assert not history["canAcknowledge"] and history["canResolve"]
        client.cookies.clear()
        assert client.get(BASE, params=query).status_code == 428


@pytest.mark.parametrize("workspace", ["main", "architecture", "unknown-workspace"])
def test_readonly_unknown_scope_has_no_policy_or_review_mutation_capability(sparse, workspace):
    _, authority, _ = sparse
    item, _ = native(sparse, "spec")
    app = create_app(authority.canvas.root)
    scope = {**SCOPE, "workspace": workspace}
    with TestClient(app, base_url=ORIGIN) as client:
        context = client.get(BASE + "/policy", headers=HEADERS, params=scope)
        assert context.status_code == 200, context.text
        assert context.json()["readOnly"] and not context.json()["canConfigure"]
        configured = client.post(BASE + "/policy", headers=HEADERS, json={**scope, "expectedPolicyHead": None,
            "enabled": True, "rules": {"requireAcknowledgementFrom": "standard", "blockOpenFindings": True}})
        assert configured.status_code == 409 and "writable" in configured.json()["error"]
        for body in ({"type": "comment", "message": "Cannot write", "anchor": ""},
                     {"type": "resolve", "targetEventId": "a" * 40, "resolution": "resolved", "reason": "Cannot resolve"},
                     {"type": "ack", "policyId": "a" * 40, "riskDigest": "a" * 64, "parentAcceptedHead": item["parentRevision"]}):
            response = client.post(BASE + "/events", headers=HEADERS, json={**scope, "proposalKind": "spec", "proposalId": item["id"],
                "expectedReviewHead": None, "idempotencyKey": body["type"], "body": body})
            assert response.status_code == 409 and "writable" in response.json()["error"]
