from backend.agi_pletor.monitoring.probes import probe


def test_up_is_ok_with_status_and_latency():
    seen = []

    def transport(host, health_path):
        seen.append((host, health_path))
        return {"state": "up", "httpStatus": 200, "latencyMs": 42, "detail": "HTTP 200"}

    assert probe("a.cz", "/health", transport=transport) == {"ok": True, "status": 200, "latency_ms": 42, "error": None}
    assert seen == [("a.cz", "/health")]


def test_unreachable_and_degraded_fail_with_detail():
    down = probe("a.cz", transport=lambda h, p: {"state": "unreachable", "httpStatus": 502, "latencyMs": 10, "detail": "HTTP 502"})
    assert down == {"ok": False, "status": 502, "latency_ms": 10, "error": "HTTP 502"}
    assert probe("a.cz", transport=lambda h, p: {"state": "degraded", "detail": ""})["error"] == "degraded"


def test_transport_exception_is_a_failed_measurement():
    def boom(host, health_path):
        raise RuntimeError("x")

    assert probe("a.cz", transport=boom) == {"ok": False, "status": None, "latency_ms": None, "error": "sonda selhala: x"}
