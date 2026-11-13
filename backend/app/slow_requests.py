"""Pomalé požadavky serveru (docs/navrhy/2026-11-13-pruhled-srdce.md §3): co server dělal, když zápis srdce čekal.

Middleware zapíše každý požadavek delší než `THRESHOLD_MS` do kruhové paměti procesu (po restartu prázdná).
Průhled srdce z ní ukazuje, co v tu chvíli drželo server nebo zámek projektu. Jen cesta a projekt, nic z těla.
"""
import threading
import time
from collections import deque

THRESHOLD_MS = 5000
_RECENT = deque(maxlen=200)
_LOCK = threading.Lock()


def note(method, path, project, started, status, now=None):
    """`started` = `time.perf_counter()` na začátku požadavku. Rychlý požadavek se nezapíše."""
    ms = int((time.perf_counter() - started) * 1000)
    if ms >= THRESHOLD_MS:
        with _LOCK:
            end = time.time() if now is None else now
            _RECENT.append({"at": end - ms / 1000, "method": method, "path": path,  # at = začátek požadavku
                            "project": project or None, "ms": ms, "status": status})


def recent(since):
    """Pomalé požadavky od `since` (unix čas), nejdelší první."""
    with _LOCK:
        found = [dict(item) for item in _RECENT if item["at"] >= since]
    return sorted(found, key=lambda item: -item["ms"])
