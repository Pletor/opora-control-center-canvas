"""`GET /api/oporahub/plan-reality`: identita, souhrn vrstvy a neplatná karta (výpočet folie: test_plan_reality.py)."""
from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.api.editor.test_opora_execution_routes import (
    client as client,  # noqa: PLC0414 - shared pytest fixture
)
from backend.canvas.test_canvas_plan import HEADERS, SCOPE

URL = "/api/oporahub/plan-reality"


def test_summary_card_and_identity(client):
    summary = client.get(URL, params=SCOPE, headers=AGENT)
    assert summary.status_code == 200 and isinstance(summary.json(), dict), summary.text
    card = client.get(URL, params={**SCOPE, "nodeId": "n0"}, headers=AGENT)
    assert card.status_code == 409 and card.json()["code"] == "repository_unknown"  # prostor bez repozitáře
    assert summary.json() == {}
    assert client.get(URL, params={**SCOPE, "nodeId": "missing"}, headers=AGENT).status_code == 409
    client.cookies.clear()
    assert client.get(URL, params=SCOPE, headers=HEADERS).status_code == 428
