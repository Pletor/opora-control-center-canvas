"""Worker strážců (`docs/strazci.md` §2): jedno daemon vlákno spouští strážce, kterým uplynul interval.

Konfigurace (prostředí; `tools/opora.py` sem převádí `[strazci]` z opora.local.toml):
  OPORA_GUARDS_WORKER=0     vypne smyčku (testy volají `run_once(now)` ručně)
  OPORA_GUARDS_SECONDS      tick smyčky (výchozí 30 s); strážce sám běží nejvýš jednou za své `every_s`

Výjimka strážce se zachytí, zapíše do jeho stavu (`lastError`) a nikdy neshodí worker ani ostatní strážce.
Stav (`lastRunAt`, `lastOkAt`, `lastError`) je jen v paměti procesu, po restartu začíná znovu.
Strážce, který přeskočí (`run` vrátí `None`), mění jen `lastRunAt`.
"""
import logging
import os
import threading
import time

from backend.canvas.strazci import findings as store
from backend.canvas.strazci.registry import GuardContext, default_guards, validate_registry
from database.repositories.guard_findings import GuardFindings

LOGGER = logging.getLogger(__name__)
DEFAULT_SECONDS = 30.0


def interval():
    try:
        return max(0.5, float(os.environ.get("OPORA_GUARDS_SECONDS", DEFAULT_SECONDS)))
    except ValueError:
        return DEFAULT_SECONDS


def worker_enabled():
    return os.environ.get("OPORA_GUARDS_WORKER", "1") != "0"


class GuardianManager:
    def __init__(self, service, *, guards=None, clock=time.time, tick=None):
        self.service, self.clock, self.tick = service, clock, tick
        self.guards = validate_registry(default_guards() if guards is None else guards)
        self.stop, self.thread = threading.Event(), None
        self.lock = threading.Lock()
        self.states, self.memos = {}, {}

    def start(self):
        if not worker_enabled() or self.thread or self.stop.is_set():
            return
        self.thread = threading.Thread(target=self._loop, name="opora-strazci", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _loop(self):
        while not self.stop.wait(self.tick or interval()):
            try:
                self.run_once()
            except Exception:
                LOGGER.exception("Strážci: průchod selhal; worker běží dál.")

    def _state(self, project, guard):
        return self.states.setdefault((project, guard), {"lastRunAt": None, "lastOkAt": None, "lastError": None})

    def due(self, project, guard, now):
        last = self._state(project, guard.id)["lastRunAt"]
        return last is None or now - last >= guard.every_s

    def run_once(self, now=None):
        """Jeden průchod přes projekty a strážce; vrací `[{project, guard, outcome}]` za spuštěné strážce."""
        now = self.clock() if now is None else now
        results = []
        for project in self.service.project_ids():
            for guard in self.guards:
                if self.stop.is_set():
                    return results
                if self.due(project, guard, now):
                    results.append({"project": project, "guard": guard.id, "outcome": self.run_guard(project, guard, now)})
        return results

    def run_guard(self, project, guard, now):
        """Spustí jednoho strážce nad projektem; vrací `skipped`, `error` nebo diff `{new, ongoing, resolved}`."""
        with self.lock:
            state = self._state(project, guard.id)
            state["lastRunAt"] = now
            memo = dict(self.memos.get((project, guard.id), {}))
        try:
            found = guard.run(GuardContext(self.service, project, now, memo))
            if found is None:
                return "skipped"
            outcome = store.apply(self.service, project, guard.id, found, now)
        except Exception as error:  # izolace: chyba jednoho strážce nikdy neshodí ostatní
            LOGGER.warning("Strážce %s nad projektem %s selhal: %s", guard.id, project, error)
            with self.lock:
                state["lastError"] = f"{type(error).__name__}: {error}"[:500]
            return "error"
        with self.lock:
            state["lastOkAt"], state["lastError"] = now, None
            self.memos[(project, guard.id)] = memo
        return outcome

    def status(self, project):
        """`{guards: [{id, label, every_s, lastRunAt, lastOkAt, lastError?, open}], open: {block, warn, info}}`."""
        with self.service.reading(project):
            counts = GuardFindings(self.service.db_for(project), project).counts()
        totals = {severity: 0 for severity in reversed(store.SEVERITIES)}
        guards = []
        for guard in self.guards:
            with self.lock:
                state = dict(self._state(project, guard.id))
            opened = {severity: counts.get(guard.id, {}).get(severity, 0) for severity in reversed(store.SEVERITIES)}
            for severity, count in opened.items():
                totals[severity] += count
            item = {"id": guard.id, "label": guard.label, "every_s": guard.every_s,
                    "lastRunAt": _iso(state["lastRunAt"]), "lastOkAt": _iso(state["lastOkAt"]), "open": opened}
            if state["lastError"]:
                item["lastError"] = state["lastError"]
            guards.append(item)
        return {"guards": guards, "open": totals}


def _iso(value):
    return None if value is None else store.at_of(value)
