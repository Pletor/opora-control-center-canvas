"""Detektor stavu hostu: čistá funkce nad posledními měřeními (nejnovější poslední) → `ok|slow|down`."""

SLOW_MS = 2000
STREAK = 3


def detect(results, slow_ms=SLOW_MS, streak=STREAK):
    """`down` = `streak` neúspěchů po sobě, `slow` = `streak` úspěchů po sobě nad `slow_ms`, jinak `ok`."""
    last = results[-streak:]
    if len(last) < streak:
        return "ok"
    if not any(r["ok"] for r in last):
        return "down"
    if all(r["ok"] and (r.get("latency_ms") or 0) > slow_ms for r in last):
        return "slow"
    return "ok"
