import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.check_runs import CheckRuns

SCOPE = ("draft", "draft", "node-1")
OTHER = ("draft", "draft", "node-2")
SHA = "9f3a1c2b4d5e6f70819293a4b5c6d7e8f9012345"


@pytest.fixture
def runs(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        yield CheckRuns(service)
    finally:
        service.close()


def green(sha=SHA, detail="uv run pytest backend: 412 prošlo"):
    return {"sha": sha, "status": "green", "detail": detail}


def test_recorded_run_is_read_back_as_the_latest_one(runs):
    written = runs.record(SCOPE, green())

    assert written["scopeId"] == "node-1" and written["sha"] == SHA
    assert written["status"] == "green" and written["recordedAt"]
    assert runs.latest(SCOPE) == written
    assert runs.latest_for_project("draft", "draft") == {"node-1": written}


def test_correction_is_a_new_record_and_never_overwrites_the_older_one(runs):
    first = runs.record(SCOPE, {"sha": SHA, "status": "red", "detail": "dva testy spadly"})
    second = runs.record(SCOPE, green(detail="po opravě zelené"))

    assert second["recordedAt"] > first["recordedAt"]
    assert runs.latest(SCOPE)["status"] == "green"
    stored = runs.canvas.db_for("draft").execute(
        "SELECT status, detail FROM check_runs WHERE scope_id='node-1' ORDER BY recorded_at"
    ).fetchall()
    assert [row["status"] for row in stored] == ["red", "green"]
    assert stored[0]["detail"] == "dva testy spadly"


def test_latest_for_project_keeps_one_record_per_scope(runs):
    runs.record(SCOPE, green(detail="první"))
    runs.record(OTHER, {"sha": SHA, "status": "red", "detail": "jiný rozsah"})
    newest = runs.record(SCOPE, green(detail="druhý"))

    latest = runs.latest_for_project("draft", "draft")
    assert set(latest) == {"node-1", "node-2"}
    assert latest["node-1"] == newest and latest["node-2"]["status"] == "red"


@pytest.mark.parametrize("payload", [
    {"sha": SHA, "status": "zeleny", "detail": ""},
    {"sha": SHA, "status": None, "detail": ""},
    {"sha": "9f3a1c", "status": "green", "detail": ""},
    {"sha": "ZZZZZZZ", "status": "green", "detail": ""},
    {"sha": "9" * 65, "status": "green", "detail": ""},
    {"sha": SHA, "status": "green", "detail": "x" * 2001},
])
def test_invalid_run_is_refused_in_czech(runs, payload):
    with pytest.raises(ValueError) as error:
        runs.record(SCOPE, payload)

    assert str(error.value)
    assert runs.latest(SCOPE) is None


def test_invalid_scope_is_refused(runs):
    with pytest.raises(ValueError):
        runs.record(("draft", "draft", "node 1"), green())
    with pytest.raises(ValueError):
        runs.record(("draft", "draft"), green())


def test_empty_reading_says_nothing_instead_of_failing(runs):
    assert runs.latest(SCOPE) is None
    assert runs.latest_for_project("draft", "draft") == {}
