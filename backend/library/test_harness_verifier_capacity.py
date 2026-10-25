"""Capacity snapshots share admission counters without granting new execution authority."""
import json

import pytest

from backend.library.harness_verifier_budget import read
from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import payload
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414
from backend.library.test_harness_verifier_budget import limit


def test_counter_tracks_real_admission_and_repeated_reads_reserve_nothing(setup, monkeypatch):
    verifier, canvas, _, record, calls, _ = setup
    limit(monkeypatch, 1)
    before = read(canvas, "draft", "draft")
    assert (before["limit"], before["admitted"], before["remaining"]) == (1, 0, 1)
    assert before["capacityAvailable"] is True and before["reservation"] is False
    assert read(canvas, "draft", "draft") == before and calls == []
    verifier.verify(payload(record))
    after = read(canvas, "draft", "draft")
    assert (after["limit"], after["admitted"], after["remaining"]) == (1, 1, 0)
    assert after["capacityAvailable"] is False
    limit(monkeypatch, 0)
    assert read(canvas, "draft", "draft")["remaining"] == 0


@pytest.mark.parametrize("config,status", [(None, "disabled"), ("{", "unavailable"),
    (json.dumps({"project": "other", "workspace": "draft", "image": "node@sha256:" + "a" * 64,
                 "maxExperiments": 999}), "not-configured-for-scope")])
def test_missing_or_foreign_configuration_does_not_leak_limit_or_fake_available_capacity(setup, monkeypatch, config, status):
    _, canvas, _, _, calls, _ = setup
    if config is None:
        monkeypatch.delenv("OPORA_HARNESS_VERIFIER")
    else:
        monkeypatch.setenv("OPORA_HARNESS_VERIFIER", config)
    result = read(canvas, "draft", "draft")
    assert result["status"] == status
    assert result["limit"] is result["remaining"] is None
    assert result["capacityAvailable"] is False and result["reservation"] is False
    assert result["admitted"] == 0 and calls == []
