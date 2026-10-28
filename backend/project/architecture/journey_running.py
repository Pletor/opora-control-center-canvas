"""Stav „cesta právě běží“ (`docs/brana-cesty.md` §3a): krátkodobý, jen v paměti procesu.

Runner (`tools/journey_run.py`) před přehráním ohlásí start (`start` → `{runId, startedAt}`) a během běhu posílá
heartbeat s právě přehrávaným nebo dokončeným přechodem (`progress`). Záznam žije 120 s od posledního heartbeatu
(`TTL_SECONDS`); restart serveru ho smaže. Nic se nezapisuje do SQLite a schéma se nemění: neměnný doklad běhu
(`journey_runs.py`) se odevzdává jako dosud a po jeho zapsání se `running` té cesty smaže (`finish`).

- Klíč běhu je `(project, applicationId, journeyId)`; nový start téže cesty předchozí běh nahradí.
- `running(project)` vrací `{(applicationId, journeyId): {runId, at, segment}}`; `at` = čas posledního heartbeatu
  (ISO 8601 UTC), `segment` = `{from, to, ok?}` posledního `progress` (bez `ok` = přechod se právě přehrává), před
  prvním `progress` `None`.
- Neznámý nebo prošlý `runId` je `JourneyRunUnknown` (HTTP 404). Chyba tvaru těla je `JourneyRunInvalid` (422).
- Nejvýš `MAX_RUNS` současných běhů; nad stropem se zahodí ten s nejstarším heartbeatem.
- Hodiny jsou vstříknuté (`monotonic` pro TTL, `wall` pro `at`) kvůli testům; přístup hlídá zámek (thread-safe).
"""

import threading
import time
import uuid
from datetime import UTC, datetime

from backend.project.architecture.journey_plan import journey_plan
from backend.project.architecture.journey_runs import JourneyRunInvalid
from backend.project.architecture.work_status import architecture_graph

TTL_SECONDS = 120
MAX_RUNS = 256
START_KEYS = {"project", "journeyId", "applicationId"}
PROGRESS_KEYS = {"segment", "ok"}


class JourneyRunUnknown(LookupError):
    """Běh s tímto `runId` neexistuje nebo už vypršel (HTTP 404)."""


def _text(value, name, limit=64):
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise JourneyRunInvalid(f"{name} musí být text o 1–{limit} znacích.")
    return value


def _object(body, keys, required, what):
    if not isinstance(body, dict):
        raise JourneyRunInvalid(f"{what} musí být objekt JSON.")
    unknown = sorted(set(body) - keys)
    if unknown:
        raise JourneyRunInvalid(f"Neznámé klíče {what}: {', '.join(unknown)}.")
    missing = sorted(required - set(body))
    if missing:
        raise JourneyRunInvalid(f"Chybí klíče {what}: {', '.join(missing)}.")
    return body


def validate_start(body):
    """Tělo startu `{project, journeyId, applicationId?}` → (project, journeyId, applicationId | None)."""
    _object(body, START_KEYS, {"project", "journeyId"}, "startu")
    application = _text(body["applicationId"], "applicationId") if "applicationId" in body else None
    return _text(body["project"], "project"), _text(body["journeyId"], "journeyId"), application


def validate_progress(body):
    """Tělo heartbeatu `{segment: {from, to}, ok?}` → segment `{from, to, ok?}`."""
    _object(body, PROGRESS_KEYS, {"segment"}, "průběhu")
    segment = _object(body["segment"], {"from", "to"}, {"from", "to"}, "segmentu")
    if "ok" in body and not isinstance(body["ok"], bool):
        raise JourneyRunInvalid("ok musí být true nebo false.")
    return {"from": _text(segment["from"], "from"), "to": _text(segment["to"], "to"),
            **({"ok": body["ok"]} if "ok" in body else {})}


def _iso(moment):
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class JourneyRunning:
    """Běžící přehrání cest v paměti procesu s TTL od posledního heartbeatu."""

    def __init__(self, monotonic=time.monotonic, wall=lambda: datetime.now(UTC), ttl=TTL_SECONDS, limit=MAX_RUNS):
        self._monotonic, self._wall, self._ttl, self._limit = monotonic, wall, ttl, limit
        self._lock = threading.Lock()
        self._runs = {}  # (project, applicationId, journeyId) -> {runId, at, segment, seen}
        self._keys = {}  # runId -> klíč

    def _purge(self):
        now = self._monotonic()
        for key in [key for key, run in self._runs.items() if now - run["seen"] > self._ttl]:
            self._drop(key)

    def _drop(self, key):
        run = self._runs.pop(key, None)
        if run:
            self._keys.pop(run["runId"], None)

    def start(self, project, application_id, journey_id):
        """Nový běh cesty (předchozí běh téže cesty nahradí): `{runId, startedAt}`."""
        key = (project, application_id, journey_id)
        run_id = uuid.uuid4().hex
        at = _iso(self._wall())
        with self._lock:
            self._purge()
            self._drop(key)
            while len(self._runs) >= self._limit:
                self._drop(min(self._runs, key=lambda item: self._runs[item]["seen"]))
            self._runs[key] = {"runId": run_id, "at": at, "segment": None, "seen": self._monotonic()}
            self._keys[run_id] = key
        return {"runId": run_id, "startedAt": at}

    def progress(self, run_id, segment):
        """Heartbeat běhu s aktuálním přechodem; neznámý nebo prošlý běh je `JourneyRunUnknown`."""
        with self._lock:
            self._purge()
            key = self._keys.get(run_id)
            if key is None:
                raise JourneyRunUnknown(f"Běh {run_id} neexistuje nebo vypršel.")
            self._runs[key].update(at=_iso(self._wall()), segment=dict(segment), seen=self._monotonic())

    def finish(self, project, application_id, journey_id):
        """Doklad cesty je zapsaný: běh té cesty skončil."""
        with self._lock:
            self._drop((project, application_id, journey_id))

    def running(self, project):
        """{(applicationId, journeyId): {runId, at, segment}} živých běhů projektu."""
        with self._lock:
            self._purge()
            return {(application, journey): {"runId": run["runId"], "at": run["at"],
                                             "segment": dict(run["segment"]) if run["segment"] else None}
                    for (owner, application, journey), run in self._runs.items() if owner == project}


def start_journey_run(service, running, body):
    """Ověří tělo i cestu (stejně jako plán: 404 neznámá, 409 rozbitá či nejednoznačná) a zahájí běh."""
    project, journey_id, application_id = validate_start(body)
    plan = journey_plan(architecture_graph(service, project), journey_id, application_id)
    return running.start(project, plan["applicationId"], plan["journeyId"])
