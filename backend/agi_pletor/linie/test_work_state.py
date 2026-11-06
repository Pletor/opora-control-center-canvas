"""Stav kuličky z `work`: tabulka případů podle kontraktu §2."""
import pytest

from backend.agi_pletor.linie.work_state import state

H, OLD, T = "a" * 40, "b" * 40, "c" * 40
GREEN = [{"name": "npm test", "status": "green", "sha": H}]
ACC = {"sha": H}
ALLOW = {"target": "develop", "targetSha": T, "sourceSha": H}


@pytest.mark.parametrize("work, tip, expected", [
    ({}, None, "open"),
    ({"headSha": None, "branch": "feat/x"}, None, "open"),
    ({"headSha": H}, None, "awaiting_checks"),
    ({"headSha": H, "checks": [{"name": "t", "status": "pending", "sha": H}]}, None, "awaiting_checks"),
    ({"headSha": H, "checks": GREEN + [{"name": "lint", "status": "red", "sha": H}]}, None, "awaiting_checks"),
    ({"headSha": H, "checks": [{"name": "t", "status": "green", "sha": OLD}]}, None, "awaiting_checks"),
    ({"headSha": H, "checks": GREEN}, None, "open"),
    ({"headSha": H, "checks": GREEN, "acceptance": ACC}, None, "accepted_unmerged"),
    ({"headSha": H, "checks": [], "acceptance": ACC}, None, "awaiting_checks"),
    ({"headSha": H, "checks": GREEN, "acceptance": ACC, "mergeAllowed": ALLOW}, T, "accepted_unmerged"),
    ({"headSha": H, "checks": GREEN, "acceptance": {"sha": OLD}}, None, "stale"),
    ({"headSha": H, "checks": GREEN, "acceptance": ACC, "mergeAllowed": {**ALLOW, "sourceSha": OLD}}, None, "stale"),
    ({"headSha": H, "checks": GREEN, "acceptance": ACC, "mergeAllowed": ALLOW}, OLD, "stale"),
    ({"headSha": H, "blocked": {"reason": "x"}, "acceptance": {"sha": OLD}}, None, "blocked"),
    ({"headSha": H, "deferred": True}, None, "deferred"),
    ({"headSha": H, "merged": {"sha": T}, "blocked": {"reason": "x"}}, None, "merged"),
])
def test_state_table(work, tip, expected):
    found = state(work, tip)
    assert found["state"] == expected and found["label"] and found["next"]


def test_labels():
    assert state({"merged": {"sha": T}})["label"] == "začleněno"
    assert state({"headSha": H, "acceptance": {"sha": OLD}})["label"] == "zastaralé přijetí"
