from backend.canvas import opora_agent_state_lease as lease


def _run(node, state="running", deadline=200.0, owner="agent:codex-2", epoch=3):
    return {"id": "x" + node, "nodeId": node, "state": state, "deadline": deadline, "owner": owner, "epoch": epoch}


def test_live_running_execution_has_lease():
    cards = lease.attach([{"nodeId": "a"}, {"nodeId": "b"}], [_run("a")], now=100.0)
    assert cards[0]["lease"] == {"holder": "agent:codex-2", "expiresAt": "1970-01-01T00:03:20Z", "epoch": 3}
    assert cards[1]["lease"] is None


def test_expired_or_finished_execution_has_no_lease():
    latest = [_run("a", deadline=50.0), _run("b", state="reported")]
    assert lease.leases(latest, now=100.0) == {}
