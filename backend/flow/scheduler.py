"""Plánovač enginu toků na pozadí: vlákno z lifespan aplikace (`backend/app/factory.py`).

Každý průchod (`TICK`, nebo hned po `wakeup`):
- zavolá `tick()` háčků (dnes `HeartDriver` v režimu `OPORA_FLOW_HEART=on`: rozvrh, události a zprávy srdce),
- posune běhy, které na něco čekají: vypršelý deadline (větev `timeout`), uzel bez heartbeatu (navázání pokusem
  `attempt + 1`) a zařazené uzly, které nikdo nevykonal (pád mezi zápisy).
Zámek registru drží jen kolem jednotlivých volání enginu, uzly mimo zámek si ho berou samy.
"""

import logging
import threading
from datetime import UTC, datetime

from backend.flow import interpreter
from backend.flow.stalls import list_stalls

LOGGER = logging.getLogger(__name__)
TICK = 2.0
DONE = ("succeeded", "failed", "cancelled")


def due_runs(db, now=None):
    """ID neukončených běhů, které potřebují `advance`: prostoj (`list_stalls`) nebo zařazený nevykonaný uzel."""
    stalled = {row["run_id"] for row in list_stalls(db, now or datetime.now(UTC))}
    queued = {row[0] for row in db.execute("SELECT DISTINCT run_id FROM flow_node_runs WHERE status='queued'")}
    ids = sorted(stalled | queued)
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = db.execute(f"SELECT id FROM flow_runs WHERE id IN ({marks}) AND status NOT IN {DONE}", ids).fetchall()
    return sorted(row["id"] for row in rows)


class FlowScheduler:
    def __init__(self, service, hooks=(), tick=TICK, wakeup=None):
        self.service, self.hooks, self.tick = service, list(hooks), tick
        self.wakeup = wakeup or threading.Event()
        self.stop, self.thread = threading.Event(), None

    def start(self):
        if self.thread or self.stop.is_set():
            return
        for hook in list(self.hooks):
            try:
                hook.start()
            except Exception:  # vadný háček se vyřadí, aplikace a ostatní běhy jedou dál
                LOGGER.exception("Tok: háček plánovače se nespustil.")
                self.hooks.remove(hook)
        self.thread = threading.Thread(target=self._loop, name="opora-flow", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        self.wakeup.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _loop(self):
        while not self.stop.is_set():
            self.wakeup.wait(self.tick)
            self.wakeup.clear()
            if self.stop.is_set():
                return
            try:
                self.run_once()
            except Exception:  # plánovač běží dál, chyba průchodu se jen zapíše
                LOGGER.exception("Tok: průchod plánovače selhal.")

    def run_once(self, now=None):
        """Jeden průchod; vrací ID posunutých běhů."""
        for hook in self.hooks:
            try:
                hook.tick()
            except Exception:  # háček nesmí zastavit posun ostatních běhů
                LOGGER.exception("Tok: háček plánovače selhal.")
        with self.service.registry_lock:
            ids = due_runs(self.service.db, now)
        for run_id in ids:
            try:
                with self.service.registry_lock:
                    interpreter.advance(self.service.db, run_id, now=now)
            except Exception:  # jeden vadný běh nezastaví ostatní
                LOGGER.exception("Tok: posun běhu %s selhal.", run_id)
        return ids
