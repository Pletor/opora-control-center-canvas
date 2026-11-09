"""Draft writes use native authority, CAS, persistent replay and truthful failure evidence."""
from copy import deepcopy
import pytest
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.editor.node.test_drawings import ELEMENT
from backend.canvas.payload_errors import NextStep


def test_drawing_native_revision_replay_conflict_and_no_acceptance(setup):
    client, service, auth = setup
    data = {"layer": "", "expected_revision": 0, "scene": {"elements": [ELEMENT]}}
    first = call(client, auth, "canvas_routes.save_drawing", data, "drawing")
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["verified"] and result["acceptedHead"] is None
    assert client.get("/api/drawing", params={**SCOPE, "layer": ""}).json() == result["result"]
    assert call(client, auth, "canvas_routes.save_drawing", data, "drawing").json() == result
    assert call(client, auth, "canvas_routes.save_drawing", {**data, "scene": {"elements": []}}, "drawing").status_code == 409
    assert call(client, auth, "canvas_routes.save_drawing", data, "stale").status_code == 409
    assert service.db_for("draft").execute("SELECT COUNT(*) FROM canvas_operation_receipts WHERE operation_id='stale'").fetchone()[0] == 0
    assert call(client, auth, "canvas_routes.save_drawing", {**data, "expected_revision": 1}, "stale").status_code == 200
    assert OporaGraphProposals(service).context(**SCOPE)["acceptedHead"] is None


def test_positions_only_xy_preserves_accepted_graph_authority(setup):
    client, service, auth = setup
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)  # Human fixture acceptance; operation itself only moves shared coordinates.
    node = item["refs"]["new"]
    before = deepcopy(service.view("draft", "draft"))
    head = native.context(**SCOPE)["acceptedHead"]
    data = {"digest": before["digest"], "positions": [{"id": node, "x": 100.4, "y": 80.6}]}
    response = call(client, auth, "canvas_routes.graph_positions", data, "positions")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["verified"] and result["acceptedHead"] == head
    assert result["result"]["positions"] == [{"id": node, "x": 100, "y": 81}]
    assert call(client, auth, "canvas_routes.graph_positions", data, "positions").json() == result
    after = service.view("draft", "draft")
    expected = before["graph"]
    next(n for n in expected["nodes"] if n["id"] == node).update(x=100, y=81)
    assert after["graph"] == expected and native.context(**SCOPE)["acceptedHead"] == head
    bad = {"digest": after["digest"], "positions": [{"id": node, "x": 0, "y": 0, "parentId": "foreign"}]}
    assert call(client, auth, "canvas_routes.graph_positions", bad, "bad").status_code == 409
    assert service.view("draft", "draft")["graph"] == expected
    assert call(client, auth, "canvas_routes.graph_positions", data, "stale").status_code == 409


def test_readback_failure_retains_pending_receipt_instead_of_duplicate_write(setup, monkeypatch):
    from backend.brain_opora.canvas_capabilities import draft_writes
    client, service, auth = setup
    def fail(*args):
        raise NextStep("Injected readback failure", code="operation_incomplete", hint="Inspect saved draft")
    monkeypatch.setattr(draft_writes, "_verify", fail)
    data = {"layer": "", "expected_revision": 0, "scene": {"elements": [ELEMENT]}}
    first = call(client, auth, "canvas_routes.save_drawing", data, "partial")
    assert first.status_code == 409 and first.json()["code"] == "operation_incomplete"
    assert service.drawing("draft", "draft", "")["revision"] == 1
    replay = call(client, auth, "canvas_routes.save_drawing", data, "partial")
    assert replay.status_code == 409 and replay.json()["code"] == "operation_incomplete"
    assert service.drawing("draft", "draft", "")["revision"] == 1


def test_native_drawing_asset_bytes_and_journal_revision_replay(setup):
    import base64
    client, service, auth = setup
    file = {"id": "native-image", "mimeType": "image/png",
            "dataURL": "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\noriginal").decode()}
    saved = call(client, auth, "canvas_routes.save_drawing_file", {"file": file}, "asset")
    assert saved.status_code == 200 and saved.json()["verified"], saved.text
    assert call(client, auth, "canvas_routes.save_drawing_file", {"file": file}, "asset").json() == saved.json()
    fetched = client.get("/api/drawing-files", params={**SCOPE, "ids": file["id"]}).json()["files"]
    assert len(fetched) == 1 and fetched[0]["dataURL"] == file["dataURL"]
    changed = {**file, "dataURL": "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nchanged").decode()}
    assert call(client, auth, "canvas_routes.save_drawing_file", {"file": changed}, "collision").status_code == 409
    native = OporaGraphProposals(service)
    item = proposal(native)
    accept(native, item)
    node = item["refs"]["new"]
    data = {"node": node, "day": "2026-11-08", "expected_revision": 0, "text": "Verified work journal"}
    journal = call(client, auth, "node_routes.save_node_journal", data, "journal")
    assert journal.status_code == 200 and journal.json()["verified"], journal.text
    assert call(client, auth, "node_routes.save_node_journal", data, "journal").json() == journal.json()
    assert client.get("/api/node-journal", params={**SCOPE, "node": node, "day": data["day"]}).json() == journal.json()["result"]
    assert call(client, auth, "node_routes.save_node_journal", data, "stale-journal").status_code == 409
    assert call(client, auth, "node_routes.save_node_journal", {**data, "node": "foreign"}, "foreign-journal").status_code == 409
    assert native.context(**SCOPE)["acceptedHead"] == journal.json()["acceptedHead"]
