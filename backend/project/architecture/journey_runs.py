"""Doklady přehrání cest zákazníka a jejich `lastRun` (`docs/brana-cesty.md` §3–§4).

Opora cestu sama nepřehrává a model nevolá: doklad odevzdá agent nebo člověk (výbava harnessu projektu) a Opora
ho jen ověří tvarem, odvodí `passed` a uloží jako neměnný záznam do `journey_runs` v `project.sqlite` (schéma
`database/schema/journey_run_schema.py`, přístup `database/repositories/journey_runs.py`). Záznam nese
`verification: "agent-reported; not independently verified"`, stejně jako výsledky kroků karty.

- Validace (chyba = `JourneyRunInvalid`, HTTP 422): jen známé klíče; `schema`, `applicationId`, `journeyId`,
  `planDigest` tvaru `sha256:<64 hex>`, `command` 1–500 znaků, `at` ISO 8601 (bez časové zóny = UTC), `segments`
  1–30 položek `{from, to, ok, reason?}` s dvojicí `from`/`to` z aktuálního plánu cesty, každá nejvýš jednou,
  `ok` bool, `reason` ≤ 300 znaků; `logUrl` nepovinné 1–500 znaků. Neznámá cesta je `JourneyNotFound` (404),
  rozbitá nebo nejednoznačná `JourneyConflict` (409) z `journey_plan`.
- `passed` se odvodí, nepíše se: každý segment plánu je v dokladu a všechny segmenty dokladu jsou `ok`.
- `lastRun` = poslední doklad cesty podle `at` (při shodě později uložený):
  `{at, passed, stale, command, failed, firstFailure?}`; `failed` je počet segmentů s `ok: false`,
  `firstFailure` první z nich v pořadí dokladu (`{from, to, reason?}`); `stale` = `planDigest` dokladu se liší
  od digestu aktuálního plánu (mapa se od běhu změnila). Cesta bez dokladu `lastRun` nemá; rozbitá cesta
  (bez plánu, a tedy bez digestu) také ne.
"""

import re
from datetime import UTC, datetime

from backend.project.architecture.journey_plan import journey_digests, journey_plan
from backend.project.architecture.journeys import derive_journeys
from backend.project.architecture.work_status import architecture_graph
from database.repositories.journey_runs import JourneyRunStore

SCHEMA = "opora.journey-run/1"
VERIFICATION = "agent-reported; not independently verified"
BODY_LIMIT = 64 * 1024
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
KEYS = {"schema", "applicationId", "journeyId", "planDigest", "command", "at", "segments", "logUrl"}
SEGMENT_KEYS = {"from", "to", "ok", "reason"}


class JourneyRunInvalid(ValueError):
    """Doklad nemá předepsaný tvar (HTTP 422)."""


def _text(value, name, limit, minimum=1):
    if not isinstance(value, str) or not minimum <= len(value) <= limit:
        raise JourneyRunInvalid(f"{name} musí být text o {minimum}–{limit} znacích.")
    return value


def _at(value):
    _text(value, "at", 64)
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise JourneyRunInvalid("at musí být čas ve tvaru ISO 8601.") from error
    moment = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


def _head(body):
    """Ověří tvar dokladu bez plánu; vrací (applicationId, journeyId)."""
    if not isinstance(body, dict):
        raise JourneyRunInvalid("Doklad musí být objekt JSON.")
    unknown = sorted(set(body) - KEYS)
    if unknown:
        raise JourneyRunInvalid(f"Neznámé klíče dokladu: {', '.join(unknown)}.")
    if body.get("schema") != SCHEMA:
        raise JourneyRunInvalid(f"schema musí být {SCHEMA}.")
    if not isinstance(body.get("planDigest"), str) or not DIGEST.fullmatch(body["planDigest"]):
        raise JourneyRunInvalid("planDigest musí mít tvar sha256:<64 hex>.")
    _text(body.get("command"), "command", 500)
    _at(body.get("at"))
    if "logUrl" in body:
        _text(body["logUrl"], "logUrl", 500)
    segments = body.get("segments")
    if not isinstance(segments, list) or not 1 <= len(segments) <= 30:
        raise JourneyRunInvalid("segments musí mít 1–30 položek.")
    for segment in segments:
        if not isinstance(segment, dict) or set(segment) - SEGMENT_KEYS or not {"from", "to", "ok"} <= set(segment):
            raise JourneyRunInvalid("Segment dokladu je {from, to, ok, reason?}.")
        _text(segment["from"], "from", 64)
        _text(segment["to"], "to", 64)
        if not isinstance(segment["ok"], bool):
            raise JourneyRunInvalid("ok segmentu musí být true nebo false.")
        if "reason" in segment:
            _text(segment["reason"], "reason", 300, minimum=0)
    return _text(body.get("applicationId"), "applicationId", 64), _text(body.get("journeyId"), "journeyId", 64)


