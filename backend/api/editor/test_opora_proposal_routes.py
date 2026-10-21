"""Proposal API binds persisted assignments to a real session actor and observed head."""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

TARGET = {**SCOPE, "scope": "n0"}
AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=planner"}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as instance:
        seed(instance)
        yield instance


def context(client):
    response = client.get("/api/oporahub/context", params=TARGET)
    assert response.status_code == 200, response.text
    return response.json()


def proposal(current, **extra):
    return {**TARGET, "subject": "Checkpoint assignment", "expectedHead": current["head"],
            "expectedContextVersion": current["contextVersion"], **extra}


def post(client, current, **extra):
    return client.post("/api/oporahub/proposals", headers=AGENT, json=proposal(current, **extra))


def rename(client, name):
    current = client.get("/api/view", params=SCOPE).json()
    graph = copy.deepcopy(current["graph"])
    graph["nodes"][1]["name"] = name
    response = client.post("/api/graph", headers=HEADERS,
                           json={**SCOPE, "graph": graph, "digest": current["digest"]})
    assert response.status_code == 200, response.text


def test_agent_captures_server_content_and_cannot_claim_human_or_merge(client):
    current = context(client)
    response = post(client, current, by={"kind": "human", "name": "spoof"},
                    specificationSnapshot={"forged": True})
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["by"] == {"kind": "agent", "name": "planner"}
    assert record["specificationSnapshot"]["specification"] == current["specification"]
    assert record["inMain"] is False
    for route in ("/api/opora-merge", "/api/opora-commit"):
        denied = client.post(route, headers=AGENT, json={
            **TARGET, "id": record["id"], "by": {"kind": "human", "name": "spoof"}})
        assert denied.status_code == 403, denied.text
    history = client.get("/api/opora-commits", params=TARGET).json()
    assert history["main"] is None and len(history["items"]) == 1
    assert client.get("/api/opora-commit", params={**TARGET, "id": record["id"]}).json() == record


def test_unknown_actor_cannot_be_silently_attributed_to_human(client):
    payload = proposal(context(client), by={"kind": "human", "name": "spoof"})
    client.cookies.clear()
    for route in ("/api/oporahub/proposals", "/api/opora-commit", "/api/opora-merge"):
        response = client.post(route, headers=HEADERS, json=payload)
        assert response.status_code == 428, response.text
    assert client.get("/api/opora-commits", params=TARGET).json()["items"] == []


@pytest.mark.parametrize("missing", ["expectedHead", "expectedContextVersion"])
def test_expectations_are_mandatory(client, missing):
    payload = proposal(context(client))
    del payload[missing]
    response = client.post("/api/oporahub/proposals", headers=AGENT, json=payload)
    assert response.status_code == 409
    assert client.get("/api/opora-commits", params=TARGET).json()["items"] == []


def test_historical_diff_remains_immutable_after_subsequent_canvas_edits(client):
    first = post(client, context(client)).json()
    rename(client, "Second assignment")
    second = post(client, context(client)).json()
    params = {**TARGET, "before": first["id"], "after": second["id"]}
    diff = client.get("/api/oporahub/diff", params=params)
    assert diff.status_code == 200 and diff.json()["changes"]
    rename(client, "Third assignment")
    assert client.get("/api/oporahub/diff", params=params).json() == diff.json()
    assert client.get("/api/opora-commit", params={**TARGET, "id": first["id"]}).json() == first
    stale = client.post("/api/opora-merge", headers=HEADERS,
                        json={**TARGET, "id": second["id"]})
    assert stale.status_code == 409 and "Zadání" in stale.json()["error"]


def test_concurrent_agents_from_same_head_produce_exactly_one_success(client):
    current = context(client)
    barrier = Barrier(2)

    def submit(_):
        barrier.wait(timeout=5)
        return post(client, current)

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(submit, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert len(client.get("/api/opora-commits", params=TARGET).json()["items"]) == 1


@pytest.mark.parametrize("change", ["head", "assignment"])
def test_stale_expectation_never_reaches_immutable_file_write(client, monkeypatch, change):
    from backend.canvas.opora_hub_store import OporaHubStore

    current = context(client)
    if change == "head":
        assert post(client, current).status_code == 200
    else:
        rename(client, "New assignment")

    def forbidden_write(*args):
        pytest.fail("Stale proposal must not write a commit file")

    monkeypatch.setattr(OporaHubStore, "write", forbidden_write)
    response = post(client, current)
    assert response.status_code == 409, response.text
    assert len(client.get("/api/opora-commits", params=TARGET).json()["items"]) == (change == "head")


def test_superseded_proposal_cannot_merge_even_when_assignment_is_unchanged(client):
    first = post(client, context(client)).json()
    assert post(client, context(client)).status_code == 200
    response = client.post("/api/opora-merge", headers=HEADERS,
                           json={**TARGET, "id": first["id"]})
    assert response.status_code == 409 and "hlavu" in response.json()["error"]


def test_human_cookie_is_attributed_as_human_without_trusting_payload_name(client):
    response = client.post("/api/oporahub/proposals", headers=HEADERS,
                           json=proposal(context(client), by={"kind": "agent", "name": "forged"}))
    assert response.status_code == 200
    assert response.json()["by"] == {"kind": "human", "name": "Člověk"}
