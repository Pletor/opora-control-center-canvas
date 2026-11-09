"""Real native baseline CAS and exact proposal human preparation, without agent acceptance."""
import pytest

from backend.api.brain_opora.test_canvas_capability_routes import SCOPE, call
from backend.api.brain_opora.test_canvas_capability_routes import setup as capability_setup
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import legacy_save, propose
from backend.editor.node.test_removals import HEADERS

setup = capability_setup


def initial(service):
    view = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [node("a")], "edges": []}, view["digest"])
    return OporaChangesets(service).context("draft", "draft")


def prepare(client, auth, context):
    data = {"subject": "Pinned baseline", "expectedAcceptedHead": None,
            "expectedGraphDigest": context["graphDigest"], "expectedSpecificationsVersion": context["specificationsVersion"]}
    response = call(client, auth, "opora_changeset_routes.baseline", data, "baseline-review")
    assert response.status_code == 200, response.text
    return data, response.json()


def test_baseline_review_is_durable_scoped_exact_and_native_accept_does_not_duplicate(setup):
    client, service, auth = setup
    context = initial(service)
    data, response = prepare(client, auth, context)
    assert response["state"] == "awaiting_human"
    assert response["result"]["documents"] == context["documents"]
    assert OporaChangesets(service).context("draft", "draft") == context
    path = "/api/oporahub/baseline-preparations/baseline-review"
    assert client.get(path, params=SCOPE, headers=auth).json() == response
    assert call(client, auth, "opora_changeset_routes.baseline_preparation", {"identifier": "baseline-review"}).json()["result"] == response
    assert client.get(path, params={**SCOPE, "project": "foreign"}, headers=auth).status_code == 403
    payload = response["result"]["payload"]
    assert client.post("/api/oporahub/baselines", json=payload, headers=auth).status_code == 403
    assert client.post("/api/oporahub/baselines", json=payload, headers={"X-Opora-Actor": "human"}).status_code in (403, 428)
    accepted = client.post("/api/oporahub/baselines", json=payload, headers=HEADERS)
    assert accepted.status_code == 200, accepted.text
    head = accepted.json()["id"]
    assert client.post("/api/oporahub/baselines", json=payload, headers=HEADERS).status_code == 409
    assert OporaChangesets(service).context("draft", "draft")["acceptedHead"] == head
    assert call(client, auth, "opora_changeset_routes.baseline", data, "baseline-review").json() == response
    assert call(client, auth, "opora_changeset_routes.baseline", {**data, "subject": "Changed"}, "baseline-review").status_code == 409
    pending = propose(service)
    result = call(client, auth, "opora_changeset_routes.accept", {"identifier": pending["id"], "expectedAcceptedHead": head})
    assert result.status_code == 200, result.text
    assert result.json()["result"] == pending and result.json()["state"] == "awaiting_human"
    assert "ohChangeset=" + pending["id"] in result.json()["reviewUrl"]
    assert OporaChangesets(service).context("draft", "draft")["acceptedHead"] == head


@pytest.mark.parametrize("change", ["document", "graph"])
def test_prepared_baseline_stale_native_post_refuses_without_acceptance(setup, change):
    client, service, auth = setup
    context = initial(service)
    _, prepared = prepare(client, auth, context)
    if change == "document":
        legacy_save(service)
    else:
        view = service.view("draft", "draft")
        service.save_graph("draft", "draft", {"nodes": [node("a"), node("b")], "edges": []}, view["digest"])
    response = client.post("/api/oporahub/baselines", headers=HEADERS, json=prepared["result"]["payload"])
    assert response.status_code == 409, response.text
    assert OporaChangesets(service).context("draft", "draft")["acceptedHead"] is None
