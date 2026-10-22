"""Živý proces: příjem událostí kanceláře do outboxu OporaHubu a zdraví zdrojů (docs/zivy-proces.md).

Přijatá událost `opora.process-event/1` se zapíše přes `emit_event` jako řádek `opora_events`
se `source`, `phase`, `state`, `title`, `detail`, `refs`, `tool` a `external_id` (= `id`
producenta, klíč dedupe). Tím jde kancelář i Opora jedním tokem `/api/oporahub/events` s jedním
kurzorem a jednou retencí outboxu. Druh (`kind`) kanceláře zůstává, jak ho poslala.
"""
from datetime import UTC, datetime

from backend.canvas.opora_events import PROCESS_SIGNAL, emit_event
from backend.canvas.process_event_validation import INGEST_SOURCES, batch, normalize
from database.repositories import opora_events as store

OFFICE_FRESH_MINUTES = 10
ACTOR_KIND = {"worker": "agent", "agent": "agent", "human": "human", "system": "system"}


def _scope_exists(service, project, workspace, known):
    key = (project, workspace)
    if key not in known:
        known[key] = service.project_exists(project) and (
            workspace in ("draft", "main") or any(row["id"] == workspace for row in service.workspaces(project)))
    return known[key]


def _actor(event, poster):
    actor = event.get("actor")
    if not actor:
        return {"kind": "agent", "name": poster}
    return {"kind": ACTOR_KIND[actor["kind"]], "name": actor.get("name") or actor.get("id") or poster}


def _emit(db, event, poster):
    refs = event["refs"]
    process = {"source": event["source"], "phase": event["phase"], "state": event["state"], "title": event["title"],
               "detail": event.get("detail"), "refs": refs, "tool": event.get("tool"), "external_id": event["id"]}
    data = {"seq": event["seq"], "sourceAt": event["at"]}
    if event.get("actor"):
        data["actor"] = event["actor"]
    return emit_event(db, project_id=refs["project"], workspace_id=refs["workspace"], kind=event["kind"],
                      node_id=refs.get("cardId"), execution_id=refs.get("executionId"), pr_number=refs.get("pr"),
                      actor=_actor(event, poster), data=data, process=process)


def ingest(service, payload, *, poster="office"):
    """Dávka z kanceláře → {accepted, duplicates, rejected[]}; tělo mimo kontrakt = ValueError."""
    raw_events = batch(payload)
    rejected, valid, known = [], [], {}
    for index, raw in enumerate(raw_events):
        try:
            event = normalize(raw, sources=INGEST_SOURCES)
            refs = event["refs"]
            if not refs.get("project") or not refs.get("workspace"):
                raise ValueError("refs.project a refs.workspace jsou povinné.")
            if not _scope_exists(service, refs["project"], refs["workspace"], known):
                raise ValueError("Projekt nebo pracovní prostor v Opoře neexistuje.")
        except ValueError as error:
            item = {"index": index, "error": str(error)}
            if isinstance(raw, dict) and isinstance(raw.get("id"), str):
                item["id"] = raw["id"][:200]
            rejected.append(item)
            continue
        valid.append(event)
    accepted = duplicates = 0
    for project in sorted({event["refs"]["project"] for event in valid}):
        db = service.db_for(project)
        with service.lock_for(project), db:
            db.execute("BEGIN IMMEDIATE")
            seen = set()
            for event in (item for item in valid if item["refs"]["project"] == project):
                if event["id"] in seen or store.has_external(db, project, event["id"]):
                    duplicates += 1
                    continue
                seen.add(event["id"])
                _emit(db, event, poster)
                accepted += 1
    if accepted:
        PROCESS_SIGNAL.notify()  # po commitu: čtenář proudu řádky už vidí
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


def _age(stamp, current):
    if not stamp:
        return None
    try:
        then = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return max(0.0, round((current - then).total_seconds(), 1))


def health(service, project, workspace, *, memory_status=None, fresh_minutes=OFFICE_FRESH_MINUTES):
    """Stáří poslední události podle zdroje, zda kancelář žije a stav paměti (OpenViking)."""
    current = datetime.now(UTC)
    with service.reading(project):
        latest = store.last_by_source(service.db_for(project), project, workspace)
    sources = {source: {"lastAt": latest.get(source), "ageSeconds": _age(latest.get(source), current)}
               for source in ("office", "opora", "github")}
    office_age = sources["office"]["ageSeconds"]
    return {"schema": "opora.process-health/1", "project": project, "workspace": workspace,
            "now": current.isoformat(), "sources": sources, "officeFreshMinutes": fresh_minutes,
            "officeConnected": office_age is not None and office_age <= fresh_minutes * 60,
            "memory": memory_status if memory_status is not None else {"status": "unavailable",
                                                                         "reason": "Paměť není zapojená."},
            "listeners": PROCESS_SIGNAL.waiting()}
