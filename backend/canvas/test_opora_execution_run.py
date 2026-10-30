"""Profil běhu `run` v zadání (docs/navrhy/2026-10-30-metriky-a-spoustece.md §3): stabilní, připnutý z claimu."""
from backend.canvas import card_gauge
from backend.canvas.graph import digest
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_executions import authority as authority  # noqa: PLC0414
from backend.canvas.test_opora_executions import claim, credentials
from database.repositories.opora_executions import Executions


def heartbeat(authority, record):
    return authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})


def test_claim_pins_the_stable_run_profile(authority):
    record = claim(authority)
    run = record["assignment"]["run"]
    assert set(run) == {"label", "effort", "model", "advisor", "handout", "humanReview"}
    assert run["label"] in (*card_gauge.LABELS, card_gauge.UNKNOWN) and "age" not in run and "costUsd" not in run
    assert record["assignmentDigest"] == digest(record["assignment"])


def test_a_changed_label_during_the_run_does_not_revoke_it(authority, monkeypatch):
    record = claim(authority)
    monkeypatch.setattr(card_gauge, "profile", lambda *args, **kwargs: card_gauge.run_of(99, "critical"))
    assert heartbeat(authority, record)["state"] == "running"


def test_a_run_claimed_before_run_existed_stays_valid(authority, service):
    record = claim(authority)
    repo = Executions(service.db_for("draft"), *SCOPE.values())
    stored = repo.read(record["executionId"])
    stored["assignment"] = {key: value for key, value in stored["assignment"].items() if key != "run"}
    stored["assignmentDigest"] = digest(stored["assignment"])
    with service.db_for("draft"):
        repo.save(stored)
    assert heartbeat(authority, stored)["state"] == "running"
