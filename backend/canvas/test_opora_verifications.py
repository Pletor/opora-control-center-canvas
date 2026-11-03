"""Formal imports preserve execution authority, immutable pins and inert trust."""
import base64
import copy
import hashlib

import pytest

from backend.canvas.opora_verifications import OporaVerifications
from backend.canvas.test_opora_executions import authority as authority  # noqa: PLC0414
from backend.canvas.test_opora_executions import claim, credentials
from backend.canvas.test_opora_executions import service as service  # noqa: PLC0414
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def artifact(path="Main.lean", role="proof", data=b"theorem identity : True := True.intro"):
    return {"path": path, "role": role, "sha256": hashlib.sha256(data).hexdigest(),
            "dataBase64": base64.b64encode(data).decode("ascii")}


def verification():
    return {"tool": {"name": "lean", "version": "4.20", "distributionSha256": "a" * 64},
            "source": {"repository": "owner/repository", "commitSha": "a" * 40},
            "claims": [{"id": "identity", "kind": "theorem", "statement": "True"}],
            "assumptions": [], "configuration": {"axioms": [], "mode": "proof-check"},
            "artifacts": [artifact()]}


def request(execution, request_id="formal1"):
    return {**credentials(execution), "executionId": execution["executionId"],
            "requestId": request_id, "verification": verification()}


def report(execution, request_id="report1"):
    return {**credentials(execution), "requestId": request_id,
            "report": {"outcome": "passed", "checkedClaims": ["identity"], "summary": "Reported proof check",
                       "artifacts": [artifact("stdout.txt", "stdout", b"Reported success\r\n")]}}


def test_import_replay_pins_bytes_and_no_completion(authority, service):
    execution = claim(authority)
    ledger = OporaVerifications(service)
    before = DesktopV3State(service).read("draft", "draft")
    payload = request(execution)
    saved = ledger.create(payload)
    assert saved == ledger.create(payload)
    assert saved["acceptedRevision"] == execution["acceptedRevision"]
    assert saved["assignmentDigest"] == execution["assignmentDigest"]
    assert saved["trust"] == "agent-reported" and not saved["independentlyVerified"]
    assert not saved["currentEligibility"] and saved["sourceBinding"] == "agent-reported"
    assert "dataBase64" not in str(saved) and execution["token"] not in str(saved)
    assert len(saved["requestDigest"]) == 64 and len(saved["manifestDigest"]) == 64
    result = ledger.submit_report(saved["id"], report(execution))
    assert result["outcome"] == "passed" and result["trust"] == "agent-reported"
    assert not result["independentlyVerified"] and not result["currentEligibility"]
    assert DesktopV3State(service).read("draft", "draft") == before
    assert authority.heartbeat(execution["executionId"], {**credentials(execution), "ttlSeconds": 60})["state"] == "running"
    authority.submit(execution["executionId"], {**credentials(execution), "requestId": "done", "result": {"summary": "Done"}})
    assert ledger.submit_report(saved["id"], report(execution)) == result
    assert ledger.create(payload)["id"] == saved["id"]
    changed = copy.deepcopy(payload)
    changed["verification"]["claims"][0]["statement"] = "False"
    with pytest.raises(ValueError, match="different content"):
        ledger.create(changed)
    with pytest.raises(ValueError, match="different report"):
        ledger.submit_report(saved["id"], report(execution, "another"))


@pytest.mark.parametrize("revoke", ["expire", "release", "accepted"])
def test_new_requests_and_reports_require_current_authority(authority, service, revoke):
    execution = claim(authority)
    ledger = OporaVerifications(service)
    saved = ledger.create(request(execution))
    if revoke == "expire":
        with service.db_for("draft") as db:
            db.execute("UPDATE card_leases SET expires_at=0")
    elif revoke == "release":
        authority.release(execution["executionId"], credentials(execution))
    else:
        from backend.canvas.test_opora_changesets import accept, propose
        accept(service, propose(service, nodes=("a",)), execution["acceptedRevision"])  # autoritu bere změna vlastní karty
    with pytest.raises(ValueError):
        ledger.create(request(execution, "new"))
    with pytest.raises(ValueError):
        ledger.submit_report(saved["id"], report(execution))
    assert ledger.create(request(execution))["id"] == saved["id"]


