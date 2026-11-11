"""Cesty `/api/page-plan` přes celou aplikaci (middleware, identita, chyby jako `{error, code, hint}`)."""
import json
import threading

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens
from backend.project.architecture import page_plan_capture, page_plan_scan
from backend.project.architecture.test_page_plan import box, graph
from backend.project.architecture.test_page_plan_scan import GOOD

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN, "content-type": "application/json"}
AGENT = {**HEADERS, "x-opora-actor": "agent; name=tester"}
SCOPE = {"project": "draft", "workspace": "draft"}
PAGE = {**SCOPE, "pageId": "kurz"}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph(), "digest": digest}).status_code == 200
        yield client


def plan(client, headers=None):
    response = client.get("/api/page-plan", params=PAGE, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


def test_human_and_agent_read_and_agent_proposes(client):
    current = plan(client)
    assert set(current) == {"page", "sections", "logic", "digest", "readOnly"}
    assert plan(client, AGENT)["digest"] == current["digest"]
    sections = [*current["sections"], box("hero", "hero", status="proposed")]
    saved = client.post("/api/page-plan", headers=AGENT,
                        json={**PAGE, "expectedDigest": current["digest"], "sections": sections})
    assert saved.status_code == 200, saved.text
    assert saved.json()["sections"][2]["source"] == "agent"
    refused = client.post("/api/page-plan", headers=AGENT,
                          json={**PAGE, "expectedDigest": saved.json()["digest"], "sections": sections[:1]})
    assert refused.status_code == 403 and refused.json()["code"] == "agent_box_refused" and refused.json()["hint"]
    stale = client.post("/api/page-plan", headers=HEADERS, json={**PAGE, "expectedDigest": "x", "sections": []})
    assert stale.status_code == 409 and stale.json()["code"] == "plan_changed"
    invalid = client.post("/api/page-plan", headers=HEADERS,
                          json={**PAGE, "expectedDigest": saved.json()["digest"], "sections": [box("a", role="x")]})
    assert invalid.status_code == 422


def test_box_status_is_human_only(client):
    url = "/api/page-plan/kurz/boxes/header/status"
    assert client.post(url, headers=AGENT, json={**SCOPE, "status": "approved"}).status_code == 403
    done = client.post(url, headers=HEADERS, json={**SCOPE, "status": "approved"})
    assert done.status_code == 200 and done.json()["sections"][0]["status"] == "approved"
    missing = client.post("/api/page-plan/kurz/boxes/nic/status", headers=HEADERS, json={**SCOPE, "status": "draft"})
    assert missing.status_code == 404 and missing.json()["code"] == "box_not_found"


def test_without_identity_is_428(client):
    client.cookies.clear()
    response = client.get("/api/page-plan", params=PAGE)
    assert response.status_code == 428 and response.json()["code"] == "identity_required"


def test_worker_token_reads_and_writes_its_workspace(client):
    token = tokens.issue_worker(client.app.state.service, "draft", "draft", {"name": "worker"})["token"]
    client.cookies.clear()
    gate = {**HEADERS, tokens.HEADER: token}
    current = plan(client, gate)
    saved = client.post("/api/page-plan", headers=gate, json={**PAGE, "expectedDigest": current["digest"],
                                                              "sections": [*current["sections"], box("x", status="proposed")]})
    assert saved.status_code == 200, saved.text
    assert client.post("/api/page-plan/kurz/boxes/x/status", headers=gate, json={**SCOPE, "status": "approved"}).status_code == 403


def test_scan_route_starts_and_reports(client, monkeypatch):
    finished = threading.Event()

    def shots(url, selectors, folder):
        (folder / "page.png").write_bytes(b"PNG")
        return {"page": "page.png", "sections": {}}, []
    monkeypatch.setattr(page_plan_capture, "capture", shots)

    def fake(url, note, folder):
        finished.set()
        return json.dumps(GOOD), 0.01
    monkeypatch.setattr(page_plan_scan, "research", fake)
    started = client.post("/api/page-plan/scan", headers=HEADERS, json={**PAGE, "url": "https://example.com"})
    assert started.status_code == 200 and started.json()["state"] == "running"
    finished.wait(5)
    for _ in range(100):
        state = client.get(f"/api/page-plan/scan/{started.json()['scanId']}", params=SCOPE).json()
        if state["state"] != "running":
            break
        threading.Event().wait(0.02)
    assert state["state"] == "done" and state["proposal"]["logic"][0]["ref"] == "koupit"
    assert client.get("/api/page-plan/scan/latest", params=PAGE).json()["scanId"] == state["scanId"]
    picture = client.get(f"/api/page-plan/scan/{state['scanId']}/capture/page.png", params=SCOPE)
    assert picture.status_code == 200 and picture.headers["content-type"] == "image/png"
    for name in ("research.out.jsonl", "..%2F" + state["scanId"] + ".json"):
        assert client.get(f"/api/page-plan/scan/{state['scanId']}/capture/{name}", params=SCOPE).status_code == 404
    current = plan(client)
    taken = client.post("/api/page-plan", headers=HEADERS, json={**PAGE, "expectedDigest": current["digest"],
                                                                 "scanId": state["scanId"],
                                                                 "sections": state["proposal"]["sections"]})
    assert taken.status_code == 200 and {item["source"] for item in taken.json()["sections"]} == {"scan"}
    assert client.get(f"/api/page-plan/scan/{state['scanId']}", params=SCOPE).json()["outcome"] == "adopted"
    assert client.get("/api/page-plan/scan/latest", params=PAGE).status_code == 404
    discard = f"/api/page-plan/scan/{state['scanId']}/discard"
    assert client.post(discard, headers=AGENT, json=SCOPE).status_code == 403
    assert client.post(discard, headers=HEADERS, json=SCOPE).json()["code"] == "scan_closed"
    assert client.get("/api/page-plan/scan/" + "0" * 32, params=SCOPE).status_code == 404
    bad = client.post("/api/page-plan/scan", headers=HEADERS, json={**PAGE, "url": "file:///etc/passwd"})
    assert bad.status_code == 422
