"""Multiple configured projects retain independent policy, budget and evidence authority."""
import json
import os

import pytest

from backend.library import harness_exploration as exploration
from backend.library import harness_stability as stability
from backend.library import harness_verifier_plan as plans
from backend.library.harness_scope_config import ScopeNotConfigured, select
from backend.library.harness_stability_retained import RetainedStability
from backend.library.test_harness_stability import prepared as prepared  # noqa: PLC0414
from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import payload
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414

VERIFIER = {"project": "draft", "workspace": "draft", "image": "node@sha256:" + "a" * 64, "maxExperiments": 10}
EXPLORATION = {"project": "draft", "workspace": "draft", "environment": "nonproduction"}
STABILITY = {"project": "draft", "workspace": "draft", "approvedPlanDigests": ["b" * 64]}


def envelope(*entries):
    return {"schema": "harness.scopes/1", "scopes": list(entries)}


@pytest.mark.parametrize("env,entry,read", [
    ("OPORA_HARNESS_VERIFIER", VERIFIER, plans.configuration),
    ("OPORA_HARNESS_EXPLORATION", EXPLORATION, exploration.policy),
    ("OPORA_HARNESS_STABILITY", STABILITY, stability.policy)])
def test_expand_and_rollback_preserve_selected_policy_and_deny_implicit_scope(monkeypatch, env, entry, read):
    monkeypatch.setenv(env, json.dumps(entry))
    before = read("draft", "draft")
    foreign = {**entry, "project": "second"}
    monkeypatch.setenv(env, json.dumps(envelope(foreign, entry)))
    assert read("draft", "draft") == before
    assert read("second", "draft") != before
    for project, workspace in [("absent", "draft"), ("draft", "absent"), (None, None)]:
        with pytest.raises(ValueError): read(project, workspace)
    monkeypatch.setenv(env, json.dumps(entry))
    assert read("draft", "draft") == before
    with pytest.raises(ScopeNotConfigured): read("second", "draft")


@pytest.mark.parametrize("entries", [[], [VERIFIER] * 2, [VERIFIER] * 33,
    [VERIFIER, {**VERIFIER, "project": "second", "maxExperiments": True}],
    [VERIFIER, {**VERIFIER, "project": "second", "image": "node:latest"}],
    [VERIFIER, None], [VERIFIER, {**VERIFIER, "project": "*"}]])
def test_invalid_or_duplicate_other_scope_cannot_hide_behind_valid_first_entry(monkeypatch, entries):
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(envelope(*entries)))
    with pytest.raises(ValueError): plans.configuration("draft", "draft")


def test_envelope_is_bounded_and_strict(monkeypatch):
    with pytest.raises(ValueError, match="64 KiB"):
        select(json.dumps(envelope(VERIFIER)) + " " * 65536, plans._configuration, "draft", "draft")
    for raw in [json.dumps({**envelope(VERIFIER), "default": VERIFIER}),
                '{"schema":"harness.scopes/1","schema":"harness.scopes/1","scopes":[]}']:
        monkeypatch.setenv("OPORA_HARNESS_VERIFIER", raw)
        with pytest.raises(ValueError): plans.configuration("draft", "draft")


def test_runtime_uses_exact_scope_image_limit_and_withdrawal(setup, monkeypatch):
    verifier, _, _, record, calls, _ = setup
    foreign = {**VERIFIER, "project": "second", "image": "node@sha256:" + "e" * 64, "maxExperiments": 0}
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(envelope(foreign, VERIFIER)))
    result = verifier.verify(payload(record))
    assert result["report"] is not None and len(calls) == 1
    assert calls[0][1] == VERIFIER["image"] and calls[0][2] is True
    assert verifier._current(payload(record), result) is True
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(envelope(foreign)))
    assert verifier._current(payload(record), result) is False
    with pytest.raises(ScopeNotConfigured): verifier.verify(payload(record))
    assert len(calls) == 1


def test_retained_evidence_survives_unrelated_scope_change_but_not_own_withdrawal(prepared, monkeypatch):
    live, _, record, report = prepared
    reader = RetainedStability(live.canvas)
    ref = {"project": record["project"], "workspace": record["workspace"], "verificationId": report["id"]}
    before = reader.assess(ref)
    for env in ("OPORA_HARNESS_VERIFIER", "OPORA_HARNESS_STABILITY"):
        entry = json.loads(os.environ[env])
        foreign = {**entry, "project": "second"}
        monkeypatch.setenv(env, json.dumps(envelope(foreign, entry)))
    assert reader.assess(ref) == before
    with pytest.raises(ValueError): reader.assess({**ref, "project": "second"})
    policy = json.loads(os.environ["OPORA_HARNESS_STABILITY"])
    monkeypatch.setenv("OPORA_HARNESS_STABILITY", json.dumps(envelope(policy["scopes"][0])))
    with pytest.raises(ScopeNotConfigured): reader.assess(ref)


def test_capacity_keeps_distinct_ceilings_and_spent_counts_with_two_configured_scopes(setup, monkeypatch):
    from backend.library.harness_verifier_budget import read
    from database.repositories.opora_verifications import Verifications

    verifier, canvas, _, record, _, _ = setup
    foreign = {**VERIFIER, "workspace": "second", "maxExperiments": 3}
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(envelope(foreign, {**VERIFIER, "maxExperiments": 1})))
    first = verifier.verify(payload(record))
    with canvas.db_for("draft") as db:
        Verifications(db, "draft", "second").insert({**first, "id": "other-scope", "workspace": "second", "requestId": "other-scope"})
    own, other = read(canvas, "draft", "draft"), read(canvas, "draft", "second")
    assert (own["admitted"], own["remaining"], own["capacityAvailable"]) == (1, 0, False)
    assert (other["admitted"], other["remaining"], other["capacityAvailable"]) == (1, 2, True)
    missing = read(canvas, "draft", "absent")
    assert missing["status"] == "not-configured-for-scope" and missing["remaining"] is None
