"""`lease.heartbeat` is told on an observable change or as a periodic keep-alive, never once per renewal."""
from datetime import UTC, datetime, timedelta

import pytest

from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas.opora_events import stamp
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_lease_events import heartbeat_interval_seconds, heartbeat_reason
from backend.canvas.test_opora_changesets import baseline, legacy_save
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_executions import claim, credentials
from database.repositories import opora_events as store


@pytest.fixture(autouse=True)
def no_pull_module():
    pulls.register(None)
    original = pulls.source
    pulls.source = lambda: pulls._override
    yield
    pulls.source = original
    pulls.register(None)


@pytest.fixture
def planned(service):
    legacy_save(service, goal="Read accepted task")
    baseline(service)
    return ExecutionResults(service)


def heartbeats(service):
    rows = store.page(service.db_for("draft"), "draft", None, 0, 1000)[0]
    return [row for row in rows if row["kind"] == "lease.heartbeat"]


def renew(planned, record, ttl=60):
    return planned.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": ttl})


def lease_expiry(service):
    return service.db_for("draft").execute("SELECT expires_at FROM card_leases WHERE node_id='a'").fetchone()[0]


def test_renewals_extend_the_lease_every_time_but_tell_the_feed_once(planned, service):
    record = claim(planned)
    expiries = []
    for _ in range(5):
        renewed = renew(planned, record)
        expiries.append(lease_expiry(service))
        assert renewed["expiresAt"] == expiries[-1]
    assert expiries == sorted(expiries) and len(set(expiries)) == 5  # the bookkeeping is unchanged
    told = heartbeats(service)
    assert len(told) == 1
    assert told[0]["data"] == {"capped": False, "epoch": record["epoch"], "expiresAt": told[0]["data"]["expiresAt"],
                               "reason": "first", "ttlSeconds": 60}


def test_quiet_renewal_emits_nothing_at_all(planned, service):
    record = claim(planned)
    renew(planned, record)
    mark = store.head(service.db_for("draft"))
    renew(planned, record)
    assert store.head(service.db_for("draft")) == mark


def test_keepalive_after_the_interval_and_a_changed_ttl_is_told(planned, service):
    record = claim(planned)
    renew(planned, record)
    db = service.db_for("draft")
    with db:  # The last told heartbeat is now 16 minutes old.
        db.execute("UPDATE opora_events SET at=? WHERE kind='lease.heartbeat'",
                   (stamp(datetime.now(UTC) - timedelta(minutes=16)),))
    renew(planned, record)
    renew(planned, record)
    assert [item["data"]["reason"] for item in heartbeats(service)] == ["first", "keepalive"]
    renew(planned, record, ttl=90)
    assert heartbeats(service)[-1]["data"]["reason"] == "ttl"


def test_interval_zero_tells_every_renewal(planned, service, monkeypatch):
    monkeypatch.setenv("OPORA_LEASE_HEARTBEAT_EVENT_MINUTES", "0")
    record = claim(planned)
    for _ in range(3):
        renew(planned, record)
    assert [item["data"]["reason"] for item in heartbeats(service)] == ["first", "keepalive", "keepalive"]


@pytest.mark.parametrize("value,seconds", [(None, 900), ("5", 300), ("0", 0), ("-1", 900), ("soon", 900)])
def test_interval_setting(monkeypatch, value, seconds):
    if value is None:
        monkeypatch.delenv("OPORA_LEASE_HEARTBEAT_EVENT_MINUTES", raising=False)
    else:
        monkeypatch.setenv("OPORA_LEASE_HEARTBEAT_EVENT_MINUTES", value)
    assert heartbeat_interval_seconds() == seconds


def test_reason_names_each_observable_change(monkeypatch):
    monkeypatch.delenv("OPORA_LEASE_HEARTBEAT_EVENT_MINUTES", raising=False)
    now = datetime.now(UTC)
    last = (stamp(now - timedelta(minutes=1)), {"epoch": 3, "ttlSeconds": 60, "capped": False})
    record = {"epoch": 3}
    normal = {"ttl": 60, "capped": False, "previous_expires": 1040.0, "stamp": 1000.0, "now": now}
    assert heartbeat_reason(None, record, **normal) == "first"
    assert heartbeat_reason(last, record, **normal) is None
    assert heartbeat_reason(last, {"epoch": 4}, **normal) == "epoch"
    assert heartbeat_reason(last, record, **(normal | {"ttl": 120})) == "ttl"
    assert heartbeat_reason(last, record, **(normal | {"capped": True})) == "capped"
    # Office renews every third of the TTL; under a third left means beats were missed and it recovered.
    assert heartbeat_reason(last, record, **(normal | {"previous_expires": 1015.0})) == "late"
    assert heartbeat_reason(last, record, **(normal | {"now": now + timedelta(minutes=15)})) == "keepalive"
