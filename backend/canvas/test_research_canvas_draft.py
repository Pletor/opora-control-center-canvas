"""Initial research planning persists a native draft, never synthesizes acceptance."""
from copy import deepcopy

import pytest

from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.canvas.research_canvas_draft import verify
from backend.canvas.test_opora_graph_complete import full_plan
from backend.editor.node.test_removals import HEADERS, SCOPE
from backend.editor.research.planning_source import pins
from backend.editor.research.test_continuations import imported


def test_initial_native_research_draft_receipt_full_readback_and_replay(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, imported_result, _ = imported(client, accepted_context=False)
        continuation = imported_result["continuation"]
        service = client.app.state.service
        context = client.get("/api/oporahub/graph-proposals/context", params=SCOPE).json()
        body = {**SCOPE, "digest": context["graphDigest"], "plan": full_plan(),
                "researchSource": pins(continuation), "operationId": continuation["operationId"]}
        from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
        body["plan"]["extend"] = [{"node": "@s1", "expectedRevision": DesktopV3State(service).current(**SCOPE)["revision"],
                                    "text": {"expectedRevision": 0, "text": "Existing card evidence"}}]
        response = client.post("/api/canvas-plan", headers=HEADERS, json=body)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["acceptedHeadAtWrite"] is None and result["researchSource"] == body["researchSource"]
        assert verify(service, **SCOPE, response=result) == {**result["canvasDraft"], "acceptedHeadAtReadback": None}
        assert "s1" in result["canvasDraft"]["affectedNodeIds"] and "s1" not in result["canvasDraft"]["nodeIds"]
        assert client.post("/api/canvas-plan", headers=HEADERS, json=body).json() == result
        assert client.get("/api/oporahub/graph-proposals/context", params=SCOPE).json()["acceptedHead"] is None
        from backend.canvas.test_opora_changesets import baseline
        accepted = baseline(service)  # Specifications only: does not prove whole draft acceptance.
        checked = verify(service, **SCOPE, response=result)
        assert checked["acceptedHeadAtReadback"] == accepted["id"]
        assert "acceptedAtReadback" not in checked
        node = result["refs"]["source"]
        changed = client.post("/api/node-text", headers=HEADERS,
            json={**SCOPE, "node": node, "expected_revision": 1, "text": "Concurrent document edit"})
        assert changed.status_code == 200, changed.text
        with pytest.raises(ValueError, match="no longer matches"):
            verify(service, **SCOPE, response=result)
        # Immutable response survives changed live documents; the verifier does not falsely acknowledge it.
        assert client.post("/api/canvas-plan", headers=HEADERS, json=body).json() == result


def test_forged_initial_source_or_accepted_context_cannot_write(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, result, _ = imported(client)
        context = client.get("/api/oporahub/graph-proposals/context", params=SCOPE).json()
        body = {**SCOPE, "digest": context["graphDigest"], "plan": full_plan(),
                "researchSource": pins(result["continuation"]), "operationId": "initial-invalid"}
        assert client.post("/api/canvas-plan", headers=HEADERS, json=body).status_code == 409
        bad = deepcopy(body)
        bad["researchSource"]["researchRevision"] += 1
        assert client.post("/api/canvas-plan", headers=HEADERS, json=bad).status_code == 409
        assert client.get("/api/oporahub/graph-proposals/context", params=SCOPE).json()["graphDigest"] == context["graphDigest"]
        assert client.app.state.service.db_for("draft").execute(
            "SELECT COUNT(*) FROM canvas_operation_receipts WHERE operation_id='initial-invalid'").fetchone()[0] == 0


@pytest.mark.parametrize("wrong", ["missing", "stale", "scope", "shape"])
@pytest.mark.parametrize("native", ["canvas-plan", "proposal"])
def test_invalid_research_pins_are_native_http_errors_without_writes(tmp_path, wrong, native):
    with client_with_sector(tmp_path) as client:
        _, result, _ = imported(client, accepted_context=native == "proposal")
        context = client.get("/api/oporahub/graph-proposals/context", params=SCOPE).json()
        source = pins(result["continuation"])
        if wrong == "missing":
            source["continuationId"] = "missing-continuation"
        elif wrong == "stale":
            source["researchRevision"] += 1
        elif wrong == "scope":
            # Valid receipt identity from another scope must not resolve here.
            db = client.app.state.service.db_for("draft")
            with db:
                db.execute("UPDATE research_continuations SET workspace_id='foreign' WHERE id=?", (source["continuationId"],))
        else:
            source["researchRevision"] = "1"
        body = {**SCOPE, "operationId": "invalid-pins", "plan": full_plan()}
        if native == "proposal":
            body.update(subject="Invalid source", parentRevision=context["acceptedHead"],
                        expectedGraphDigest=context["graphDigest"])
            body["plan"].update(draftVersion=3, researchSource=source)
            path = "/api/oporahub/graph-proposals"
        else:
            body.update(digest=context["graphDigest"], researchSource=source)
            path = "/api/canvas-plan"
        response = client.post(path, headers=HEADERS, json=body)
        assert response.status_code == (422 if wrong == "shape" else 409), response.text
        assert client.get("/api/oporahub/graph-proposals/context", params=SCOPE).json() == context
        assert client.app.state.service.db_for("draft").execute(
            "SELECT COUNT(*) FROM canvas_operation_receipts WHERE operation_id='invalid-pins'").fetchone()[0] == 0
