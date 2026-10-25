import copy
import hashlib
import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.harness_invocation_routes import create_harness_invocation_router
from backend.canvas.opora_result_extensions import validate_extensions
from backend.library.harness_documentation import validate_documentation
from backend.library.harness_documentation_reports import read
from backend.library.test_harness_invocation_reports import database
from backend.library.test_harness_invocations import fixture as node_fixture
from database.repositories.opora_executions import Executions


def fixture():
    record, node = node_fixture()
    content = json.dumps({"schema": "harness.context7/1", "library": "/nodejs/node/v22.17.0"})
    resource = record["assignment"]["documents"][0]["fields"]["harness"]["resources"][0]
    resource.update(category="mcp", content=content, requires=["mcp:context7"],
                    digest=hashlib.sha256(content.encode()).hexdigest())
    item = {"schema": "harness.documentation-observation/1", "readId": str(uuid.uuid4()),
            "execution": node["execution"], "resource": {"id": resource["resource"], "digest": resource["digest"]},
            "adapter": "context7-documentation/1", "library": "/nodejs/node/v22.17.0", "documentDigest": "c" * 64,
            "fetchedAt": "2026-10-24T03:30:00.000Z", "durationMs": 2182, "outputBytes": 100,
            "evidence": "worker-reported", "independentlyVerified": False, "causalContribution": False,
            "promotionAllowed": False}
    return record, item


def save(db, record, item, request):
    repo = Executions(db, record["project"], record["workspace"])
    try:
        repo.read(record["executionId"])
    except ValueError:
        repo.insert(record, "agent:test", request, "request-digest")
    receipt = {"receiptId": uuid.uuid4().hex, "assignmentDigest": record["assignmentDigest"],
               "result": {"harnessDocumentation": [item], "summary": "private task detail"}}
    repo.insert_receipt(record["executionId"], request, request, receipt)
    return repo


@pytest.mark.parametrize("patch", [
    {"schema": "other"}, {"readId": "bad"}, {"query": "private"}, {"text": "private"}, {"token": "secret"},
    {"evidence": "server-verified"}, {"promotionAllowed": True}, {"independentlyVerified": True},
    {"causalContribution": True}, {"durationMs": True}, {"durationMs": float("nan")}, {"durationMs": 10 ** 10000},
    {"outputBytes": False}, {"outputBytes": 65537}, {"fetchedAt": "yesterday"}, {"fetchedAt": []},
    {"adapter": "node-readonly/1"}, {"library": "/other/version"}, {"documentDigest": "bad"},
])
def test_invalid_metadata(patch):
    record, item = fixture()
    item.update(patch)
    with pytest.raises(ValueError):
        validate_documentation({"harnessDocumentation": [item]}, record)


def test_binding_and_absence():
    record, item = fixture()
    assert validate_documentation({}, {}) == []
    assert validate_documentation({"harnessDocumentation": [item]}, record) == [item]
    for change in [lambda r: r.update(nodeId="other"), lambda r: r.update(contextProtocolVersion=True),
                   lambda r: r.update(epoch=7), lambda r: r.update(assignmentDigest="d" * 64),
                   lambda r: r["assignment"]["documents"].append(copy.deepcopy(r["assignment"]["documents"][0])),
                   lambda r: r["assignment"]["documents"][0]["fields"]["harness"]["resources"][0].update(content="changed")]:
        modified = copy.deepcopy(record)
        change(modified)
        with pytest.raises(ValueError):
            validate_documentation({"harnessDocumentation": [item]}, modified)
    for items in [[item, item], [item] * 33, {}]:
        with pytest.raises(ValueError):
            validate_documentation({"harnessDocumentation": items}, record)


def test_registered_validation_dedup_conflicts_and_private_projection():
    record, item = fixture()
    db = database()
    repo = save(db, record, item, "r1")
    validate_extensions({"harnessDocumentation": [item]}, record, repo)
    save(db, record, item, "r2")
    report = read(db, record["project"], record["workspace"])
    assert len(report["observations"]) == 1
    assert report["serverObserved"] is False and report["promotionAllowed"] is False
    assert "private task detail" not in json.dumps(report)
    assert "percent" not in report and "no failed-attempt denominator" in report["coverage"]
    assert read(db, "other", record["workspace"])["observations"] == []
    assert read(db, record["project"], record["workspace"], node="other")["observations"] == []
    assert read(db, record["project"], record["workspace"], resource="other")["observations"] == []
    changed = {**item, "durationMs": 20}
    with pytest.raises(ValueError, match="different metadata"):
        validate_extensions({"harnessDocumentation": [changed]}, record, repo)
    save(db, record, changed, "r3")
    report = read(db, record["project"], record["workspace"])
    assert report["observations"] == [] and report["conflictingReads"] == 1
    assert read(db, record["project"], record["workspace"], limit=1)["receiptWindowLimited"]


def test_v2_uses_complete_optional_validator():
    record, item = fixture()
    kit = record["assignment"]["documents"][0]["fields"]["harness"]
    kit["schema"] = "harness.kit/2"
    with pytest.raises(ValueError):
        validate_documentation({"harnessDocumentation": [item]}, record)
    selection = pytest.importorskip("backend.library.harness_selection")
    resource = kit["resources"][0]
    kit["selection"] = {"schema": "harness.selection/1", "policy": "harness.recommendation/1",
                        "problem": kit["problems"][0], "profileRevision": None,
                        "declaredCapabilities": ["mcp:context7"], "evidence": "caller-declared-selection",
                        "entries": [{"resource": resource["resource"], "digest": resource["digest"],
                                     "versionDigest": selection.version_digest(resource), "order": 0,
                                     "reason": "unknown-exploration", "assignments": []}]}
    assert validate_documentation({"harnessDocumentation": [item]}, record) == [item]
    kit["selection"]["entries"][0]["digest"] = "0" * 64
    with pytest.raises(ValueError):
        validate_documentation({"harnessDocumentation": [item]}, record)


def test_registered_route_filters_and_limits():
    import sqlite3
    import threading

    from database.schema.opora_execution_schema import SCHEMA
    record, item = fixture()
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(SCHEMA)
    save(db, record, item, "r1")

    class Canvas:
        def project_exists(self, project):
            return project == record["project"]

        def lock_for(self, _project):
            return threading.RLock()

        def db_for(self, _project):
            return db

    app = FastAPI()
    app.include_router(create_harness_invocation_router(Canvas()))
    client = TestClient(app)
    base = "/api/oporahub/harness-documentation?project=project-1&workspace=draft"
    response = client.get(base)
    assert response.status_code == 200
    assert response.json()["observations"][0]["observation"] == item
    # Missing project and malformed filters return before opening the SQLite connection.
    assert client.get(base.replace("project-1", "missing")).status_code == 404
    assert client.get(base + "&limit=101").status_code == 422
    assert client.get(base + "&resource=").status_code == 422
