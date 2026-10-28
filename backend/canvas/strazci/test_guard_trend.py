"""Strážce trendu: osm čísel ve vzorku, žádné nálezy, retence 90 dní; falešný čas."""
import json

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.strazci import guard_trend
from backend.canvas.strazci.findings import at_of
from backend.canvas.strazci.registry import GuardContext
from database.repositories.guard_trend import GuardTrend

NOW = 1_800_000_000.0


@pytest.fixture
def service(tmp_path):
    instance = CanvasService(tmp_path / "data")
    yield instance
    instance.close()


def series(service, since=0.0):
    with service.reading("draft"):
        return GuardTrend(service.db_for("draft"), "draft").series(at_of(since))


def test_journey_counts_verify_only_passed_fresh_runs():
    journeys = [{"applicationId": "app", "id": name} for name in ("a", "b", "c", "d")]
    last = {("app", "a"): {"passed": True, "stale": False}, ("app", "b"): {"passed": True, "stale": True},
            ("app", "c"): {"passed": False, "stale": False}}
    assert guard_trend.journey_counts(journeys, last) == (1, 4)


def test_building_counts_cards_in_flight_but_not_closed():
    stages = [("a", "work", "runs_active"), ("b", "review", "human_review_required"), ("c", "plan", "card_in_plan"),
              ("d", "plan_writeback", "card_closed"), ("e", "merge", "awaiting_human_close")]
    assert guard_trend.building_count(stages, closed={"e"}) == 2


def test_run_samples_every_metric_and_reports_nothing(service):
    db = service.db_for("draft")
    with db:
        db.execute("INSERT INTO desktop_v3_state VALUES('draft','draft',1,?,'2026-10-28')",
                   (json.dumps({"nodes": {"a": {"done": {"confirmed": True}}, "b": {}}}),))
        db.execute("INSERT INTO opora_event_card_state VALUES('draft','draft','b','work','ok','runs_active',NULL,NULL,'x')")
    assert guard_trend.run(GuardContext(service, "draft", NOW)) == []
    values = {metric: points[-1]["value"] for metric, points in series(service).items()}
    assert set(values) == set(guard_trend.METRICS)
    assert values["cards.done"] == 1 and values["cards.building"] == 1 and values["holes"] == 0


def test_samples_older_than_ninety_days_are_pruned(service):
    guard_trend.record(service, "draft", {"holes": 3}, NOW - 91 * 86400)
    guard_trend.record(service, "draft", {"holes": 2}, NOW - 89 * 86400)
    guard_trend.record(service, "draft", {"holes": 1}, NOW)
    assert [point["value"] for point in series(service)["holes"]] == [2, 1]
    assert [point["value"] for point in series(service, NOW - 3600)["holes"]] == [1]
