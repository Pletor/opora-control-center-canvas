"""Supervisor srdce (docs/brain-heart.md §1, §2): spí, budí se na vstupy a pouští jednu dávku na projekt.

Vlákno (démon) sleduje outbox událostí projektů se zapnutou bránou: čekající lístek `ask` / `change`
a úkol `failed` přidají vstup s oknem 20 s, zpráva člověka budí hned. Dávka běží ve vlastním vlákně, nejvýš
jedna na projekt a nejvýš 6 automatických za hodinu (zpráva člověka strop obchází, prázdná dávka se nepočítá); vstup, který přijde během
dávky, počká na další. Vyčerpaný limit
předplatného uspí srdce na 15 min a vstupy zůstanou. Běží jen na loopbacku a jen bez `OPORA_HEART=off`.
"""
import logging
import os
import threading
import time
from collections import deque

from backend.brain_opora.determinism import brain_files, gate_setting, snapshot, tokens
from backend.brain_opora.heart import batch, command, session
from backend.brain_opora.heart.inputs import resolve, wake_input
from backend.canvas.process_signal import PROCESS_SIGNAL
from backend.project.workspace.workspace_sources import WorkspaceSources
from database.repositories import opora_events

LOGGER = logging.getLogger(__name__)
WINDOW, RATE_SLEEP, PER_HOUR, HOUR, TICK = 20.0, 15 * 60.0, 6, 3600.0, 2.0
LOOPBACK = ("127.0.0.1", "localhost", "::1")
PAGE = 200
POLL = 10.0  # pojistka: outbox se čte i bez signálu (nově zapnutá brána, události jiného procesu)


def enabled(environ=None):
    """Zapnuté, když `OPORA_HEART` není `off` a server poslouchá jen na loopbacku (`OPORA_CANVAS_HOST`)."""
    env = os.environ if environ is None else environ
    return env.get("OPORA_HEART", "on").strip().lower() != "off" and env.get("OPORA_CANVAS_HOST", "127.0.0.1") in LOOPBACK


def _thread(target):
    threading.Thread(target=target, name="opora-heart-batch", daemon=True).start()


