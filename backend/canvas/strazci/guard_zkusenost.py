"""Strážce `zkusenost` (`docs/strazci.md` §4): uzavření karty, merge PR a doklad cesty → záznam do OpenViking.

Spouští ho událost, ale bez háčku do míst, kde událost vzniká: strážce v každém ticku dočte nové řádky od svého
kurzoru (`guard_experience_cursor`) ve dvou zdrojích, `opora_events` (`card.closed`, `merge.done`) a `journey_runs`.
První běh v projektu jen nastaví kurzory na současnou hlavu (žádné doplňování historie). Ke každému zdroji vznikne
deterministický záznam (`zkusenost_record.py`) v outboxu `guard_experience` ve stejné transakci, ve které se posune
kurzor. Doručení je jako `backend/library/harness_memory.py`: nárok (claim/lease), role karty z plochy
(`agentRole`), zápis klíčem role přes `memory_service._role_client`, při chybě `retry` s odkladem, bez role
`waiting-role`. Vypnutá paměť nebo nedostupný OpenViking nic neblokuje: záznamy čekají ve frontě, doručení se v ticku
zastaví po první chybě a nejvýš `DELIVER_LIMIT` zápisů na projekt. Strážce nehlásí nálezy; bez nové události a bez
doručení přeskočí (`None`).
"""
import hashlib
import json

from backend.canvas.strazci import zkusenost_record as records
from backend.canvas.strazci.findings import at_of
from backend.canvas.strazci.guard_cesty import _page
from backend.canvas.strazci.guard_mapa import workspace_of
from backend.canvas.strazci.registry import Guard
from backend.integrations.openviking_client import OpenVikingUnavailable
from backend.memory import roles
from backend.project.architecture.journeys import derive_journeys
from backend.project.architecture.work_status import architecture_graph
from database.repositories import guard_experience as store
from database.repositories import harness_memory as harness_store
from database.repositories.journey_runs import JourneyRunStore

EVENT_KINDS = ("card.closed", "merge.done")
STEP_KINDS = ("step.done", "step.failed")
BATCH = 100
DELIVER_LIMIT = 2


def _events_head(db, project):
    return db.execute("SELECT COALESCE(MAX(id), 0) FROM opora_events WHERE project_id=?", (project,)).fetchone()[0]


def heads(service, project):
    """(hlavy zdrojů, kurzory strážce) nad jedním snímkem; kurzor None = první běh."""
    with service.reading(project):
        db = service.db_for(project)
        current = {"event": _events_head(db, project), "journey": JourneyRunStore(db, project).head()}
        return current, {source: store.cursor(db, project, source) for source in current}


def journey_pages(service, project):
    """{(applicationId, journeyId): první stránka cesty} přijaté architektury (karta záznamu cesty)."""
    return {(journey["applicationId"], journey["id"]): _page(journey)
            for journey in derive_journeys(architecture_graph(service, project)) if "broken" not in journey}


def _trigger(row):
    keys = ("id", "at", "workspaceId", "kind", "nodeId", "executionId", "prNumber", "data")
    return {**dict(zip(keys, row[:7])), "data": json.loads(row[7])}


def event_records(db, project, cursor, head):
    """(záznamy, nový kurzor) z `card.closed` / `merge.done` po `cursor` až po `head`."""
    rows = db.execute("SELECT id, at, workspace_id, kind, node_id, execution_id, pr_number, data FROM opora_events"
                      " WHERE project_id=? AND id>? AND id<=? AND kind IN (?,?) AND node_id IS NOT NULL ORDER BY id"
                      " LIMIT ?", (project, cursor, head, *EVENT_KINDS, BATCH)).fetchall()
    result = []
    for trigger in map(_trigger, rows):
        scope = "project_id=? AND workspace_id=? AND node_id=? AND id<?"
        parameters = [project, trigger["workspaceId"], trigger["nodeId"], trigger["id"]]
        if trigger["kind"] == "merge.done" and trigger["executionId"]:
            scope, parameters = scope + " AND execution_id=?", [*parameters, trigger["executionId"]]
        steps = db.execute(f"SELECT id, kind, execution_id, step_id FROM opora_events WHERE {scope} AND kind IN (?,?)"
                           " ORDER BY id", (*parameters, *STEP_KINDS)).fetchall()
        merge = trigger if trigger["kind"] == "merge.done" else None
        if merge is None:
            row = db.execute("SELECT pr_number, data FROM opora_events WHERE project_id=? AND workspace_id=? AND"
                             " node_id=? AND id<? AND kind='merge.done' ORDER BY id DESC LIMIT 1",
                             parameters[:4]).fetchone()
            merge = None if row is None else {"prNumber": row[0], "data": json.loads(row[1])}
        result.append(("event", trigger["id"], trigger["workspaceId"], trigger["nodeId"],
                       records.card_record(project, trigger, [tuple(step) for step in steps], merge)))
    return result, rows[-1][0] if len(rows) == BATCH else head


