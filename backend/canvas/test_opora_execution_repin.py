"""Re-pin po vlastní dávce plánu: nový neměnný pin, původní zůstává; bez živého běhu dávka beze změny."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_execution_start_deliver import AGENT, ready, start
from backend.app.test_local_merge_autonomy import ok
from backend.canvas.opora_execution_repin import plan_with_repin
from backend.canvas.test_canvas_plan import ORIGIN
from database.repositories import opora_execution_contexts as private


def test_without_live_executions_the_plan_is_untouched(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _, scope, _ = ready(client, tmp_path)
        canvas = client.app.state.service
        assert plan_with_repin(canvas, {**scope}, "agent:nikdo", lambda: {"ok": 1}) == {"ok": 1}
        assert plan_with_repin(canvas, {**scope, "dryRun": True}, "agent:t", lambda: {"ok": 2}) == {"ok": 2}


def test_repin_adds_a_new_pin_and_keeps_the_origin(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        identifier = started["executionId"]
        digest = ok(client.get("/api/view", params=scope))["digest"]
        plan = {"nodes": [{"ref": "pod", "kind": "node", "parent": "@" + card, "name": "Podkarta"}],
                "edges": [], "decisions": []}
        assert ok(client.post("/api/canvas-plan", headers=AGENT,
                              json={**scope, "digest": digest, "plan": plan}))["rePinned"] == [identifier]
        db = client.app.state.service.db_for(scope["project"])
        with db:
            db.execute("BEGIN")
            origin = private.read(db, scope["project"], scope["workspace"], identifier)
            fresh = private.read(db, scope["project"], scope["workspace"], identifier + ":repin1")
        assert origin["contextVersion"] == started["contextVersion"] != fresh["contextVersion"]
        record = ok(client.get("/api/oporahub/executions", params={**scope, "nodeId": card}, headers=AGENT))["executions"][0]
        assert record["contextRepins"] == 1 and record["state"] == "running", record
