"""Co srdce budí (docs/brain-heart.md §1): zpráva člověka a outbox událostí projektů se zapnutou bránou.

Čekající lístek `ask` / `change` a úkol `failed` přidají vstup s oknem `WINDOW` (20 s), zpráva člověka budí hned
(kromě stejné věty, kterou vstupní brána označí `duplicate`, docs/navrhy/2026-10-30-vstupni-brana.md). První čtení
projektu začne na konci outboxu a dožene čekající lístky a zprávy, které žádná dávka `ok` neviděla (`inputs.backlog`).
Spouštěče bez vlastní události (milník, karty, prázdná fronta, výslech) se počítají při čtení outboxu. Vstup, který
přijde během dávky, počká na další. Míchá se do `Heart` (`heart.py`), stav drží `HeartState` (`state.py`).
"""
import logging

from backend.brain_opora.determinism import brain_files, gate_setting, intake
from backend.canvas.process_signal import PROCESS_SIGNAL
from backend.flow.catalogs.heart.inputs import (
    MESSAGE_HOURS,
    backlog,
    brief_wakes,
    card_wakes,
    closed_workspaces,
    human_changes,
    idle_wakes,
    milestone_wakes,
    trigger_workspaces,
    wake_input,
)
from backend.flow.catalogs.heart.state import HOUR, WINDOW, iso
from database.repositories import opora_events

LOGGER = logging.getLogger(__name__)
PAGE = 200
POLL = 10.0  # pojistka: outbox se čte i bez signálu (nově zapnutá brána, události jiného procesu)
GIT_POLL = 300.0  # hlídač gitu: jak často čte HEAD zdrojů (a synchronizuje zdroj `git`)
CARD_GAP = 60.0  # spouštěče karet po událostech nejvýš jednou za minutu na projekt (plný průchod řídí `trigger.schedule`)
IDLE_POLL = 120.0  # spouštěč prázdné fronty (determinism/idle.py) nejvýš jednou za 2 min na projekt


