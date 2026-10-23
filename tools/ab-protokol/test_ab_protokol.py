"""Harness A/B protokolu: běží offline na dočasných datech a dává stabilní, doložitelné výsledky."""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ab_meter import FIXTURE, fixture, isolated_env  # noqa: E402
from ab_score import RUBRIC, transfer  # noqa: E402


@pytest.fixture(scope="module")
def runs():
    from ab_hub import Hub
    from ab_legacy import Legacy

    with isolated_env():
        out = {}
        for name, factory in (("A", Legacy), ("B", Hub), ("B+", lambda: Hub(predecessors=True))):
            sim = factory()
            try:
                sim.run()
                out[name] = {"outcome": sim.outcome, "transfer": transfer(sim), "root": sim.root,
                             "calls": list(sim.meter.calls)}
            finally:
                sim.close()
        yield out


def test_fixture_is_a_redacted_read_only_copy():
    data = fixture()
    assert len(data["cards"]) == 3 and len(data["edges"]) == 2
    assert [e["source"] for e in data["edges"]] == [c["id"] for c in data["cards"][:2]]
    assert "://" not in json.dumps({k: v for k, v in data.items() if k != "source"})
    assert all(v["nodeBriefBytes"] > 200_000 for v in data["live"].values())
    assert FIXTURE.stat().st_size < 64_000


def test_rubric_weights_sum_to_100():
    assert sum(weight for _, _, weight, _ in RUBRIC) == 100


def test_runs_stay_offline_in_a_temporary_folder(runs):
    base = Path(os.environ.get("AB_PROTOKOL_TMP") or tempfile.gettempdir()).resolve()
    for item in runs.values():
        root = Path(item["root"]).resolve()
        assert base in root.parents and "opora-data" not in str(root)
        assert all(call.path.startswith("/api/") for call in item["calls"])


def test_both_protocols_carry_three_cards_to_human_acceptance(runs):
    for name in ("A", "B"):
        cards = [v for k, v in runs[name]["outcome"].items() if isinstance(v, dict) and "accepted" in v]
        assert len(cards) == 3 and all(c["accepted"] == 200 for c in cards), runs[name]["outcome"]


def test_legacy_brief_carries_handoff_and_hub_assignment_does_not(runs):
    assert all(row["found"]["předávka"] and row["found"]["rozhodnutí"] for row in runs["A"]["transfer"])
    assert all(row["score"] == 0 for row in runs["B"]["transfer"])
    assert all(row["score"] >= 5 / 6 for row in runs["B+"]["transfer"])


def test_hub_lens_after_result_is_refused(runs):
    """Office posílá Lens až po výsledku; server ho odmítne, protože běh už nemá oprávnění."""
    first = next(v for v in runs["B"]["outcome"].values() if isinstance(v, dict) and "lens" in v)
    assert first["lens"] == 409 and "no longer authoritative" in first["lensDetail"]


def test_legacy_step_todos_invalidate_the_agents_own_context(runs):
    assert len(runs["A"]["outcome"]["selfConflicts"]) == 3
