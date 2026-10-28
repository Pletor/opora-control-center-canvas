"""Rozhraní strážců: stav strážců a filtrované nálezy projektu."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.strazci_routes import create_strazci_router
from backend.canvas.canvas_service import CanvasService
from backend.canvas.strazci.manager import GuardianManager
from backend.canvas.strazci.registry import Guard

NOW = 1_800_000_000.0


@pytest.fixture
def setup(tmp_path):
    service = CanvasService(tmp_path / "data")
    found = [{"key": "k1", "rule": "r", "severity": "warn", "message": "Varování", "nodeId": "n1"},
             {"key": "k2", "rule": "r", "severity": "block", "message": "Blok", "nodeId": "n2"}]
    manager = GuardianManager(service, guards=[Guard("g", "Strážce G", 60, lambda ctx: list(found))])
    app = FastAPI()
    app.include_router(create_strazci_router(service, manager))
    yield TestClient(app), manager, found
    service.close()


def test_status_lists_guards_with_open_counts(setup):
    client, manager, _ = setup
    before = client.get("/api/strazci", params={"project": "draft"}).json()
    assert before == {"guards": [{"id": "g", "label": "Strážce G", "every_s": 60, "lastRunAt": None, "lastOkAt": None,
                                  "open": {"block": 0, "warn": 0, "info": 0}}],
                      "open": {"block": 0, "warn": 0, "info": 0}}
    manager.run_once(NOW)
    after = client.get("/api/strazci", params={"project": "draft"}).json()
    assert after["open"] == {"block": 1, "warn": 1, "info": 0} and after["guards"][0]["lastOkAt"]


def test_findings_filter_by_node_and_open(setup):
    client, manager, found = setup
    manager.run_once(NOW)
    body = client.get("/api/strazci/findings", params={"project": "draft"}).json()
    assert [item["key"] for item in body["findings"]] == ["k2", "k1"]
    only = client.get("/api/strazci/findings", params={"project": "draft", "node": "n1"}).json()["findings"]
    assert [item["key"] for item in only] == ["k1"]
    found.pop()
    manager.run_once(NOW + 60)
    assert [i["key"] for i in client.get("/api/strazci/findings", params={"project": "draft"}).json()["findings"]] == ["k1"]
    every = client.get("/api/strazci/findings", params={"project": "draft", "open": 0}).json()["findings"]
    assert {item["key"]: item["resolvedAt"] is not None for item in every} == {"k1": False, "k2": True}


def test_unknown_project_is_404(setup):
    client, _, _ = setup
    assert client.get("/api/strazci", params={"project": "nikdo"}).status_code == 404
    assert client.get("/api/strazci/findings", params={"project": "nikdo"}).status_code == 404


def test_trend_returns_series_filtered_by_metric_and_days(tmp_path):
    from backend.canvas.strazci import guard_trend

    service = CanvasService(tmp_path / "trend")
    try:
        guard_trend.record(service, "draft", {"holes": 4, "cards.done": 1}, NOW - 20 * 86400)
        guard_trend.record(service, "draft", {"holes": 2, "cards.done": 3}, NOW - 3600)
        app = FastAPI()
        app.include_router(create_strazci_router(service, GuardianManager(service, guards=[]), clock=lambda: NOW))
        client = TestClient(app)
        body = client.get("/api/strazci/trend", params={"project": "draft"}).json()
        assert body["days"] == 14 and body["metrics"] == list(guard_trend.METRICS)
        assert {metric: [p["value"] for p in points] for metric, points in body["series"].items()} == {
            "holes": [2], "cards.done": [3]}
        month = client.get("/api/strazci/trend", params={"project": "draft", "metric": "holes", "days": 30}).json()
        assert month["metrics"] == ["holes"] and [p["value"] for p in month["series"]["holes"]] == [4, 2]
        assert client.get("/api/strazci/trend", params={"project": "draft", "metric": "nic"}).status_code == 422
        assert client.get("/api/strazci/trend", params={"project": "draft", "days": 91}).status_code == 422
        assert client.get("/api/strazci/trend", params={"project": "nikdo"}).status_code == 404
    finally:
        service.close()
