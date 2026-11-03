"""Hlídač gitu srdce (docs/brain-heart-orchestrator.md §4): běží každých `wakes.GIT_POLL` s ve vlastním vlákně, ať
neblokuje čtení outboxu. U zdroje `git` pustí existující synchronizaci aplikace (`service.sync`) a posune čisté
prostory za `main`, u zdroje `local` jen čte HEAD. Pohnutý HEAD přidá vstup `commits` s oknem 20 s; první průchod
jen zapamatuje, selhání srdce nebudí. Před dávkou posune její prostor za lokální `main` (uzel `context.snapshot`).
Míchá se do `Heart` (`heart.py`), stav (`heads`, `git_errors`, `tokens`) drží `HeartState`.
"""
import logging
import time

from backend.brain_opora.determinism import gate_setting, git_log
from backend.flow.catalogs.heart.state import WINDOW
from backend.project.workspace.workspace_sources import WorkspaceSources
from backend.project.worktrees import workspace_fast_forward

LOGGER = logging.getLogger(__name__)
SYNC_WAIT, SYNC_STEP = 180.0, 1.0  # čekání na úlohu synchronizace (fetch má sám strop 120 s)
COMMITS = 20  # nejvýš řádků „sha7 titulek“ ve vstupu `commits`
HOME = {"git": "main", "local": "draft"}  # pracovní prostor, jehož zdroj hlídač čte vždy


class GitWatch:
    def _git_pass(self):
        try:
            self.watch_git()
        except Exception:  # hlídač nesmí shodit plánovač ani srdce budit
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
            if time.monotonic() > deadline:
                raise TimeoutError("Synchronizace nedoběhla včas.")
            time.sleep(SYNC_STEP)

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