@pytest.mark.parametrize("operation", ["create", "report"])
def test_late_expiry_rolls_back_uploaded_blobs(authority, service, monkeypatch, operation):
    from database.repositories.opora_verifications import Verifications
    execution = claim(authority)
    ledger = OporaVerifications(service)
    saved = ledger.create(request(execution)) if operation == "report" else None
    db = service.db_for("draft")
    previous = db.execute("SELECT COUNT(*) FROM opora_verification_blobs").fetchone()[0]
    original = Verifications.store_blobs
    def expire(store, blobs):
        original(store, blobs)
        store.db.execute("UPDATE card_leases SET expires_at=0")
    monkeypatch.setattr(Verifications, "store_blobs", expire)
    with pytest.raises(ValueError, match="authoritative"):
        if saved:
            ledger.submit_report(saved["id"], report(execution))
        else:
            ledger.create(request(execution))
    assert db.execute("SELECT COUNT(*) FROM opora_verification_blobs").fetchone()[0] == previous
    assert db.execute("SELECT COUNT(*) FROM opora_verification_reports").fetchone()[0] == 0
    assert authority.heartbeat(execution["executionId"], {**credentials(execution), "ttlSeconds": 60})["state"] == "running"


def test_blob_integrity_scope_manifest_and_graph_independence(authority, service, monkeypatch):
    execution = claim(authority)
    ledger = OporaVerifications(service)
    saved = ledger.create(request(execution))
    fingerprint = saved["verification"]["artifacts"][0]["sha256"]
    assert ledger.artifact(saved["id"], fingerprint, "draft", "draft").startswith(b"theorem")
    with pytest.raises(ValueError, match="scope"):
        ledger.read(saved["id"], "draft", "other")
    with pytest.raises(ValueError, match="manifest"):
        ledger.artifact(saved["id"], "f" * 64, "draft", "draft")
    monkeypatch.setattr(service, "view", lambda *args: pytest.fail("History must not read live graph"))
    assert ledger.history("draft", "draft")["requests"][0]["id"] == saved["id"]
    with service.db_for("draft") as db:
        db.execute("UPDATE opora_verification_blobs SET data=?", (b"corrupted",))
    assert ledger.read(saved["id"], "draft", "draft")["verification"]["artifacts"][0]["available"] is False
    with pytest.raises(ValueError, match="corrupt"):
        ledger.artifact(saved["id"], fingerprint, "draft", "draft")
    with service.db_for("draft") as db:
        db.execute("DELETE FROM opora_verification_blobs")
    assert ledger.history("draft", "draft")["requests"][0]["verification"]["artifacts"][0]["available"] is False


def test_project_and_combined_quota_are_atomic(authority, service, monkeypatch):
    from backend.canvas import opora_verification_validation as limits
    ledger = OporaVerifications(service)
    execution = claim(authority)
    monkeypatch.setattr(limits, "PROJECT_LIMIT", 1)
    with pytest.raises(ValueError, match="quota"):
        ledger.create(request(execution))
    db = service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_verification_blobs").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM opora_verification_requests").fetchone()[0] == 0
    monkeypatch.setattr(limits, "PROJECT_LIMIT", 64 * 1024 * 1024)
    saved = ledger.create(request(execution))
    monkeypatch.setattr(limits, "RUN_LIMIT", 40)
    with pytest.raises(ValueError, match="inputs and outputs"):
        ledger.submit_report(saved["id"], report(execution))
    assert db.execute("SELECT COUNT(*) FROM opora_verification_reports").fetchone()[0] == 0