def validate_run(body, plan):
    """Ověřený doklad proti plánu cesty: (záznam k uložení s odvozeným `passed`, `at` v UTC pro řazení)."""
    _head(body)
    planned = [(segment["from"], segment["to"]) for segment in plan["segments"]]
    reported = [(segment["from"], segment["to"]) for segment in body["segments"]]
    for pair in reported:
        if pair not in planned:
            raise JourneyRunInvalid(f"Přechod {pair[0]} → {pair[1]} v plánu cesty není.")
    if len(set(reported)) != len(reported):
        raise JourneyRunInvalid("Přechod se v dokladu opakuje.")
    passed = set(planned) <= set(reported) and all(segment["ok"] for segment in body["segments"])
    record = {key: body[key] for key in ("schema", "applicationId", "journeyId", "planDigest", "command", "at")}
    record["segments"] = [{key: segment[key] for key in ("from", "to", "ok", "reason") if key in segment}
                          for segment in body["segments"]]
    record.update({**({"logUrl": body["logUrl"]} if "logUrl" in body else {}),
                   "passed": passed, "verification": VERIFICATION})
    return record, _at(body["at"])


def last_run(run, digest):
    """`lastRun` cesty z jejího posledního dokladu proti `digest` aktuálního plánu."""
    failures = [segment for segment in run["segments"] if not segment["ok"]]
    first = failures[0] if failures else None
    return {"at": run["at"], "passed": run["passed"], "stale": run["planDigest"] != digest,
            "command": run["command"], "failed": len(failures),
            **({"firstFailure": {key: first[key] for key in ("from", "to", "reason") if key in first}}
               if first else {})}


def last_runs(graph, runs):
    """{(applicationId, journeyId): lastRun} nerozbitých cest grafu, které mají doklad."""
    return {key: last_run(runs[key], digest) for key, digest in journey_digests(graph).items() if key in runs}


def latest_journey_runs(service, project):
    """Poslední doklad každé cesty projektu: {(applicationId, journeyId): doklad}."""
    with service.reading(project):
        return JourneyRunStore(service.db_for(project), project).latest()


def record_journey_run(service, project, body):
    """Ověří doklad proti plánu přijaté architektury a uloží ho; vrací uložený záznam."""
    application_id, journey_id = _head(body)
    plan = journey_plan(architecture_graph(service, project), journey_id, application_id)
    record, at_utc = validate_run(body, plan)
    recorded_at = datetime.now(UTC).isoformat(timespec="microseconds")
    db = service.db_for(project)
    with service.lock_for(project), db:
        db.execute("BEGIN IMMEDIATE")
        JourneyRunStore(db, project).insert(record, at_utc, recorded_at)
    return {**record, "recordedAt": recorded_at}


def project_journeys(service, project):
    """Odvozené cesty přijaté architektury s `lastRun` (`GET /api/project-architecture/journeys`)."""
    graph = architecture_graph(service, project)
    runs = last_runs(graph, latest_journey_runs(service, project))
    return {"journeys": [{**item, **({"lastRun": runs[key]} if (key := (item["applicationId"], item["id"])) in runs else {})}
                         for item in derive_journeys(graph)]}
