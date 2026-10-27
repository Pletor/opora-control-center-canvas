"""Dávka plánu přenese druh toku vazby `carries` jen tam, kde ho plán uvedl, a vazbu jiného portu s ním odmítne."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import ORIGIN, SCOPE, plan, seed, send, snapshot


def test_plan_sets_carries_only_where_given(tmp_path):
    body = plan()
    body["edges"][0]["carries"] = "data"
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        response = send(client, seed(client), body)
        assert response.status_code == 200, response.text
        refs = response.json()["refs"]
        edges = client.get("/api/view", params=SCOPE).json()["graph"]["edges"]
        carried = [(e["source"], e["target"], e["carries"]) for e in edges if "carries" in e]
        assert carried == [(refs["vzorek"], refs["ingest"], "data")]


def test_plan_rejects_carries_on_other_port_and_unknown_value(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        before = snapshot(client)
        for index, value in ((5, "data"), (0, "stream")):
            body = plan()
            body["edges"][index]["carries"] = value
            response = send(client, digest, body)
            assert response.status_code == 409, response.text
            assert "carries" in response.json()["error"]
            assert snapshot(client) == before
