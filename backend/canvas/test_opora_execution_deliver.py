"""`deliver`: další krok podle toho, co chybí, a odmítnutí běhu, jehož kartu mezitím převzal jiný běh."""
import time

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_execution_start_deliver import OTHER, commit_card, deliver, ready, start
from backend.app.test_local_merge_autonomy import ok
from backend.canvas.opora_execution_deliver import next_step
from backend.canvas.test_canvas_plan import ORIGIN

RECORD = {"nodeId": "n1", "executionId": "e1"}


def test_next_step_follows_the_first_missing_requirement():
    assert next_step(RECORD, [], [], True, True)["verb"] == "pick"
    assert next_step(RECORD, ["gate_ready"], ["npm test"], False, True)["command"].endswith('--check "npm test=green"')
    assert next_step(RECORD, ["steps", "human_close"], [], False, True)["command"] == "opora_hub.py start --node n1"
    assert next_step(RECORD, ["journeys", "human_close"], [], False, True)["verb"] == "journey_run"
    assert next_step(RECORD, ["merged", "human_close"], [], False, True)["verb"] == "merge"
    # Jen uzavření chybí: kartu uzavře server sám (opora_card_auto_close), nikdo na ni nečeká.
    assert next_step(RECORD, ["human_close"], [], False, False)["verb"] == "pick"
    assert next_step(RECORD, ["human_close"], [], False, True)["verb"] == "pick"


def test_expired_lease_taken_over_by_another_actor_is_409(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        db = client.app.state.service.db_for(scope["project"])
        with db:
            db.execute("UPDATE card_leases SET expires_at=? WHERE node_id=?", (time.time() - 1, card))
        ok(start(client, scope, card, headers=OTHER))  # cizí aktér kartu po vypršení převezme
        commit_card(repo, card)
        refused = deliver(client, scope, started)
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "execution_superseded" and "start" in refused.json()["hint"]


def test_missing_token_is_422(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _, scope, card = ready(client, tmp_path)
        started = ok(start(client, scope, card))
        response = client.post(f"/api/oporahub/executions/{started['executionId']}/deliver",
                               headers=OTHER, json={**scope, "summary": "x"})
        assert response.status_code == 422 and response.json()["field"] == "X-Opora-Execution-Token", response.text
