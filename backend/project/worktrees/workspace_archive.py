"""Skladiště uzavřených worktree (docs/domeny-a-worktree.md §6, §13.3).

Přesun do skladiště je postup o čtyřech krocích, seřazených tak, aby selhání kterékoli části
nechalo konzistentní a opakovatelný stav:

1. záznam `archived_workspaces` (od té chvíle worktree mizí ze seznamů, pohledu i stavu práce),
2. `git worktree remove` bez `--force` (větev `work/<id>` zůstává); při selhání se záznam z kroku 1
   vrátí a nic se nezměnilo,
3. data prostoru `canvas/workspaces/<id>` → `canvas/workspaces/_archive/<id>`,
4. smazání řádku `workspaces`.

Selže-li krok 3 nebo 4, chyba řekne, co už se stalo; nové zavolání postup dokončí (hotové kroky přeskočí).
Odmítne se worktree se změnami (`git status --porcelain`) i worktree s živou relací (stav běží/čeká, §7).
Ze skladiště jde jen číst; obnova je pozdější kus.
"""

import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from backend.canvas.graph import payload_project, valid_id
from backend.integrations.gitio import git
from backend.project.architecture.work_status import (
    RUNNING,
    WAITING,
    collect_sources,
    worktree_state,
)

ARCHIVE_KEYS = {"project", "reason", "confirmed"}
ARCHIVE_FOLDER = "_archive"
REASON_LIMIT = 500
LIVE_STATES = {RUNNING: "běží", WAITING: "čeká"}


def archived_workspaces(service, pid):
    """Položky skladiště projektu, nejnovější první."""
    with service.registry_lock:
        rows = service.db.execute(
            "SELECT * FROM archived_workspaces WHERE project_id=? ORDER BY archived_at DESC, id", (pid,)
        ).fetchall()
    return [{"id": r["id"], "nodeId": r["node_id"], "branch": r["branch"], "actor": r["actor"],
             "reason": r["reason"], "archivedAt": r["archived_at"]} for r in rows]


def live_state(service, registry, hook_store, pid, wid, now=None):
    """(stav, důvody) jednoho worktree podle zdrojů stavu práce (§7)."""
    now = now or datetime.fromtimestamp(time.time(), UTC)
    sources = collect_sources(service, registry, hook_store, pid)
    return worktree_state(
        [s for s in sources["sessions"] if s.get("workspace") == wid],
        [b for b in sources["bindings"] if b.get("workspace") == wid],
        [lease for lease in sources["leases"] if lease["workspace_id"] == wid],
        {a["node_id"]: a for a in sources["activity"] if a["workspace_id"] == wid},
        now,
    )


class WorkspaceArchive:
    def __init__(self, service, registry, hook_store):
        """`hook_store` = úložiště hook bindingů, nebo funkce, která ho vrátí (vzniká až s routerem hooků)."""
        self.service = service
        self.registry = registry
        self._hook_store = hook_store

    @property
    def hook_store(self):
        return self._hook_store() if callable(self._hook_store) else self._hook_store

    def items(self, pid):
        if pid != "draft" and not valid_id(pid):
            raise ValueError("Neplatné ID projektu.")
        return {"items": archived_workspaces(self.service, pid)}

    def archive(self, wid, payload):
        pid, reason = self._validate(wid, payload)
        service = self.service
        with service.git_lock:
            row = service.row("workspaces", wid)
            if row["project_id"] != pid:
                raise ValueError("Pracovní prostor patří jinému projektu.")
            project = service.row("projects", pid)
            directory = Path(row["directory"])
            present = directory.exists()
            self._refuse_live(pid, wid, directory if present else None)
            fresh = self._record(row, reason)
            done = ["záznam ve skladišti"]
            if present:
                try:
                    git(project["repo"], "worktree", "remove", str(directory), timeout=60)
                except ValueError:
                    if fresh:
                        self._forget(wid)
                        raise ValueError("Git worktree nejde odebrat (soubory mimo Git nebo zámek). Nic se nezměnilo.")
                    raise ValueError(self._partial(done, "Git worktree nejde odebrat"))
            else:
                git(project["repo"], "worktree", "prune", optional=True)
            done.append("worktree odebrán, větev " + row["branch"] + " zůstala")
            try:
                self._move_data(pid, wid)
            except OSError:
                raise ValueError(self._partial(done, "data prostoru nejde přesunout do skladiště"))
            done.append("data ve skladišti")
            with service.registry_lock:
                service.db.execute("DELETE FROM workspaces WHERE id=?", (wid,))
                service.db.commit()
        return {"archived": wid, "branch": row["branch"]}

    def _validate(self, wid, payload):
        if not isinstance(payload, dict) or set(payload) != ARCHIVE_KEYS:
            raise ValueError("Neplatný formát přesunu do skladiště (project, reason, confirmed).")
        pid = payload_project(payload)
        if payload["confirmed"] is not True:
            raise ValueError("Přesun worktree do skladiště vyžaduje výslovné potvrzení.")
        reason = payload["reason"]
        if not isinstance(reason, str) or not reason.strip() or len(reason) > REASON_LIMIT:
            raise ValueError(f"Napište důvod uzavření worktree (nejvýš {REASON_LIMIT} znaků).")
        if not valid_id(wid) or wid == ARCHIVE_FOLDER:
            raise ValueError("Neplatný identifikátor.")
        return pid, reason.strip()

    def _refuse_live(self, pid, wid, directory):
        reasons = []
        if directory is not None and git(directory, "status", "--porcelain"):
            reasons.append("worktree má neuložené změny")
        state, signals = live_state(self.service, self.registry, self.hook_store, pid, wid)
        if state in LIVE_STATES:
            reasons.append(f"na worktree se pracuje ({LIVE_STATES[state]}: " + ", ".join(signals) + ")")
        if reasons:
            raise ValueError("Worktree nejde přesunout do skladiště: " + "; ".join(reasons) + ".")

    def _record(self, row, reason):
        """Krok 1. True = záznam vznikl teď (při selhání gitu ho lze vrátit)."""
        service = self.service
        with service.registry_lock:
            if service.db.execute("SELECT 1 FROM archived_workspaces WHERE id=?", (row["id"],)).fetchone():
                return False
            service.db.execute(
                "INSERT INTO archived_workspaces VALUES(?,?,?,?,?,?,?,?,?)",
                (row["id"], row["project_id"], row["node_id"], row["branch"], row["actor"], row["base_sha"],
                 row["directory"], reason, datetime.now(UTC).isoformat()),
            )
            service.db.commit()
        return True

    def _forget(self, wid):
        with self.service.registry_lock:
            self.service.db.execute("DELETE FROM archived_workspaces WHERE id=?", (wid,))
            self.service.db.commit()

    def _move_data(self, pid, wid):
        source = self.service.graph_file(pid, wid).parent
        target = source.parent / ARCHIVE_FOLDER / wid
        if not source.exists():
            return
        if target.exists():
            raise OSError("Cíl ve skladišti už existuje.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))

    @staticmethod
    def _partial(done, failure):
        return ("Přesun do skladiště se nedokončil: " + failure + ". Hotovo: " + ", ".join(done)
                + ". Zopakujte přesun; hotové kroky se přeskočí.")