class Wakes:
    def _intake(self, project, workspace, text, now):
        """Vstup vstupní brány ke zprávě (docs/navrhy/2026-10-30-vstupni-brana.md §4); chyba = None, zpráva jde dál."""
        try:
            with self.service.lock_for(project):
                db = self.service.db_for(project)
                with db:
                    return intake.safe_record(db, workspace, "heart_message", None, text, iso(now))
        except Exception:  # vstupní brána nesmí zastavit zprávu člověka
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
            brain_files.append_message(self.brain(project), iso(now), workspace, text, via, duplicate)
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
                self._derived(project, milestone_wakes, None, now, "milníku")  # milník mohl dozrát, když srdce nečetlo
                self._cards(project, set(), now)
                self._idle(project, now)
                self._briefs(project, now)
                continue
            for event in events:
                self.cursors[project] = event["id"]
                item = wake_input(event)
                if item is not None:
                    self._add(project, event["workspaceId"], item, now + WINDOW)
            closed = closed_workspaces(events)
            if closed:
                self._derived(project, milestone_wakes, closed, now, "milníku")
            self._derived(project, human_changes, events, now, "ruční změny plánu")
            self._cards(project, trigger_workspaces(events), now)
            self._idle(project, now)
            self._briefs(project, now)

    def _derived(self, project, wakes, extra, now, what):
        """Spouštěč `milestone.done` (po `card.closed` a při prvním čtení, `extra` None = všechny prostory) nebo
        `graph.human_change` (člověk přijal návrh plánu, `extra` = události): jednou na stav, s oknem `WINDOW`.
        Chyba se jen zaloguje, spouštěč nesmí shodit čtení outboxu."""
        try:
            found = wakes(self.service, project, extra, iso(now))
        except Exception:  # spouštěč nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: spouštěč %s projektu %s selhal.", what, project)
            return
        for workspace, item in found:
            self._add(project, workspace, item, now + WINDOW)

    def _briefs(self, project, now):
        """Spouštěč výslechu požadavku (docs/navrhy/2026-10-30-vyslech-srdce.md §2): požadavek vzniká příkazem srdce
        bez vlastní události, proto se čte při každém průchodu outboxu. Jednou na stav, s oknem `WINDOW`."""
        try:
            found = brief_wakes(self.service, project, iso(now), now)
        except Exception:  # spouštěč nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: spouštěč výslechu projektu %s selhal.", project)
            return
        for workspace, item in found:
            self._add(project, workspace, item, now + WINDOW)

    def _cards(self, project, workspaces, now):
        """Spouštěče karet (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4): prostory s událostí běhu nebo plánu
        nejvýš jednou za `CARD_GAP`, všechny prostory s přijatým plánem při prvním čtení a po `trigger.schedule`
        (ten vymaže `card_at`). Jednou na stav (`heart_triggers`), s oknem `WINDOW`. Chyba se jen zaloguje."""
        dirty = self.card_dirty.setdefault(project, set())
        dirty.update(space for space in workspaces if isinstance(space, str))
        if project not in self.card_at:
            spaces = None
        elif dirty and now - self.card_at[project] >= CARD_GAP:
            spaces = set(dirty)
        else:
            return
        self.card_at[project] = now
        dirty.clear()
        try:
            found = card_wakes(self.service, project, spaces, iso(now), now)
        except Exception:  # spouštěč nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: spouštěče karet projektu %s selhaly.", project)
            return
        for workspace, item in found:
            self._add(project, workspace, item, now + WINDOW)

    def _idle(self, project, now):
        """Spouštěč prázdné fronty (OPORA-002, determinism/idle.py): nejvýš jednou za `IDLE_POLL`, ne během dávky
        projektu (srdce právě může plánovat). Vstup `idle` jednou na stav, s oknem `WINDOW`; stropy a `nextAllowedAt`
        hlídá spouštění dávky jako u ostatních vstupů. Chyba se jen zaloguje."""
        with self.lock:
            busy = project in self.running
        if busy or now - self.idle_at.get(project, float("-inf")) < IDLE_POLL:
            return
        self.idle_at[project] = now
        try:
            found, reasons = idle_wakes(self.service, project, iso(now), now)
        except Exception:  # spouštěč nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: spouštěč prázdné fronty projektu %s selhal.", project)
            return
        values = set(reasons.values())
        self.idle[project] = next((value for value in ("frontier_empty", "waiting_human") if value in values), None)
        for workspace, item in found:
            self._add(project, workspace, item, now + WINDOW)

    def _catch_up(self, project, now):
        """První čtení projektu začíná na konci outboxu: co čeká z doby, kdy srdce nečetlo (restart serveru,
        lístek před prvním průchodem, nově zapnutá brána), dožene `backlog`. Splatné hned; lístek, který dávka
        `ok` už viděla, ani zprávu, která už čeká ve frontě, znovu nezařadí."""
        try:
            found = backlog(self.service, project, self.brain(project), iso(now - MESSAGE_HOURS * HOUR))
        except Exception:  # dohánění nesmí shodit čtení outboxu
            LOGGER.exception("Srdce: dohánění čekajících vstupů projektu %s selhalo.", project)
            return
        with self.lock:
            queued = {(space, item.get("text")) for space, item, _ in self.pending.get(project, [])
                      if item.get("type") == "message"}
        for workspace, item in found:
            if item["type"] != "message" or (workspace, item["text"]) not in queued:
                self._add(project, workspace, item, now)

    def collect(self, now):
        """Vstupy průchodu: outbox událostí (po signálu nebo jednou za `POLL`) a hlídač gitu ve vlastním vlákně."""
        if PROCESS_SIGNAL.generation != self.generation or now - self.polled_at >= POLL:
            self.generation, self.polled_at = PROCESS_SIGNAL.generation, now
            self.poll_events(now)
        if now - self.git_at >= GIT_POLL and not self.git_busy:
            self.git_at, self.git_busy = now, True
            self.git_spawn(self._git_pass)
