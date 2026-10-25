"""Shared lessons require current public evidence and an exact remote readback."""
import copy
import json
import sqlite3

import pytest

from backend.canvas.opora_verification_validation import digest
from backend.library import harness_shared_memory as shared
from backend.library.harness_memory import HarnessMemory
from backend.integrations.openviking_client import OpenVikingClient
from database.schema.harness_learning_schema import SCHEMA as QUEUE_SCHEMA


class Canvas:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE opora_verification_requests(project_id TEXT, workspace_id TEXT, id TEXT,
                execution_id TEXT, node_id TEXT);
            CREATE TABLE opora_verification_reports(project_id TEXT, workspace_id TEXT,
                verification_id TEXT, digest TEXT);
        """)
        self.db.executescript(QUEUE_SCHEMA)
        self.memory_service = None

    def project_ids(self):
        return ["project-a"]

    def db_for(self, project):
        assert project == "project-a"
        return self.db

    def lock_for(self, project):
        assert project == "project-a"
        from contextlib import nullcontext
        return nullcontext()


def assessment():
    return {"eligible": True, "publication": "pub-one",
            "candidate": {"id": "candidate-x", "digest": "c" * 64}, "problem": "problem-y",
            "policyDigest": "d" * 64, "evidenceDigest": "e" * 64,
            "sources": [{"project": "project-a", "workspace": "workspace-a",
                         "verificationId": "verification-1", "reportDigest": "r" * 64}],
            "verifiedProjects": 3, "verifiedImages": 2,
            "environmentBasis": "pinned-image", "evidenceBasis": "paired-fixtures",
            "privateContent": "should never escape", "sourceUri": "viking://private"}


@pytest.fixture
def canvas(monkeypatch):
    c = Canvas()
    monkeypatch.setattr(shared, "_assessment", lambda _canvas, publication: {**assessment(), "publication": publication})
    events = iter(range(41, 100))
    monkeypatch.setattr(shared, "emit_event", lambda db, **kwargs: next(events))
    with c.db:
        c.db.execute("INSERT INTO opora_verification_requests VALUES(?,?,?,?,?)",
                     ("project-a", "workspace-a", "verification-1", "execution-1", "node-1"))
        c.db.execute("INSERT INTO opora_verification_reports VALUES(?,?,?,?)",
                     ("project-a", "workspace-a", "verification-1", "r" * 64))
    yield c
    c.db.close()


def test_snapshot_is_public_allowlist_and_enqueue_is_idempotent(canvas):
    body = shared.snapshot(canvas, "pub-one")
    assert set(body) == {"schema", "publication", "candidate", "problem", "policyDigest", "evidenceDigest",
                         "sources", "verifiedProjects", "verifiedImages", "environmentBasis", "evidenceBasis",
                         "meaning", "productionOutcome", "promotionAllowed", "executionAuthority", "lessonDigest"}
    assert "privateContent" not in json.dumps(body) and "sourceUri" not in json.dumps(body)
    first = shared.enqueue(canvas, "pub-one")
    again = shared.enqueue(canvas, "pub-one")
    assert first["lessonDigest"] == again["lessonDigest"] and first["state"] == again["state"] == "pending"
    assert canvas.db.execute("SELECT COUNT(*) FROM harness_memory_deliveries").fetchone()[0] == 1


def test_changed_evidence_gets_new_lesson_and_withdrawal_rejects(canvas, monkeypatch):
    original = shared.enqueue(canvas, "pub-one")
    changed = assessment()
    changed["evidenceDigest"] = "f" * 64
    monkeypatch.setattr(shared, "_assessment", lambda _c, p: {**changed, "publication": p})
    revised = shared.enqueue(canvas, "pub-one")
    assert revised["lessonDigest"] != original["lessonDigest"]
    withdrawn = {**changed, "eligible": False}
    monkeypatch.setattr(shared, "_assessment", lambda _c, p: {**withdrawn, "publication": p})
    with pytest.raises(ValueError, match="eligible"):
        shared.enqueue(canvas, "pub-one")


def queued(canvas):
    shared.enqueue(canvas, "pub-one")
    return {"key": ("project-a", "workspace-a", "execution-1", 41, "candidate-x"),
            "node": "node-1", "payload": canvas.db.execute("SELECT payload FROM harness_memory_deliveries").fetchone()[0]}


def test_job_binding_tamper_and_current_evidence_changes_are_detected(canvas, monkeypatch):
    job = queued(canvas)
    assert shared.valid_job(canvas.db, job) and shared.current(canvas, job)
    bad = copy.deepcopy(job)
    bad["key"] = (*bad["key"][:4], "other")
    assert not shared.valid_job(canvas.db, bad)
    bad = copy.deepcopy(job)
    payload = json.loads(bad["payload"])
    payload["problem"] = "private edited"
    bad["payload"] = json.dumps(payload)
    assert not shared.valid_job(canvas.db, bad)
    changed = assessment()
    changed["evidenceDigest"] = "f" * 64
    monkeypatch.setattr(shared, "_assessment", lambda _c, p: {**changed, "publication": p})
    assert not shared.current(canvas, job)
    monkeypatch.setattr(shared, "_assessment", lambda _c, p: {**assessment(), "publication": p, "eligible": False})
    assert not shared.current(canvas, job)


class RoleClient:
    def __init__(self, content=None, callback=None):
        self.content, self.callback = content, callback
        self.requests = []

    def _request(self, method, path, **kwargs):
        self.requests.append((method, path, kwargs))
        if self.callback:
            self.callback()
        return {"status": "ok", "result": self.content}

    _envelope = staticmethod(OpenVikingClient._envelope)


class Memory:
    def __init__(self, client):
        self.client = client

    def enabled(self):
        return True

    def _role_client(self, role):
        assert role == "role-backend"
        return self.client


def submitted(canvas, content, callback=None):
    job = queued(canvas)
    from backend.library.harness_memory import memory_uri
    stored_job = {"key": job["key"], "node": job["node"]}
    uri = memory_uri(stored_job, "role-backend")
    with canvas.db:
        canvas.db.execute("UPDATE harness_memory_deliveries SET state='submitted',role_id='role-backend',uri=?", (uri,))
    client = RoleClient(content, callback)
    canvas.memory_service = Memory(client)
    return job, client


def test_recall_unavailable_until_ack_then_reads_exact_remote_content(canvas):
    lesson = shared.snapshot(canvas, "pub-one")
    assert shared.recall(canvas, "pub-one")["status"] == "unavailable"
    submitted(canvas, json.dumps(lesson, sort_keys=True))
    result = shared.recall(canvas, "pub-one")
    assert result["status"] == "verified-readback" and result["lesson"] == lesson
    assert result["promotionAllowed"] is False and result["executionAuthority"] is False


def test_wrong_remote_content_and_withdrawal_during_readback_refuse(canvas, monkeypatch):
    submitted(canvas, "{}")
    with pytest.raises(Exception, match="readback"):
        shared.recall(canvas, "pub-one")
    monkeypatch.setattr(shared, "_assessment", lambda _c, p: {**assessment(), "publication": p})
    lesson = shared.snapshot(canvas, "pub-one")
    client = RoleClient(json.dumps(lesson), callback=lambda: monkeypatch.setattr(
        shared, "_assessment", lambda _c, p: {**assessment(), "publication": p, "eligible": False}))
    canvas.memory_service = Memory(client)
    with pytest.raises(ValueError, match="eligible"):
        shared.recall(canvas, "pub-one")


def test_tampered_remote_uri_is_rejected_before_read(canvas):
    _, client = submitted(canvas, "{}")
    with canvas.db:
        canvas.db.execute("UPDATE harness_memory_deliveries SET uri='viking://user/role-backend/private.md'")
    with pytest.raises(ValueError, match="URI"):
        shared.recall(canvas, "pub-one")
    assert client.requests == []


def test_real_worker_checks_shared_evidence_outside_locks_and_withdrawal_after_write(canvas, monkeypatch):
    shared.enqueue(canvas, "pub-one")
    with canvas.db:
        canvas.db.execute("UPDATE harness_memory_deliveries SET role_id='role-backend'")
    positive = [True]
    def assess(_canvas, publication):
        assert not canvas.db.in_transaction, "cross-project assessment must not hold queue transaction"
        return {**assessment(), 'eligible': positive[0], 'publication': publication}
    monkeypatch.setattr(shared, '_assessment', assess)
    class Client(RoleClient):
        def write(self, role, uri, text, tags):
            assert not canvas.db.in_transaction
            assert 'kind=harness-shared' in tags
            self.content = text
            self.requests.append(uri)
            positive[0] = False
    client = Client()
    canvas.memory_service = Memory(client)
    worker = HarnessMemory(canvas, canvas.memory_service)
    assert worker.run_once() == ['superseded']
    assert canvas.db.execute('SELECT state FROM harness_memory_deliveries').fetchone()[0] == 'superseded'
    with pytest.raises(ValueError, match='eligible'):
        shared.recall(canvas, 'pub-one')
    positive[0] = True
    assert shared.enqueue(canvas, 'pub-one')['state'] == 'pending'
    assert canvas.db.execute('SELECT COUNT(*) FROM harness_memory_deliveries').fetchone()[0] == 1
    # A later successful delivery reuses the immutable address, without a second queue item.
    def write(role, uri, text, tags):
        client.content = text
        client.requests.append(uri)
    client.write = write
    assert worker.run_once() == ['submitted']
    assert client.requests[0] == client.requests[1]
    assert shared.recall(canvas, 'pub-one')['status'] == 'verified-readback'


def test_worker_never_writes_a_withdrawn_shared_lesson(canvas, monkeypatch):
    shared.enqueue(canvas, 'pub-one')
    with canvas.db:
        canvas.db.execute("UPDATE harness_memory_deliveries SET role_id='role-backend'")
    monkeypatch.setattr(shared, '_assessment', lambda *_: {**assessment(), 'eligible': False})
    client = RoleClient()
    assert HarnessMemory(canvas, Memory(client)).run_once() == ['superseded']
    assert client.requests == []