def journey_records(db, project, cursor, head, pages, workspace):
    """(záznamy, nový kurzor) z dokladů cest po `cursor`; cesta bez stránky (rozbitá, smazaná) záznam nemá."""
    store_runs = JourneyRunStore(db, project)
    runs = [(seq, run) for seq, run in store_runs.since(cursor, BATCH) if seq <= head]
    result = []
    for seq, run in runs:
        card = pages.get((run["applicationId"], run["journeyId"]))
        if card:
            previous = store_runs.previous(run["applicationId"], run["journeyId"], seq)
            result.append(("journey", seq, workspace, card,
                           records.journey_record(project, workspace, card, seq, run, previous)))
    return result, runs[-1][0] if len(runs) == BATCH else head


def collect(service, project, now):
    """Dočte nové zdroje a zařadí záznamy do outboxu; vrací počet zařazených, nebo None bez změny hlavy."""
    current, seen = heads(service, project)
    if all(seen[source] == current[source] for source in current):
        return None
    changed_journeys = seen["journey"] is not None and seen["journey"] != current["journey"]
    pages = journey_pages(service, project) if changed_journeys else {}
    workspace = workspace_of(service, project)
    queued = 0
    db = service.db_for(project)
    with service.lock_for(project), db:
        db.execute("BEGIN IMMEDIATE")
        for source, read in (("event", lambda c: event_records(db, project, c, current["event"])),
                             ("journey", lambda c: journey_records(db, project, c, current["journey"], pages, workspace))):
            cursor = store.cursor(db, project, source)
            if cursor is None:  # první běh: bez historie, jen hlava
                store.move_cursor(db, project, source, current[source])
                continue
            if cursor >= current[source]:
                continue
            items, moved = read(cursor)
            for item in items:
                store.enqueue(db, project, *item, at_of(now))
            queued += len(items)
            store.move_cursor(db, project, source, moved)
    return queued


def memory_uri(project, job, role):
    source, ident = job["key"][1], job["key"][2]
    digest = hashlib.sha256(f"{project}\0{source}\0{ident}".encode()).hexdigest()[:16]
    return f"viking://user/{role}/peers/{project}/resources/cards/{job['node']}/zkusenost-{source}-{digest}.md"


def deliver(service, memory, project, now):
    """Nejvýš `DELIVER_LIMIT` zápisů; první nedostupnost OpenVikingu doručení v tomto ticku ukončí."""
    results = []
    db = service.db_for(project)
    for _ in range(DELIVER_LIMIT):
        with service.lock_for(project), db:
            db.execute("BEGIN IMMEDIATE")
            job = store.claim(db, project, now)
            if job is None:
                break
            role = job["role"] or harness_store.role(db, {"role": "", "key": (project, job["workspace"]),
                                                          "node": job["node"]})
            if not isinstance(role, str) or roles.role(role) is None:
                store.finish(db, job, "waiting-role", now, error="missing-registered-role")
                results.append("waiting-role")
                continue
            store.pin_role(db, job, role)
        uri = memory_uri(project, job, role)
        text = json.dumps({**job["payload"], "role": role}, ensure_ascii=False, sort_keys=True, indent=1)
        state, error = "submitted", ""
        try:
            memory._role_client(role).write(role, uri, text, tags=["opora=1", "kind=guard-experience",
                                                                   f"project={project}"])
        except (ValueError, OSError, OpenVikingUnavailable):
            state, error = "retry", "memory-write-unavailable"
        with service.lock_for(project), db:
            changed = store.finish(db, job, state, now, error=error, role=role, uri=uri if state == "submitted" else "")
        results.append(state if changed else "lease-lost")
        if state == "retry":
            break
    return results


def run(ctx):
    queued = collect(ctx.service, ctx.project, ctx.now)
    memory = getattr(ctx.service, "memory_service", None)
    delivered = deliver(ctx.service, memory, ctx.project, ctx.now) if memory is not None and memory.enabled() else []
    return None if queued is None and not delivered else []


GUARD = Guard(id="zkusenost", label="Zkušenost pro agenty", every_s=10, run=run)
