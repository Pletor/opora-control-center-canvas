"""Stav srdce v paměti (docs/brain-heart.md §1, §2): fronta vstupů, stropy dávek, spánek a `GET /api/brain/heart/status`.

Vstupy čekají v `pending` jako `(workspace, item, due)`. `take_due` vybere splatné vstupy jednoho prostoru na projekt,
který nemá otevřený běh, a pustí je, jen když projekt nepřekročil stropy: nejvýš `per_hour` automatických dávek za
hodinu (zpráva člověka strop obchází, prázdná dávka se nepočítá) a žádná dávka během spánku po limitu předplatného.
Dávku samotnou pouští engine toků (`driver.py`, uzly v `nodes.py`). Běží jen na loopbacku a jen bez `OPORA_HEART=off`.
Token srdce je jen v paměti a v prostředí procesu dávky, nikdy na disku.
"""
import os
import threading
import time
from collections import deque

from backend.agi_pletor.llm_settings import cswap
from backend.brain_opora.determinism import brain_files, tokens
from backend.brain_opora.heart import batch, command, session
from backend.project.workspace.workspace_sources import WorkspaceSources

PER_HOUR, HOUR, WINDOW = 6, 3600.0, 20.0  # WINDOW: okno vstupu z události (s), zpráva člověka budí hned
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def enabled(environ=None):
    """Zapnuté, když `OPORA_HEART` není `off` a server poslouchá jen na loopbacku (`OPORA_CANVAS_HOST`)."""
    env = os.environ if environ is None else environ
    return env.get("OPORA_HEART", "on").strip().lower() != "off" and env.get("OPORA_CANVAS_HOST", "127.0.0.1") in LOOPBACK


def _git_thread(target):
    threading.Thread(target=target, name="opora-heart-git", daemon=True).start()


class HeartState:
    def __init__(self, service, *, base_url, runner=None, clock=time.time, find=None, git_spawn=_git_thread, jev=None,
                 switch_account=None):
        self.service, self.base_url, self.clock = service, base_url, clock
        self.jev = jev or (lambda: None)  # `evaluate(state, questions)` s klíčem aplikace, nebo None (bez Jevu)
        self.git_spawn, self.heads, self.git_errors = git_spawn, {}, {}
        self.git_at, self.git_busy = float("-inf"), False
        self.runner = runner or batch.run_process
        self.find = find or command.find_claude
        self.switch_account = switch_account or (lambda: cswap.switch())  # po limitu: další účet claude-swap; pozdní vazba kvůli testům
        self.lock, self.wakeup = threading.Lock(), threading.Event()
        self.pending, self.running, self.starts, self.cursors, self.tokens, self.errors = {}, set(), {}, {}, {}, {}
        self.sleeping_until, self.generation, self.polled_at = 0.0, None, float("-inf")
        self.card_at, self.card_dirty = {}, {}  # spouštěče karet: poslední vyhodnocení a prostory k vyhodnocení
        self.idle_at, self.idle = {}, {}  # prázdná fronta: poslední vyhodnocení a `idleReason` projektu
        self.current = {}  # běžící dávka projektu: {startedAt, inputs}, jen v paměti (kanál srdce „právě teď“)

    def _add(self, project, workspace, item, due):
        with self.lock:
            items = self.pending.setdefault(project, [])
            if item.get("type") == "researchPlanning" and any(
                    entry[1].get("continuationId") == item["continuationId"] for entry in items):
                return
            if item.get("type") == "ticket" and any(entry[1].get("ticketId") == item["ticketId"] for entry in items):
                return  # jeden lístek = jeden vstup (dohánění po startu a outbox se mohou potkat)
            items.append((workspace, item, due))

    def next_allowed(self, project, now, per_hour=PER_HOUR):
        """Nejbližší čas, kdy smí projekt začít dávku (spánek po limitu a strop dávek za hodinu)."""
        starts = self.starts.setdefault(project, deque())
        while starts and starts[0] <= now - HOUR:
            starts.popleft()
        capped = starts[0] + HOUR if len(starts) >= per_hour else now
        return max(now, self.sleeping_until, capped)

    def take_due(self, now, per_hour=PER_HOUR, busy=None):
        """Splatné vstupy jednoho prostoru na projekt, který nemá běžící dávku (`busy`) a nepřekročil stropy;
        vybrané projekty jdou do `running`. Vrací `[(project, workspace, items)]`."""
        busy = busy or (lambda project: project in self.running)
        started = []
        with self.lock:
            for project, items in list(self.pending.items()):
                if not items or busy(project) or min(due for _, _, due in items) > now:
                    continue
                # zpráva člověka strop za hodinu obchází (eval m2: strop zablokoval zadání), limit předplatného ne
                human = any(item.get("type") == "message" for _, item, _ in items)
                if (max(now, self.sleeping_until) if human else self.next_allowed(project, now, per_hour)) > now:
                    continue
                workspace = items[0][0]
                taken = [item for space, item, _ in items if space == workspace]
                self.pending[project] = [entry for entry in items if entry[0] != workspace]
                self.running.add(project)
                started.append((project, workspace, taken))
        return started

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

    def status(self, project, now=None):
        """`GET /api/brain/heart/status`: relace, posledních 5 dávek, spánek, nejbližší povolený čas, `activeWorkspace`
        (prostor posledního plánu, který srdce přijalo; docs/brain-heart-orchestrator.md §9), `current` (běžící dávka
        `{startedAt, inputs, steps}`, jinak None; `typicalMs` = medián trvání posledních 10 úspěšných dávek se zprávou; docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md §A) a `idleReason`
        (prázdná fronta z posledního vyhodnocení `_idle`: `frontier_empty` / `waiting_human` / None)."""
        now = self.clock() if now is None else now
        brain = self.brain(project)
        with self.lock:
            pending = len(self.pending.get(project, []))
            running, allowed = project in self.running, self.next_allowed(project, now)
            current = self.current.get(project) if running else None
        return {"project": project, "enabled": enabled(), "running": running,
                "pending": pending, "session": session.load(brain), "batches": batch.read_journal(brain, 5),
                "sleeping": self.sleeping_until > now, "sleepingUntil": iso(self.sleeping_until),
                "nextAllowedAt": iso(allowed), "error": self.errors.get(project),
                "gitError": self.git_errors.get(project), "activeWorkspace": brain_files.active_workspace(brain),
                "current": current, "idleReason": self.idle.get(project),
                "typicalMs": batch.typical_ms(brain),
                # Průhled: proč srdce čeká, kde se může zastavit a kam šel čas dávek (docs/navrhy/2026-11-13-pruhled-srdce.md)
                "explain": f"/api/pletor/heart/explain?project={project}&format=text"}


def iso(moment):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment)) if moment else None


def iso_utc(moment):
    """Začátek dávky ve stejném tvaru jako `at` v deníku dávek (i pro čas 0 ve zkouškách)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment))
