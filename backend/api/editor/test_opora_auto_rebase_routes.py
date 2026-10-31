"""HTTP wiring of auto-rebase conflicts, card history/blame and sparse enrollment."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS
from backend.canvas.test_opora_auto_rebase import propose
from backend.canvas.test_opora_changesets import accept, baseline
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414

PARAMS = {"project": "draft", "workspace": "draft"}
AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=builder"}


def test_conflict_resolution_history_and_blame_over_http(service):
    root = baseline(service)
    ours, theirs = propose(service, "a", goal="Ours"), propose(service, "a", goal="Theirs")
    head = accept(service, theirs, root["id"])["id"]
    with TestClient(create_app(service.root), base_url="http://127.0.0.1:8740") as client:
        run = client.post("/api/oporahub/auto-rebase/run", json=PARAMS, headers=AGENT)
        assert run.status_code == 200, run.text
        assert [item["proposalId"] for item in run.json()["conflicts"]] == [ours["id"]]
        listed = client.get("/api/oporahub/auto-rebase/conflicts", params={**PARAMS, "status": "open"}).json()
        conflict = listed["items"][0]
        assert conflict["items"][0]["key"] == "spec:a:goal"
        assert client.get(f"/api/oporahub/auto-rebase/conflicts/{conflict['id']}", params=PARAMS).json() == conflict
        resolution = propose(service, "a", goal="Merged")
        resolved = client.post(f"/api/oporahub/auto-rebase/conflicts/{conflict['id']}/resolve",
                               json={**PARAMS, "resolutionProposalId": resolution["id"]}, headers=AGENT)
        assert resolved.status_code == 200 and resolved.json()["status"] == "resolved"
        history = client.get("/api/oporahub/history/card/a", params=PARAMS).json()
        assert [item["revisionId"] for item in history["items"]] == [root["id"], head]
        blame = client.get("/api/oporahub/blame/card/a", params=PARAMS).json()
        assert {item["key"]: item["revisionId"] for item in blame["items"]}["spec:goal"] == head
        rebuild = client.post("/api/oporahub/history/rebuild", json=PARAMS, headers=AGENT)
        assert rebuild.status_code == 403
        dry = client.post("/api/oporahub/sparse-context/backfill", json={**PARAMS, "dryRun": True}, headers=AGENT)
        assert dry.status_code == 200 and dry.json()["dryRun"] is True
        assert client.post("/api/oporahub/sparse-context/backfill", json={**PARAMS, "dryRun": False},
                           headers=AGENT).status_code == 403
        assert client.get("/api/oporahub/sparse-context/enrollment", params=PARAMS).status_code == 200


def test_keep_accepted_over_http(service):
    root = baseline(service)
    propose(service, "a", goal="Ours")
    accept(service, propose(service, "a", goal="Theirs"), root["id"])
    with TestClient(create_app(service.root), base_url="http://127.0.0.1:8740") as client:
        client.post("/api/oporahub/auto-rebase/run", json=PARAMS, headers=AGENT)
        conflict = client.get("/api/oporahub/auto-rebase/conflicts", params={**PARAMS, "status": "open"}).json()["items"][0]
        path = f"/api/oporahub/auto-rebase/conflicts/{conflict['id']}/resolve"
        both = client.post(path, json={**PARAMS, "keep": "accepted", "resolutionProposalId": "0" * 40}, headers=AGENT)
        assert both.status_code == 409
        kept = client.post(path, json={**PARAMS, "keep": "accepted"}, headers=AGENT)
        assert kept.status_code == 200, kept.text
        assert kept.json()["status"] == "resolved" and kept.json()["resolutionProposalId"] is None
