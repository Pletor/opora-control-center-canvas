"""Actual HTTP content review uses immutable IDs and human-only acceptance."""
from fastapi.testclient import TestClient

from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from database.repositories.opora_changesets import ChangesetRepository

BASE = "/api/oporahub/content-changes"


def test_full_api_proposal_detail_diff_adoption_accept_replay(sparse):
    graphs, _, refs = sparse
    app = create_app(graphs.service.root)
    with TestClient(app, base_url=ORIGIN) as client:
        head = ChangesetRepository(app.state.service.db_for("draft"), "draft", "draft").head()
        response = client.post(BASE, headers=AGENT, json={**SCOPE, "expectedAcceptedHead": head, "subject": "Review content",
            "changes": [{"kind": "text", "target": refs["a"], "field": "text", "value": "Accepted text"},
                        {"kind": "drawing", "target": "", "field": "scene", "value": {"elements": []}},
                        {"kind": "config", "target": refs["a"], "field": "materials", "value": []}]})
        assert response.status_code == 200, response.text
        item = response.json()
        listing = client.get(BASE, params=SCOPE, headers=AGENT).json()
        assert listing["items"][0]["id"] == item["id"] and not listing["canAccept"]
        assert "baseContent" not in listing["items"][0]
        detail = client.get(BASE + "/" + item["id"], params=SCOPE, headers=HEADERS).json()
        assert detail["proposal"] == item and detail["canAccept"] and detail["accepted"] is None
        assert all("before" in change and "acceptedBefore" in change for change in item["changes"])
        payload = {**SCOPE, "expectedAcceptedHead": head, "reviewedProposalId": item["id"], "adoptBaseContentDigest": item["baseContentDigest"]}
        assert client.post(BASE + "/" + item["id"] + "/accept", headers=AGENT, json=payload).status_code == 409
        response = client.post(BASE + "/" + item["id"] + "/accept", headers=HEADERS, json=payload)
        assert response.status_code == 200, response.text
        assert client.post(BASE + "/" + item["id"] + "/accept", headers=HEADERS, json=payload).json() == response.json()
        assert client.get(BASE + "/" + item["id"], params=SCOPE, headers=HEADERS).json()["accepted"] == response.json()["id"]


def test_content_body_has_its_own_bound_above_default_two_megabytes(sparse):
    graphs, _, refs = sparse
    app = create_app(graphs.service.root)
    with TestClient(app, base_url=ORIGIN) as client:
        head = ChangesetRepository(app.state.service.db_for("draft"), "draft", "draft").head()
        scene = {"elements": [{"id": f"text-{position}", "type": "text", "text": "x" * 20000,
                               "x": 0, "y": 0, "width": 100, "height": 100} for position in range(55)]}
        changes = [{"kind": "drawing", "target": refs[node], "field": "scene", "value": scene} for node in ("a", "b")]
        response = client.post(BASE, headers=AGENT, json={**SCOPE, "expectedAcceptedHead": head,
            "subject": "Two complete drawings", "changes": changes})
        assert response.status_code == 200, response.text[:300]
        assert len(response.request.content) > 2 * 1024 * 1024
        oversized = client.post(BASE, headers=AGENT, json={"padding": "x" * (13 * 1024 * 1024)})
        assert oversized.status_code == 413
