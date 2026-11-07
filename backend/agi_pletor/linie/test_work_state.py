"""Starý tvar stavu kuličky nad `evaluate`: tabulka případů (docs/navrhy/2026-11-06-linie-rebrand.md §2a)."""
import pytest

from backend.agi_pletor.linie.work_state import state

H, OLD, T = "a" * 40, "b" * 40, "c" * 40
GREEN = [{"name": "npm test", "status": "green", "sha": H}]
ACC = {"sha": H}
ALLOW = {"target": "develop", "targetSha": T, "sourceSha": H}


@pytest.mark.parametrize("work, expected", [
    ({}, "open"),
    ({"headSha": None, "branch": "feat/x"}, "open"),
    ({"headSha": H}, "awaiting_checks"),
    ({"headSha": H, "checks": [{"name": "t", "status": "pending", "sha": H}]}, "awaiting_checks"),
    ({"headSha": H, "checks": GREEN + [{"name": "lint", "status": "red", "sha": H}]}, "awaiting_checks"),
    ({"headSha": H, "checks": [{"name": "t", "status": "green", "sha": OLD}]}, "awaiting_checks"),
    ({"headSha": H, "checks": GREEN}, "open"),
    ({"headSha": H, "checks": GREEN, "acceptance": ACC}, "accepted_unmerged"),
    ({"headSha": H, "checks": [], "acceptance": ACC}, "awaiting_checks"),
    ({"headSha": H, "checks": GREEN, "acceptance": ACC, "mergeAllowed": ALLOW}, "accepted_unmerged"),
    ({"headSha": H, "checks": GREEN, "acceptance": {"sha": OLD}}, "stale"),
    # L7 §2a nezná mergeAllowed: povolení pro jiné SHA je jen další krok, posunutý cíl odmítne merge 409 (§8)
    ({"headSha": H, "checks": GREEN, "acceptance": ACC, "mergeAllowed": {**ALLOW, "sourceSha": OLD}},
     "accepted_unmerged"),
    ({"headSha": H, "blocked": {"reason": "x"}, "acceptance": {"sha": OLD}}, "blocked"),
    ({"headSha": H, "deferred": True}, "deferred"),
    ({"headSha": H, "merged": {"sha": T}, "blocked": {"reason": "x"}}, "blocked"),  # §2a: blocked je první pravidlo
])
def test_state_table(work, expected):
    found = state(work)
    assert found["state"] == expected and found["label"] and found["next"]


def test_labels_come_from_evaluate_text():
    assert state({"merged": {"sha": T, "target": "develop"}})["label"] == "začleněno do develop"
    assert state({"headSha": H, "checks": GREEN, "acceptance": {"sha": OLD}})["label"] == f"přijato pro starší {OLD[:7]}"
    assert state({"headSha": H, "merged": {"sha": T}}, after_merge="d" * 40)["state"] == "open"  # nová revize
