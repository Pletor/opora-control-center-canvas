from datetime import UTC, datetime, timedelta

from backend.flow.stalls import stall_reason

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def test_running_without_or_with_old_heartbeat():
    assert "bez heartbeatu" in stall_reason({"status": "running"}, NOW)
    old = {"status": "running", "last_heartbeat_at": (NOW - timedelta(minutes=12)).isoformat()}
    assert "12 min" in stall_reason(old, NOW)
    fresh = {"status": "running", "last_heartbeat_at": (NOW - timedelta(minutes=1)).isoformat()}
    assert stall_reason(fresh, NOW) is None


def test_waiting_after_deadline_and_finished_rows():
    late = {"status": "waiting", "waiting_for": "human", "deadline": (NOW - timedelta(seconds=1)).isoformat()}
    assert "deadline vypršel" in stall_reason(late, NOW)
    on_time = {"status": "waiting", "waiting_for": "human", "deadline": (NOW + timedelta(hours=1)).isoformat()}
    assert stall_reason(on_time, NOW) is None
    assert stall_reason({"status": "succeeded"}, NOW) is None
