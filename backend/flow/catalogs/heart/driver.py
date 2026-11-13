"""Srdce řízené enginem toků: jediná cesta dávek srdce (docs/navrhy/2026-11-03-novy-zaklad.md §5 bod 3).

`Heart` (`heart.py`) je zdroj vstupů a stavu (`collect` čte outbox a git, `message` přijímá zprávy člověka,
`status` je `GET /api/brain/heart/status`). Plánovač enginu volá `tick`, který splatné vstupy (`take_due`, okno 20 s)
pustí jako běh aktivní verze sdíleného workflow srdce. Stropy (`per_hour`, `per_project`) bere z parametrů uzlu
`agent.claude`, plný průchod spouštěčů karet z `trigger.schedule`.
"""

import json
import logging

from backend.brain import seed as brain_seed
from backend.flow import interpreter
from backend.flow.catalogs.heart import seed
from backend.flow.catalogs.heart.nodes import AGENT_DEFAULTS, SCHEDULE_DEFAULT_SECONDS, params
from backend.flow.catalogs.heart.runtime import HEARTBEAT_SECONDS, Runtime, _thread, bind

LOGGER = logging.getLogger(__name__)
OPEN = ("queued", "running", "waiting")


class HeartDriver:
    def __init__(self, service, heart, spawn=_thread, heartbeat_seconds=HEARTBEAT_SECONDS):
        self.service, self.heart = service, heart
        self.runtime = Runtime(service, heart, spawn, heartbeat_seconds)
        self.workflow_id, self.runs, self.fired = None, {}, {}

    def start(self):
        """Vazba uzlů, idempotentní seed Brainu (skilly srdce) a Srdce v1 a převzetí otevřených běhů srdce
        (po restartu je engine naváže)."""
        bind(self.runtime)
        with self.service.registry_lock:
            brain_seed.ensure(self.service.db, self.service.root)
            self.workflow_id, _ = seed.ensure_active(self.service.db)
            rows = self.service.db.execute(
                "SELECT r.id, r.trigger FROM flow_runs r JOIN flow_workflow_versions v ON v.id=r.workflow_version_id "
                f"WHERE v.workflow_id=? AND r.status IN {OPEN}", (self.workflow_id,)).fetchall()
        for row in rows:
            project = (json.loads(row["trigger"]).get("payload") or {}).get("project")
            if project:
                self.runs[row["id"]] = project
                self.heart.running.add(project)

    def _active(self):
        row = self.service.db.execute("SELECT id, graph FROM flow_workflow_versions WHERE workflow_id=? AND "
                                      "status='active'", (self.workflow_id,)).fetchone()
        return (row["id"], json.loads(row["graph"])) if row else (None, None)

    def tick(self):
        """Jeden průchod: rozvrh, vstupy srdce, uvolnění hotových běhů a nové běhy na splatné vstupy."""
        heart, now = self.heart, self.heart.clock()
        with self.service.registry_lock:
            version_id, graph = self._active()
        if version_id is None:
            return []
        nodes = graph["nodes"]
        self._schedule(version_id, [n for n in nodes if n["type"] == "trigger.schedule"], now)
        heart.collect(now)
        self._release()
        agent = next((n for n in nodes if n["type"] == "agent.claude"), {})
        caps = params(agent, AGENT_DEFAULTS)
        per_project = int(caps["per_project"])
        due = heart.take_due(now, int(caps["per_hour"]),
                             busy=lambda project: list(self.runs.values()).count(project) >= per_project)
        started = [self._start(version_id, nodes, project, workspace, items) for project, workspace, items in due]
        return [run_id for run_id in started if run_id]

    def _schedule(self, version_id, schedules, now):
        for node in schedules:
            last = self.fired.setdefault(node["id"], now)  # první průchod outboxu karty projde sám
            if now - last >= float(params(node, {"interval_seconds": SCHEDULE_DEFAULT_SECONDS})["interval_seconds"]):
                self.fired[node["id"]] = now
                with self.service.registry_lock:
                    interpreter.start_run(self.service.db, version_id, {"source": "schedule", "node_id": node["id"]})

    def _start(self, version_id, nodes, project, workspace, items):
        kind = "trigger.human_message" if any(item.get("type") == "message" for item in items) else "trigger.heart_event"
        node_id = next((n["id"] for n in nodes if n["type"] == kind), None)
        try:
            with self.service.registry_lock:
                run = interpreter.start_run(self.service.db, version_id, {
                    "source": "heart", "node_id": node_id,
                    "payload": {"project": project, "workspace": workspace, "items": items}})
        except Exception as error:  # vadná verze nesmí shodit plánovač; vstupy počkají na opravu
            from backend.app import error_log

            self.heart.errors[project] = f"{type(error).__name__}: {error}"[:500]
            error_log.submit("heart", "exception", "Tok srdce: běh projektu nešel založit.", project=project,
                             workspace=workspace, subject="run", cause=self.heart.errors[project],
                             lever="Opravit aktivní verzi toku Srdce v1 (Velín → Toky); vstupy počkají.")
            error._opora_recorded = True  # log zůstává na stderr, deník už má záznam s projektem
            LOGGER.exception("Tok srdce: běh projektu %s nešel založit.", project)
            for item in items:
                self.heart._add(project, workspace, item, self.heart.clock() + 60)
            self._free(project)
            return None
        self.runs[run["id"]] = project
        return run["id"]

    def _free(self, project):
        if project not in self.runs.values():
            with self.heart.lock:
                self.heart.running.discard(project)
                self.heart.current.pop(project, None)
            self.heart.wakeup.set()

    def _release(self):
        """Hotové běhy uvolní projekt (projekt vypadne z `running`); chyba uzlu jde do `errors` projektu."""
        if not self.runs:
            return
        with self.service.registry_lock:
            marks = ",".join("?" * len(self.runs))
            rows = self.service.db.execute(f"SELECT id, status FROM flow_runs WHERE id IN ({marks})",
                                           tuple(self.runs)).fetchall()
            failed = {row["run_id"]: row["error"] for row in self.service.db.execute(
                f"SELECT run_id, error FROM flow_node_runs WHERE status='failed' AND run_id IN ({marks})",
                tuple(self.runs))}
        for row in rows:
            if row["status"] in OPEN:
                continue
            project = self.runs.pop(row["id"])
            if row["status"] == "failed" and failed.get(row["id"]):
                self.heart.errors[project] = failed[row["id"]]
            self._free(project)
