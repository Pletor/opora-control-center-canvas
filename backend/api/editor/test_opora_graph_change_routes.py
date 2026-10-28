"""V1 and V2 public graph proposal protocol retains real actor enforcement."""
from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.api.editor.test_opora_graph_routes import BASE, client, create
from backend.canvas.test_canvas_plan import HEADERS, SCOPE

__all__ = ["client"]


def accepted_baseline(client):
    item = create(client)
    response = client.post(BASE + "/" + item["id"] + "/accept", headers=HEADERS, json={**SCOPE,
        "expectedAcceptedHead": None, "expectedGraphDigest": item["graphDigest"], "adoptBaseGraphDigest": item["graphDigest"]})
    assert response.status_code == 200, response.text
    return item["refs"]["task"]


def propose(client, plan):
    context = client.get(BASE + "/context", params=SCOPE)
    assert context.status_code == 200, context.text
    observed = context.json()
    response = client.post(BASE, headers=AGENT, json={**SCOPE, "parentRevision": observed["acceptedHead"],
        "expectedGraphDigest": observed["graphDigest"], "subject": "Reviewed edit", "plan": plan})
    assert response.status_code == 200, response.text
    return response.json()


def test_v2_dispatch_review_identity_sparse_history_and_removal(client):
    node = accepted_baseline(client)
    item = propose(client, {"updateNodes": [{"id": node, "fields": {"name": "Renamed task"}}]})
    assert item["schemaVersion"] == 2 and item["by"]["kind"] == "agent"
    detail = client.get(BASE + "/" + item["id"], params=SCOPE)
    assert detail.status_code == 200 and detail.json() == item
    summaries = client.get(BASE, params=SCOPE).json()["items"]
    assert len(summaries) == 2 and all("baseGraph" not in row and "stateEffects" not in row for row in summaries)
    payload = {**SCOPE, "expectedAcceptedHead": item["parentRevision"], "expectedGraphDigest": item["graphDigest"],
               "adoptBaseGraphDigest": None, "reviewedChangesId": item["id"]}
    path = BASE + "/" + item["id"] + "/accept"
    assert client.post(path, headers=AGENT, json=payload).status_code == 403
    missing_ack = {key: value for key, value in payload.items() if key != "reviewedChangesId"}
    rejected = client.post(path, headers=HEADERS, json=missing_ack)  # neplatné tělo = 422 a jméno chybějícího pole
    assert rejected.status_code == 422 and "reviewedChangesId" in rejected.json()["error"]
    response = client.post(path, headers=HEADERS, json=payload)
    assert response.status_code == 200, response.text
    assert client.get(BASE + "/context", params=SCOPE).json()["acceptedGraph"]["nodes"][0]["name"] == "Renamed task"
    removal = propose(client, {"removeNodes": [node]})
    payload.update(expectedAcceptedHead=removal["parentRevision"], expectedGraphDigest=removal["graphDigest"], reviewedChangesId=removal["id"])
    response = client.post(BASE + "/" + removal["id"] + "/accept", headers=HEADERS, json=payload)
    assert response.status_code == 200, response.text
    assert client.get(BASE + "/context", params=SCOPE).json()["workingGraph"] == {"nodes": [], "edges": []}


def test_context_remains_readable_after_working_deletion(client):
    node = accepted_baseline(client)
    service = client.app.state.service
    view = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [], "edges": []}, view["digest"], allow_removal=True)
    context = client.get(BASE + "/context", params=SCOPE)
    assert context.status_code == 200, context.text
    assert context.json()["acceptedGraph"]["nodes"] and not context.json()["workingGraph"]["nodes"]
    assert propose(client, {"removeNodes": [node]})["changes"]["nodes"][0]["workingBefore"] is None
