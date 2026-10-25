import sqlite3
from contextlib import contextmanager, nullcontext

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.harness_invocation_routes import create_harness_invocation_router
from backend.library.test_harness_invocations import fixture
from database.repositories.opora_executions import Executions
from database.schema.opora_execution_schema import SCHEMA


class Canvas:
    def __init__(self, db):
        self.db = db

    def project_exists(self, project):
        return project == "project-1"

    def lock_for(self, _project):
        return nullcontext()

    def db_for(self, _project):
        return self.db


@contextmanager
def client_with_receipt():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        db.executescript(SCHEMA)
        record, observation = fixture()
        repo = Executions(db, record["project"], record["workspace"])
        repo.insert(record, "agent:test", "claim", "request-digest")
        receipt = {"receiptId": "source-receipt", "executionId": record["executionId"],
                   "requestId": "result-1", "result": {"harnessInvocations": [observation],
                                                           "stdout": "private output", "token": "private token"},
                   "assignmentDigest": record["assignmentDigest"], "state": "reported"}
        repo.insert_receipt(record["executionId"], "result-1", "result-digest", receipt)
        app = FastAPI()
        app.include_router(create_harness_invocation_router(Canvas(db)))
        with TestClient(app) as client:
            yield client
    finally:
        db.close()


def test_http_report_is_scoped_bounded_and_redacted():
    with client_with_receipt() as client:
        response = client.get("/api/oporahub/harness-invocations",
                              params={"project": "project-1", "workspace": "draft"})
        assert response.status_code == 200
        body = response.json()
        assert body["evidence"] == "worker-reported" and body["serverObserved"] is False
        assert body["cohorts"][0]["invocations"] == 1
        assert "private output" not in response.text and "private token" not in response.text
        assert '"stdout"' not in response.text and '"token"' not in response.text
        assert client.get("/api/oporahub/harness-invocations", params={"project": "project-1", "workspace": "other"}).json()["cohorts"] == []
        assert client.get("/api/oporahub/harness-invocations", params={"project": "project-1", "workspace": "draft", "nodeId": "other"}).json()["cohorts"] == []
        assert client.get("/api/oporahub/harness-invocations", params={"project": "project-1", "workspace": "draft", "resource": "other"}).json()["cohorts"] == []
        assert client.get("/api/oporahub/harness-invocations", params={"project": "project-1", "workspace": "draft", "limit": 0}).status_code == 422
        missing = client.get("/api/oporahub/harness-invocations", params={"project": "missing", "workspace": "draft"})
        assert missing.status_code == 404 and missing.json()["code"] == "project_not_found"
