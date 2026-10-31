"""Supervisor srdce (docs/brain-heart.md §1, §2): spí, budí se na vstupy a pouští jednu dávku na projekt.

Vlákno (démon) sleduje outbox událostí projektů se zapnutou bránou: čekající lístek `ask` / `change`
a úkol `failed` přidají vstup s oknem 20 s, zpráva člověka budí hned (kromě stejné věty, kterou vstupní brána
označí `duplicate`, docs/navrhy/2026-10-30-vstupni-brana.md). První čtení projektu začne na konci outboxu
a dožene čekající lístky a zprávy, které žádná dávka `ok` neviděla (`inputs.backlog`). Dávka běží ve vlastním vlákně, nejvýš
jedna na projekt a nejvýš 6 automatických za hodinu (zpráva člověka strop obchází, prázdná dávka se nepočítá); vstup, který přijde během
dávky, počká na další. Vyčerpaný limit
předplatného uspí srdce na 15 min a vstupy zůstanou. Běží jen na loopbacku a jen bez `OPORA_HEART=off`.
Před složením dávky zařadí vstupy brány `pending` přes Jev (`decision/intake.py`, jen s povolením projektu a klíčem
aplikace z `jev`); chyba Jevu dávku nezastaví.

Hlídač gitu (docs/brain-heart-orchestrator.md §4) běží každých `GIT_POLL` s ve vlastním vlákně, ať neblokuje
čtení outboxu: u zdroje `git` pustí existující synchronizaci aplikace (`service.sync`), u zdroje `local` jen čte
HEAD. Pohnutý HEAD přidá vstup `commits` s oknem 20 s; první průchod jen zapamatuje, selhání srdce nebudí.
"""
import logging
import os
import threading
import time
from collections import deque

from backend.brain_opora.decision import intake as intake_decision
from backend.brain_opora.determinism import (
    brain_files,
    gate_setting,
    git_log,
    intake,
    snapshot,
    tokens,
)
from backend.brain_opora.heart import batch, command, session
from backend.brain_opora.heart.inputs import (
    MESSAGE_HOURS,
    backlog,
    brief_wakes,
    card_wakes,
    closed_workspaces,
    human_changes,
    milestone_wakes,
    resolve,
    trigger_workspaces,
    wake_input,
)
from backend.canvas.process_signal import PROCESS_SIGNAL
from backend.project.workspace.workspace_sources import WorkspaceSources
from backend.project.worktrees import workspace_fast_forward
from database.repositories import opora_events

LOGGER = logging.getLogger(__name__)
WINDOW, RATE_SLEEP, PER_HOUR, HOUR, TICK = 20.0, 15 * 60.0, 6, 3600.0, 2.0
LOOPBACK = ("127.0.0.1", "localhost", "::1")
PAGE = 200
POLL = 10.0  # pojistka: outbox se čte i bez signálu (nově zapnutá brána, události jiného procesu)
GIT_POLL = 300.0  # hlídač gitu: jak často čte HEAD zdrojů (a synchronizuje zdroj `git`)
SYNC_WAIT, SYNC_STEP = 180.0, 1.0  # čekání na úlohu synchronizace (fetch má sám strop 120 s)
COMMITS = 20  # nejvýš řádků „sha7 titulek“ ve vstupu `commits`
HOME = {"git": "main", "local": "draft"}  # pracovní prostor, jehož zdroj hlídač čte vždy
CARD_GAP = 60.0  # spouštěče karet po událostech nejvýš jednou za minutu na projekt
CARD_POLL = 600.0  # a bez událostí jednou za 10 min (zaseknutý běh žádnou událost nepošle)


def enabled(environ=None):
    """Zapnuté, když `OPORA_HEART` není `off` a server poslouchá jen na loopbacku (`OPORA_CANVAS_HOST`)."""
    env = os.environ if environ is None else environ
    return env.get("OPORA_HEART", "on").strip().lower() != "off" and env.get("OPORA_CANVAS_HOST", "127.0.0.1") in LOOPBACK


