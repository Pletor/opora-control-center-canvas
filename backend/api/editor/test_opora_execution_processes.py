"""Linked legacy process reports cannot bypass permanent execution enrollment."""
import sqlite3
from contextlib import closing

import pytest

from backend.api.editor.test_opora_execution_enrollment import enroll
from backend.api.editor.test_opora_execution_routes import AGENT, SCOPE
from backend.api.editor.test_opora_execution_routes import client as execution_client
from backend.canvas.test_canvas_plan import HEADERS
from backend.editor.process.process_store import ProcessStore

SPOOF = {"kind": "human", "name": "Forged author"}
client = execution_client


def create(client, node="n0", headers=AGENT):
    return client.post("/api/processes", headers=headers, json={"project": SCOPE["project"],
        "nodeId": node, "title": "Legacy", "steps": ["Check"], "inputs": {"worktree": "wt-one"}, "by": SPOOF})


@pytest.mark.parametrize("operation", ["create", "transition", "steps", "reports"])
def test_enrolled_legacy_mutations_reject_body_human(client, operation):
    process = create(client).json()["process"]
    enroll(client)
    path = "/api/processes/" + process["id"]
    before = client.get(path, params=SCOPE).json()
    if operation == "create":
        response = create(client)
    else:
        body = {"project": SCOPE["project"], "revision": process["revision"], "by": SPOOF}
        suffix = "/" + operation
        if operation == "transition":
            body["to"] = "running"
        elif operation == "steps":
            suffix += "/" + process["steps"][0]["id"]
            body.update(state="done", evidence={"summary": "Spoof", "by": SPOOF})
        else:
            body.update(kind="result", summary="Old worker", processRevision=process["revision"])
        response = client.post(path + suffix, headers=AGENT, json=body)
    assert response.status_code == 409 and "execution receipts" in response.text, response.text
    assert client.get(path, params=SCOPE).json() == before


def test_human_process_override_uses_verified_attribution(client):
    enroll(client)
    response = create(client, headers=HEADERS)
    assert response.status_code == 200, response.text
    process = response.json()["process"]
    path = "/api/processes/" + process["id"]
    response = client.post(path + "/transition", headers=HEADERS, json={"project": SCOPE["project"],
        "revision": process["revision"], "to": "running", "by": SPOOF})
    assert response.status_code == 200, response.text
    assert response.json()["process"]["history"][-1]["by"] == {"kind": "human", "name": "Člověk"}
    process = response.json()["process"]
    response = client.post(path + "/reports", headers=HEADERS, json={"project": SCOPE["project"],
        "kind": "step_done", "stepId": process["steps"][0]["id"], "summary": "Reviewed",
        "by": SPOOF, "processRevision": process["revision"]})
    assert response.status_code == 200, response.text
    assert response.json()["report"]["by"] == {"kind": "human", "name": "Člověk"}


def test_other_workspace_enrollment_also_guards_project_process(client):
    service = client.app.state.service
    with service.db_for(SCOPE["project"]) as db:
        db.execute("INSERT INTO opora_execution_epochs VALUES(?,?,?,1)", (SCOPE["project"], "other", "n0"))
    assert create(client).status_code == 409
    assert create(client, node="unrelated").status_code == 200
    assert create(client, node=None).status_code == 200


def test_process_file_write_keeps_enrollment_transaction_locked(client, monkeypatch):
    service = client.app.state.service
    db = service.db_for(SCOPE["project"])
    path = db.execute("PRAGMA database_list").fetchone()[2]
    original = ProcessStore.create
    observed = []

    def write(store, *args, **kwargs):
        with closing(sqlite3.connect(path, timeout=0)) as competitor, pytest.raises(sqlite3.OperationalError, match="locked"):
            competitor.execute("BEGIN IMMEDIATE")
        observed.append(True)
        return original(store, *args, **kwargs)

    monkeypatch.setattr(ProcessStore, "create", write)
    assert create(client).status_code == 200
    assert observed == [True]
