"""Kruhový buffer událostí jedné session: `seq` roste monotónně, drží se posledních 2000.

Událost delší než 64 KB (JSON v UTF-8) se zkrátí na nejdelším textovém poli a dostane
`"truncated": true`. Zpráva uživatele má vlastní strop (`max_bytes` v `append`), aby se dlouhé
zadání v historii nezkrátilo. Čtenáři SSE se ptají `after(seq)`; vlákno procesu jen přidává.
"""

from __future__ import annotations

import json
import threading
from collections import deque

MAX_EVENTS = 2000
MAX_EVENT_BYTES = 64 * 1024
# 60 000 znaků české zprávy i s escapováním JSON.
MAX_USER_MESSAGE_BYTES = 256 * 1024


def _size(event):
    return len(json.dumps(event, ensure_ascii=False).encode("utf-8"))


def truncate_event(event, limit=MAX_EVENT_BYTES):
    if _size(event) <= limit:
        return event
    result = dict(event, truncated=True)
    for _ in range(8):
        strings = [(len(value), key) for key, value in result.items() if isinstance(value, str)]
        if not strings:
            break
        _, key = max(strings)
        overflow = _size(result) - limit
        if overflow <= 0:
            return result
        value = result[key]
        keep = max(0, len(value.encode("utf-8")) - overflow - 64)
        result[key] = value.encode("utf-8")[:keep].decode("utf-8", errors="ignore")
    if _size(result) > limit:
        # Žádné textové pole nestačilo (např. obří usage): ponechá se jen kostra.
        result = {key: result[key] for key in ("type", "messageId", "id", "role") if key in result}
        result["truncated"] = True
    return result


class EventLog:
    def __init__(self, max_events=MAX_EVENTS, max_bytes=MAX_EVENT_BYTES):
        self._events = deque(maxlen=max_events)
        self._seq = 0
        self._max_bytes = max_bytes
        self._lock = threading.Lock()

    def append(self, event, max_bytes=None):
        with self._lock:
            self._seq += 1
            stored = {"seq": self._seq, **truncate_event(event, max_bytes or self._max_bytes)}
            self._events.append(stored)
            return stored

    @property
    def last_seq(self):
        with self._lock:
            return self._seq

    def after(self, seq):
        """Události s `seq > after`; `after` za koncem (restart backendu) začne od začátku."""
        with self._lock:
            start = seq if 0 <= seq <= self._seq else 0
            return [event for event in self._events if event["seq"] > start]