def _thread(target):
    threading.Thread(target=target, name="opora-heart-batch", daemon=True).start()


def _git_thread(target):
    threading.Thread(target=target, name="opora-heart-git", daemon=True).start()


class HeartSupervisor:
    def __init__(self, service, *, base_url, runner=None, clock=time.time, tick=TICK, spawn=_thread, find=None,
                 git_spawn=_git_thread, jev=None):
        self.service, self.base_url, self.clock, self.tick, self.spawn = service, base_url, clock, tick, spawn
        self.jev = jev or (lambda: None)  # `evaluate(state, questions)` s klíčem aplikace, nebo None (bez Jevu)
        self.git_spawn, self.heads, self.git_errors = git_spawn, {}, {}
        self.git_at, self.git_busy = float("-inf"), False
        self.runner = runner or batch.run_process
        self.find = find or command.find_claude
        self.lock, self.stop, self.wakeup, self.thread = threading.Lock(), threading.Event(), threading.Event(), None
        self.pending, self.running, self.starts, self.cursors, self.tokens, self.errors = {}, set(), {}, {}, {}, {}
        self.sleeping_until, self.generation, self.polled_at = 0.0, None, float("-inf")
        self.card_at, self.card_dirty = {}, {}  # spouštěče karet: poslední vyhodnocení a prostory k vyhodnocení
        self.current = {}  # běžící dávka projektu: {startedAt, inputs}, jen v paměti (kanál srdce „právě teď“)

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
            items = self.pending.setdefault(project, [])
            if item.get("type") == "ticket" and any(entry[1].get("ticketId") == item["ticketId"] for entry in items):
                return  # jeden lístek = jeden vstup (dohánění po startu a outbox se mohou potkat)
            items.append((workspace, item, due))

    def _intake(self, project, workspace, text, now):
        """Vstup vstupní brány ke zprávě (docs/navrhy/2026-10-30-vstupni-brana.md §4); chyba = None, zpráva jde dál."""
        try:
            with self.service.lock_for(project):
                db = self.service.db_for(project)
                with db:
                    return intake.safe_record(db, workspace, "heart_message", None, text, _iso(now))
        except Exception:  # noqa: BLE001 - vstupní brána nesmí zastavit zprávu člověka
            LOGGER.exception("Srdce: vstup brány ke zprávě projektu %s nešel zapsat.", project)
            return None

    def message(self, project, workspace, text, now=None, via=None, *, record_intake=True):
        """Zpráva člověka: nejdřív vstup brány a řádek do `brain/messages.jsonl` (přežije dávku i rotaci relace, §3a),
        pak vstup splatný hned; vrací počet čekajících vstupů projektu. Selhaný zápis se jen zaloguje, zpráva srdce
        budí dál. Stejná věta jako dřívější (`duplicate`) se uloží se značkou a srdce nebudí.
        `via` = jméno relace pracovníka, který zprávu předal (relé záměru, docs/brain-heart-orchestrator.md §8).
        `record_intake=False` (odpověď člověka na eskalaci srdce) vstup brány nezapisuje."""
        now = self.clock() if now is None else now
        entry = self._intake(project, workspace, text, now) if record_intake else None
        duplicate = entry["id"] if entry and entry["verdict"] == "duplicate" else None
        try:
            brain_files.append_message(self.brain(project), _iso(now), workspace, text, via, duplicate)
        except OSError:
            LOGGER.exception("Srdce: zprávu člověka projektu %s nešlo uložit.", project)
        if duplicate is None:
            item = {"type": "message", "text": text} | ({"intake": intake.line_info(entry)} if entry else {})
            self._add(project, workspace, item, now)
            self.wakeup.set()
        with self.lock:
            return len(self.pending.get(project, []))

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
                    self._catch_up(project, now)
                events = []
                while cursor is not None:
                    chunk, _, _ = opora_events.page(db, project, None, cursor, PAGE)
                    events += chunk
                    if len(chunk) < PAGE:
                        break
                    cursor = chunk[-1]["id"]
            if cursor is None:
                self._milestones(project, None, now)  # první čtení: milník mohl dozrát, když supervisor nečetl
                self._cards(project, set(), now)
                self._briefs(project, now)
                continue
            for event in events:
                self.cursors[project] = event["id"]
                item = wake_input(event)
                if item is not None:
                    self._add(project, event["workspaceId"], item, now + WINDOW)
            closed = closed_workspaces(events)
            if closed:
                self._milestones(project, closed, now)
            self._human_changes(project, events, now)
            self._cards(project, trigger_workspaces(events), now)
            self._briefs(project, now)

    def _briefs(self, project, now):
        """Spouštěč výslechu požadavku (docs/navrhy/2026-10-30-vyslech-srdce.md §2): požadavek vzniká příkazem srdce
        bez vlastní události, proto se čte při každém průchodu outboxu. Jednou na stav, s oknem `WINDOW`."""
        try:
            found = brief_wakes(self.service, project, _iso(now), now)
        except Exception:  # noqa: BLE001 - spouštěč nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: spouštěč výslechu projektu %s selhal.", project)
            return
        for workspace, item in found:
            self._add(project, workspace, item, now + WINDOW)

    def _human_changes(self, project, events, now):
        """Spouštěč `graph.human_change`: člověk přijal návrh plánu → srdce jednou na revizi, s oknem `WINDOW`."""
        try:
            found = human_changes(self.service, project, events, _iso(now))
        except Exception:  # noqa: BLE001 - spouštěč nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: spouštěč ruční změny plánu projektu %s selhal.", project)
            return
        for workspace, item in found:
            self._add(project, workspace, item, now + WINDOW)

    def _cards(self, project, workspaces, now):
        """Spouštěče karet (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4): prostory s událostí běhu nebo plánu
        nejvýš jednou za `CARD_GAP`, všechny prostory s přijatým plánem při prvním čtení a jednou za `CARD_POLL`.
        Jednou na stav (`heart_triggers`), s oknem `WINDOW`. Chyba se jen zaloguje."""
        dirty = self.card_dirty.setdefault(project, set())
        dirty.update(space for space in workspaces if isinstance(space, str))
        last = self.card_at.get(project, float("-inf"))
        if now - last >= CARD_POLL:
            spaces = None
        elif dirty and now - last >= CARD_GAP:
            spaces = set(dirty)
        else:
            return
        self.card_at[project] = now
        dirty.clear()
        try:
            found = card_wakes(self.service, project, spaces, _iso(now), now)
        except Exception:  # noqa: BLE001 - spouštěč nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: spouštěče karet projektu %s selhaly.", project)
            return
        for workspace, item in found:
            self._add(project, workspace, item, now + WINDOW)

    def _milestones(self, project, workspaces, now):
        """Spouštěč `milestone.done` (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4): splněný aktivní milník budí
        srdce jednou, s oknem `WINDOW`. Bez vlastní události outboxu: počítá se po `card.closed` a při prvním čtení
        projektu (`workspaces` None = všechny prostory). Chyba se jen zaloguje."""
        try:
            found = milestone_wakes(self.service, project, workspaces, _iso(now))
        except Exception:  # noqa: BLE001 - spouštěč nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: spouštěč milníku projektu %s selhal.", project)
            return
        for workspace, item in found:
            self._add(project, workspace, item, now + WINDOW)

    def _catch_up(self, project, now):
        """První čtení projektu začíná na konci outboxu: co čeká z doby, kdy supervisor nečetl (restart serveru,
        lístek před prvním průchodem, nově zapnutá brána), dožene `backlog`. Splatné hned; lístek, který dávka
        `ok` už viděla, ani zprávu, která už čeká ve frontě, znovu nezařadí."""
        try:
            found = backlog(self.service, project, self.brain(project), _iso(now - MESSAGE_HOURS * HOUR))
        except Exception:  # noqa: BLE001 - dohánění nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: dohánění čekajících vstupů projektu %s selhalo.", project)
            return
        with self.lock:
            queued = {(space, item.get("text")) for space, item, _ in self.pending.get(project, [])
                      if item.get("type") == "message"}
        for workspace, item in found:
            if item["type"] != "message" or (workspace, item["text"]) not in queued:
                self._add(project, workspace, item, now)

    def _git_pass(self):
        try:
            self.watch_git()
        except Exception:  # hlídač nesmí shodit supervisor ani srdce budit
            LOGGER.exception("Srdce: průchod hlídače gitu selhal.")
        finally:
            self.git_busy = False

    def _kind(self, project):
        return self.service.project_hub.settings(project)["project"]["sourceKind"]

    def _job_status(self, job):
        with self.service.registry_lock:
            row = self.service.db.execute("SELECT status, message FROM jobs WHERE id=?", (job,)).fetchone()
        return (row[0], row[1]) if row else ("missing", "Úloha synchronizace zmizela.")

    def _sync(self, project):
        """Existující synchronizace aplikace (fetch + `merge --ff-only`) a čekání na její úlohu; selhání = výjimka."""
        job = self.service.sync(project)["jobId"]
        deadline = time.monotonic() + SYNC_WAIT
        while True:
            status, message = self._job_status(job)
            if status == "complete":
                return
            if status in ("failed", "missing"):
                raise ValueError(f"Synchronizace selhala: {message}")
            if time.monotonic() > deadline or self.stop.wait(SYNC_STEP):
                raise TimeoutError("Synchronizace nedoběhla včas.")

    def _watched(self, project, kind):
        """Domovský prostor zdroje a prostory, ve kterých srdce už pracovalo (má token)."""
        with self.lock:
            known = {space for owner, space in self.tokens if owner == project}
        return sorted({HOME[kind], *known})

    def watch_git(self):
        """Jeden průchod hlídače: projekty se zapnutou bránou a zdrojem `git` / `local`; změna HEAD = vstup `commits`.
        Selhání projektu se jen zapíše (log a `git_errors`) a srdce nebudí."""
        for project in self.service.project_ids():
            try:
                if not gate_setting.is_on(self.service, project):
                    continue
                kind = self._kind(project)
                if kind not in HOME:
                    continue
                if kind == "git":
                    self._sync(project)
                    self._advance_workspaces(project, kind)
                for workspace in self._watched(project, kind):
                    self._watch_head(project, workspace, kind)
                self.git_errors.pop(project, None)
            except Exception as error:  # noqa: BLE001 - selhaný zdroj jen zapsat, ostatní projekty běží dál
                LOGGER.warning("Srdce: hlídač gitu projektu %s: %s", project, error)
                self.git_errors[project] = f"{type(error).__name__}: {error}"[:500]

    def _advance_one(self, project, workspace, main_sha):
        """Posune jeden prostor za `main_sha`; nový HEAD zapíše do `heads`. Selhání jen do logu."""
        try:
            root = WorkspaceSources(self.service).root(project, workspace)
            moved = workspace_fast_forward.fast_forward(root, main_sha) if root is not None else None
            if moved:
                self.heads[(project, workspace)] = moved
        except Exception as error:  # noqa: BLE001 - jeden prostor nerozbije průchod ani dávku
            LOGGER.warning("Srdce: posun prostoru %s/%s: %s", project, workspace, error)

    def _advance_workspaces(self, project, kind):
        """Po synchronizaci posune čisté prostory za `main` (docs/domeny-a-worktree.md, „Posun worktree za main“)."""
        try:
            main_sha = git_log.head(WorkspaceSources(self.service).root(project, HOME[kind]))
        except Exception as error:  # noqa: BLE001 - bez HEAD mainu není kam posouvat
            LOGGER.warning("Srdce: HEAD mainu projektu %s: %s", project, error)
            return
        for workspace in self._watched(project, kind):
            if workspace != HOME[kind]:
                self._advance_one(project, workspace, main_sha)

    def _advance_before_batch(self, project, workspace):
        """Před dávkou posune její prostor za lokální `main` (bez fetch), aby srdce nečetlo zastaralý worktree."""
        try:
            if workspace == HOME["git"] or self._kind(project) != "git":
                return
            main_sha = git_log.head(WorkspaceSources(self.service).root(project, HOME["git"]))
        except Exception as error:  # noqa: BLE001 - dávka musí běžet i bez posunu
            LOGGER.warning("Srdce: posun před dávkou %s/%s: %s", project, workspace, error)
            return
        self._advance_one(project, workspace, main_sha)

    def _targets(self, project, workspace, kind):
        """Kam vstup `commits` patří. `main` git projektu je jen ke čtení (karty tam nevzniknou): jeho posun dostanou
        prostory, ve kterých srdce pracovalo; bez nich `main` (srdce aspoň odpoví nebo eskaluje)."""
        if kind != "git" or workspace != HOME["git"]:
            return [workspace]
        return [space for space in self._watched(project, kind) if space != workspace] or [workspace]

    def _watch_head(self, project, workspace, kind="local"):
        root = WorkspaceSources(self.service).root(project, workspace)
        if root is None:
            return
        new, key = git_log.head(root), (project, workspace)
        old = self.heads.get(key)
        self.heads[key] = new  # nejdřív zapamatovat: nečitelný rozsah (přepsaná historie) nebudí znovu
        if old is None or old == new:
            return
        log = git_log.between(root, old, new, COMMITS)
        for target in self._targets(project, workspace, kind):
            self._add(project, target, {"type": "commits", "from": old, "to": new, "log": log}, self.clock() + WINDOW)
        self.wakeup.set()

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
        if now - self.git_at >= GIT_POLL and not self.git_busy:
            self.git_at, self.git_busy = now, True
            self.git_spawn(self._git_pass)
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
            inputs = intake_decision.classify_pending(self.service, project, workspace, inputs, jev=self.jev,
                                                      now=self.clock())
            if not any(item.get("type") == "message" for item in inputs):
                # do stropu se počítá až dávka, která opravdu běží (prázdná po `resolve` ne; sonda r1: 7. lístek čekal 53 min)
                with self.lock:
                    self.starts.setdefault(project, deque()).append(self.clock())
            with self.lock:
                self.current[project] = {"startedAt": _iso_utc(self.clock()), "inputs": inputs}
            self._advance_before_batch(project, workspace)
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
                self.current.pop(project, None)
            self.wakeup.set()

    def status(self, project, now=None):
        """`GET /api/brain/heart/status`: relace, posledních 5 dávek, spánek, nejbližší povolený čas, `activeWorkspace`
        (prostor posledního plánu, který srdce přijalo; docs/brain-heart-orchestrator.md §9) a `current` (běžící dávka
        `{startedAt, inputs}`, jinak None; docs/navrhy/2026-10-31-viditelnost-srdce-a-karet.md §A)."""
        now = self.clock() if now is None else now
        brain = self.brain(project)
        with self.lock:
            pending = len(self.pending.get(project, []))
            running, allowed = project in self.running, self.next_allowed(project, now)
            current = self.current.get(project) if running else None
        return {"project": project, "enabled": enabled() and self.thread is not None, "running": running,
                "pending": pending, "session": session.load(brain), "batches": batch.read_journal(brain, 5),
                "sleeping": self.sleeping_until > now, "sleepingUntil": _iso(self.sleeping_until),
                "nextAllowedAt": _iso(allowed), "error": self.errors.get(project),
                "gitError": self.git_errors.get(project), "activeWorkspace": brain_files.active_workspace(brain),
                "current": current}


def _iso(moment):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment)) if moment else None


def _iso_utc(moment):
    """Začátek dávky ve stejném tvaru jako `at` v deníku dávek (i pro čas 0 ve zkouškách)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment))
