"""`POST /executions/start`: tvar těla (422), idempotence téhož aktéra a cizí aktér na držené kartě (409)."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.test_execution_start_deliver import OTHER, ready, start
from backend.app.test_local_merge_autonomy import ok
from backend.canvas.opora_execution_start import validate_body
from backend.canvas.payload_errors import InvalidPayload
from backend.canvas.test_canvas_plan import ORIGIN


@pytest.mark.parametrize("payload,field", [
    ({"project": "p1", "workspace": "draft"}, "body"),
    ({"project": "p1", "workspace": "draft", "nodeId": ""}, "nodeId"),
    ({"project": "p1", "workspace": "draft", "nodeId": "n1", "ttlSeconds": 5}, "ttlSeconds"),
])
def test_body_shape_is_422(payload, field):
    with pytest.raises(InvalidPayload) as error:
        validate_body(payload)
    assert error.value.field == field


def test_same_actor_resumes_and_another_actor_gets_409(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _, scope, card = ready(client, tmp_path)
        first = ok(start(client, scope, card))
        assert first["contextVersion"] == first["assignment"]["contextVersion"] and first["token"]
        assert ok(start(client, scope, card))["executionId"] == first["executionId"]
        refused = start(client, scope, card, headers=OTHER)
        assert refused.status_code == 409 and refused.json()["code"] == "card_leased", refused.text
        assert "hint" in refused.json()
