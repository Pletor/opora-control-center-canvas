"""Jedno vyhodnocení: každý klíč tabulky §2a, next ⇔ allowed, nová revize po začlenění, sha kontrol a přijetí."""
import pytest

from backend.agi_pletor.linie.evaluate import axes, evaluate, evidence

H, OLD, M, N = "a" * 40, "b" * 40, "c" * 40, "d" * 40
GREEN = [{"name": "npm test", "status": "green", "sha": H, "at": "2026-11-07T10:00:00Z"}]
BASE = {"branch": "feat/x", "target": "develop", "headSha": H}
MERGED = {"sha": M, "target": "develop", "at": "2026-11-07T11:00:00Z"}

CASES = {
    "blocked": ({**BASE, "blocked": {"reason": "chybí klíč"}, "merged": MERGED}, None),
    "merged": ({**BASE, "checks": GREEN, "acceptance": {"sha": H}, "merged": MERGED}, None),
    "deferred": ({**BASE, "deferred": True}, None),
    "todo": ({"branch": "feat/x", "headSha": None, "runs": []}, None),
    "wip": ({"branch": "feat/x", "headSha": None, "runs": [{"sessionId": "s1", "startedAt": "t"}]}, None),
    "failed": ({**BASE, "checks": GREEN + [{"name": "lint", "status": "red", "sha": H}]}, None),
    "nocheck": ({**BASE, "checks": [], "acceptance": {"sha": OLD}}, None),
    "checking": ({**BASE, "checks": [{"name": "ci", "status": "pending", "sha": H}]}, None),
    "stale": ({**BASE, "checks": GREEN, "acceptance": {"sha": OLD}}, None),
    "pending": ({**BASE, "checks": GREEN}, None),
    "accepted": ({**BASE, "checks": GREEN, "acceptance": {"sha": H},
                  "mergeAllowed": {"sourceSha": H, "target": "develop"}}, None),
    "new_revision": ({**BASE, "checks": GREEN, "acceptance": {"sha": H}, "merged": MERGED}, N),
}
EXPECTED = {"new_revision": "wip"}


@pytest.mark.parametrize("name", CASES)
def test_each_key_of_table(name):
    work, after = CASES[name]
    found = evaluate(work, after)
    assert found["key"] == EXPECTED.get(name, name) and found["text"] and found["reason"] and found["next"]
    assert {"block", "unblock"} <= set(found["allowed"])  # §2a: block/unblock vždy
    assert set(found["blocked"]) == {"accept", "merge", "attempt"} - set(found["allowed"])


@pytest.mark.parametrize("name", CASES)
def test_next_is_consistent_with_allowed(name):
    found = evaluate(*CASES[name])
    if "přijme" in found["next"]:
        assert "accept" in found["allowed"]
    if "začlení" in found["next"]:
        assert "merge" in found["allowed"]
    for action, why in found["blocked"].items():
        assert why.startswith(found["reason"])  # zákaz nese důvod z téhož pravidla


def test_allowed_per_table():
    allowed = {name: evaluate(*CASES[name])["allowed"] for name in CASES}
    assert allowed["blocked"] == ["unblock", "block"] and allowed["todo"][0] == "attempt"
    assert "accept" in allowed["stale"] and "accept" in allowed["pending"] and "merge" in allowed["accepted"]
    assert allowed["deferred"][0] == "resume"
    for name in ("merged", "wip", "failed", "nocheck", "checking"):
        assert set(allowed[name]) == {"block", "unblock"}, name


def test_new_revision_after_merge_is_evaluated_not_merged():
    found = evaluate(*CASES["new_revision"])
    assert found["key"] != "merged" and found["reason"].startswith(f"nová revize po začlenění {M[:7]} · ")
    assert found["axes"]["work"] == {"state": "in_progress", "sha": N, "src": "git log"}
    assert found["axes"]["acceptance"]["state"] == "stale" and found["axes"]["checks"]["state"] == "missing"


def test_checks_for_other_sha_are_nocheck_and_block_accept():
    work = {**BASE, "checks": [{"name": "t", "status": "green", "sha": OLD}], "acceptance": {"sha": OLD}}
    found = evaluate(work)
    assert found["key"] == "nocheck" and "accept" not in found["allowed"]
    assert found["axes"]["checks"] == {"state": "missing", "sha": OLD, "src": "report"}
    assert found["next"].startswith(f"CI ověří HEAD {H[:7]}.") and "teprve pak nové přijetí" in found["next"]


def test_acceptance_for_other_sha_is_stale():
    found = evaluate({**BASE, "checks": GREEN, "acceptance": {"sha": OLD}})
    assert found["key"] == "stale" and found["axes"]["acceptance"] == {"state": "stale", "sha": OLD,
                                                                       "src": "záznam přijetí"}


def test_accepted_without_merge_permission_does_not_promise_merge():
    found = evaluate({**BASE, "checks": GREEN, "acceptance": {"sha": H}})
    assert found["key"] == "accepted" and "merge" not in found["allowed"] and "allow-merge" in found["next"]


def test_axes_shape_and_evidence():
    ax = axes({**BASE, "checks": GREEN, "merged": MERGED})
    assert ax["work"]["state"] == "submitted" and ax["checks"]["state"] == "passed"
    # bez merge logu je work.merged jen důkaz gitu a způsob neověřen (§5a)
    assert ax["integration"] == {"state": "merged", "target": "develop", "sha": M, "at": MERGED["at"], "mode": None,
                                 "op": None, "src": "git"}
    assert ax["deploy"] == {"envs": {}, "src": "událost prostředí"}
    kinds = [item["kind"] for item in evidence({**BASE, "checks": GREEN, "merged": MERGED,
                                                "runs": [{"sessionId": "s1", "startedAt": "t"}]}, None, {"number": 7})]
    assert kinds == ["session", "commit", "check", "merge", "pr"]
