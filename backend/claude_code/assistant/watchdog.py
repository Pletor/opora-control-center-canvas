"""Limity procesů asistenta a hlídač, který je vynucuje (docs/asistent.md §3).

Nejvýš 3 živé procesy, po 15 min nečinnosti se proces ukončí (další zpráva ho obnoví přes
`--resume`), tah nad 30 min se zabije. Limity jsou injektovatelné kvůli testům.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class Limits:
    max_processes: int = 3
    idle_seconds: float = 15 * 60
    turn_seconds: float = 30 * 60
    tick_seconds: float = 5.0
    approval_seconds: float = 10 * 60  # bez rozhodnutí člověka do 10 min platí zamítnutí (§5.1)


def expired(lives, now, limits):
    """`{sid: (turn_started, last_activity)}` → `[(sid, overdue)]`; overdue = tah přes limit."""
    result = []
    for sid, (turn_started, last_activity) in lives.items():
        if turn_started is not None and now - turn_started > limits.turn_seconds:
            result.append((sid, True))
        elif turn_started is None and now - last_activity > limits.idle_seconds:
            result.append((sid, False))
    return result


class Watchdog:
    def __init__(self, sweep, tick_seconds):
        self._sweep = sweep
        self._tick = tick_seconds
        self._stop = threading.Event()
        self._thread = None

    def ensure(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="assistant-watchdog")
            self._thread.start()

    def _run(self):
        while not self._stop.wait(self._tick):
            self._sweep()

    def stop(self):
        self._stop.set()