class HeartSupervisor:
    def __init__(self, service, *, base_url, runner=None, clock=time.time, tick=TICK, spawn=_thread, find=None):
        self.service, self.base_url, self.clock, self.tick, self.spawn = service, base_url, clock, tick, spawn
        self.runner = runner or batch.run_process
        self.find = find or command.find_claude
        self.lock, self.stop, self.wakeup, self.thread = threading.Lock(), threading.Event(), threading.Event(), None
        self.pending, self.running, self.starts, self.cursors, self.tokens, self.errors = {}, set(), {}, {}, {}, {}
        self.sleeping_until, self.generation, self.polled_at = 0.0, None, float("-inf")

    def start(self):
        if not enabled() or self.thread or self.stop.is_set():
            return
        self.thread = threading.Thread(target=self._loop, name="opora-heart", daemon=True)
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
            except Exception:  # noqa: BLE001 - supervisor běží dál, chyba jednoho průchodu se jen zapíše
                LOGGER.exception("Srdce: průchod supervisoru selhal.")

    def _add(self, project, workspace, item, due):
        with self.lock:
            self.pending.setdefault(project, []).append((workspace, item, due))

    def message(self, project, workspace, text, now=None):
        """Zpráva člověka: nejdřív řádek do `brain/messages.jsonl` (přežije dávku i rotaci relace, §3a), pak vstup
        splatný hned; vrací počet čekajících vstupů projektu. Selhaný zápis se jen zaloguje, zpráva srdce budí dál."""
        now = self.clock() if now is None else now
        try:
            brain_files.append_message(self.brain(project), _iso(now), workspace, text)
        except OSError:
            LOGGER.exception("Srdce: zprávu člověka projektu %s nešlo uložit.", project)
        self._add(project, workspace, {"type": "message", "text": text}, now)
        self.wakeup.set()
        with self.lock:
            return len(self.pending[project])

    def poll_events(self, now):
        """Nové události projektů se zapnutou bránou → vstupy s oknem `WINDOW`; nový projekt začíná na konci."""
        for project in self.service.project_ids():
            if not gate_setting.is_on(self.service, project):
                continue
            with self.service.reading(project):
                db = self.service.db_for(project)
                cursor = self.cursors.get(project)
                if cursor is None:
                    self.cursors[project] = opora_events.head(db)
                    continue
                events = []
                while True:
                    chunk, _, _ = opora_events.page(db, project, None, cursor, PAGE)
                    events += chunk
                    if len(chunk) < PAGE:
                        break
                    cursor = chunk[-1]["id"]
            for event in events:
                self.cursors[project] = event["id"]
                item = wake_input(event)
                if item is not None:
                    self._add(project, event["workspaceId"], item, now + WINDOW)

    def next_allowed(self, project, now):
        """Nejbližší čas, kdy smí projekt začít dávku (spánek po limitu a strop dávek za hodinu)."""
        starts = self.starts.setdefault(project, deque())
        while starts and starts[0] <= now - HOUR:
            starts.popleft()
        capped = starts[0] + HOUR if len(starts) >= PER_HOUR else now
        return max(now, self.sleeping_until, capped)

    def run_once(self, now=None):
        """Jeden průchod: přečte události a pustí splatné dávky; vrací seznam projektů, kterým dávku pustil."""
        now = self.clock() if now is None else now
        if PROCESS_SIGNAL.generation != self.generation or now - self.polled_at >= POLL:
            self.generation, self.polled_at = PROCESS_SIGNAL.generation, now
            self.poll_events(now)
        started = []
        with self.lock:
            for project, items in list(self.pending.items()):
                if not items or project in self.running or min(due for _, _, due in items) > now:
                    continue
                # zpráva člověka strop za hodinu obchází (eval m2: strop zablokoval zadání), limit předplatného ne
                human = any(item.get("type") == "message" for _, item, _ in items)
                if (max(now, self.sleeping_until) if human else self.next_allowed(project, now)) > now:
                    continue
                workspace = items[0][0]
                taken = [item for space, item, _ in items if space == workspace]
                self.pending[project] = [entry for entry in items if entry[0] != workspace]
                self.running.add(project)
                started.append((project, workspace, taken))
        for project, workspace, taken in started:
            self.spawn(lambda p=project, w=workspace, t=taken: self._batch(p, w, t))
        return [project for project, _, _ in started]

    def _token(self, project, workspace):
        key = (project, workspace)
        if key not in self.tokens:  # token srdce jen v paměti a v prostředí procesu, nikdy na disku
            self.tokens[key] = tokens.issue_heart(self.service, project, workspace)[1]
        return self.tokens[key]

    def _source(self, project, workspace):
        try:
            return WorkspaceSources(self.service).root(project, workspace)
        except Exception:  # noqa: BLE001 - bez zdroje srdce čte jen snímek
            return None

    def brain(self, project):
        return brain_files.brain_dir(self.service, project)

    def _batch(self, project, workspace, items):
        try:
            claude = self.find()
            if claude is None or not gate_setting.is_on(self.service, project):
                self.errors[project] = "Claude Code nenalezen." if claude is None else "Brána projektu je vypnutá."
                return
            inputs = resolve(self.service, project, items)
            if not inputs:
                return
            if not any(item.get("type") == "message" for item in inputs):
                # do stropu se počítá až dávka, která opravdu běží (prázdná po `resolve` ne; sonda r1: 7. lístek čekal 53 min)
                with self.lock:
                    self.starts.setdefault(project, deque()).append(self.clock())
            spec = batch.BatchSpec(brain=self.brain(project), claude=claude, base_url=self.base_url,
                                   token=self._token(project, workspace), project=project, workspace=workspace,
                                   snapshot=snapshot.snapshot(self.service, project, workspace), inputs=inputs,
                                   source_root=self._source(project, workspace))
            entry = batch.run(spec, self.runner, self.clock)
            self.errors.pop(project, None)
            if entry["status"] == "rate_limited":
                self.sleeping_until = self.clock() + RATE_SLEEP
                for item in items:
                    self._add(project, workspace, item, self.sleeping_until)
        except Exception as error:  # noqa: BLE001 - chyba dávky nesmí shodit supervisor
            LOGGER.exception("Srdce: dávka projektu %s selhala.", project)
            self.errors[project] = f"{type(error).__name__}: {error}"[:500]
        finally:
            with self.lock:
                self.running.discard(project)
            self.wakeup.set()

    def status(self, project, now=None):
        """`GET /api/brain/heart/status`: relace, posledních 5 dávek, spánek a nejbližší povolený čas."""
        now = self.clock() if now is None else now
        brain = self.brain(project)
        with self.lock:
            pending = len(self.pending.get(project, []))
            running, allowed = project in self.running, self.next_allowed(project, now)
        return {"project": project, "enabled": enabled() and self.thread is not None, "running": running,
                "pending": pending, "session": session.load(brain), "batches": batch.read_journal(brain, 5),
                "sleeping": self.sleeping_until > now, "sleepingUntil": _iso(self.sleeping_until),
                "nextAllowedAt": _iso(allowed), "error": self.errors.get(project)}


def _iso(moment):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment)) if moment else None
