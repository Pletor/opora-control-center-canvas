import pytest

from backend.agi_pletor.monitoring.detector import detect

OK, FAIL, SLOW = {"ok": True, "latency_ms": 100}, {"ok": False, "latency_ms": None}, {"ok": True, "latency_ms": 2500}


@pytest.mark.parametrize("results, expected", [
    ([], "ok"),
    ([FAIL, FAIL], "ok"),
    ([FAIL, FAIL, FAIL], "down"),
    ([OK, FAIL, FAIL, FAIL], "down"),
    ([FAIL, FAIL, FAIL, OK], "ok"),
    ([FAIL, OK, FAIL], "ok"),
    ([SLOW, SLOW], "ok"),
    ([SLOW, SLOW, SLOW], "slow"),
    ([SLOW, OK, SLOW], "ok"),
    ([SLOW, SLOW, FAIL], "ok"),
])
def test_detect(results, expected):
    assert detect(results) == expected


def test_thresholds_are_parameters():
    assert detect([OK, OK, OK], slow_ms=50) == "slow"
    assert detect([SLOW, SLOW, SLOW], slow_ms=3000) == "ok"
    assert detect([FAIL, FAIL], streak=2) == "down"
