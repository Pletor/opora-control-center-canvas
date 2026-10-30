"""OporaHub events outbox rows (docs/oporahub-events.md); writers own the transaction, readers page by cursor."""
import json

COLUMNS = ("id", "at", "project_id", "workspace_id", "kind", "node_id", "execution_id", "step_id", "pr_number",
           "stage", "health", "actor_kind", "actor_name", "data")
# Živý proces (docs/zivy-proces.md): nullable rozšíření; NULL u události Opory doplní čtení z `kind`.
PROCESS = ("source", "phase", "state", "title", "detail", "refs", "tool", "external_id")
JSON_FIELDS = ("refs", "tool")
ALL = COLUMNS + PROCESS


def public(row):
    """The exact event DTO of the live feed; optional fields are present as null."""
    value = dict(zip(ALL, row))
    process = {"source": value.get("source") or "opora", "phase": value.get("phase"), "state": value.get("state"),
               "title": value.get("title"), "detail": value.get("detail"),
               "refs": json.loads(value["refs"]) if value.get("refs") else None,
               "tool": json.loads(value["tool"]) if value.get("tool") else None,
               "externalId": value.get("external_id")}
    event = {"id": value["id"], "at": value["at"], "kind": value["kind"], "projectId": value["project_id"],
             "workspaceId": value["workspace_id"], "nodeId": value["node_id"], "executionId": value["execution_id"],
             "stepId": value["step_id"], "prNumber": value["pr_number"], "stage": value["stage"],
             "health": value["health"], "actor": {"kind": value["actor_kind"], "name": value["actor_name"]},
             "data": json.loads(value["data"]), **process}
    # Live process (docs/zivy-proces.md): a pure function derives phase/state/title from `kind`.
    from backend.canvas.opora_event_process import derive
    return derive(event)


def insert(db, event):
    """Append one event; returns its cursor id. The caller's transaction commits or rolls it back."""
    data = json.dumps(event["data"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    process = event.get("process") or {}
    extra = tuple(json.dumps(process[name], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                  if name in JSON_FIELDS and process.get(name) is not None else process.get(name)
                  for name in PROCESS)
    columns = COLUMNS[1:] + (PROCESS if process else ())
    cursor = db.execute("INSERT INTO opora_events(" + ",".join(columns) + ") VALUES("
                        + ",".join("?" * len(columns)) + ")",
                        (event["at"], event["projectId"], event["workspaceId"], event["kind"], event["nodeId"],
                         event["executionId"], event["stepId"], event["prNumber"], event["stage"], event["health"],
                         event["actor"]["kind"], event["actor"]["name"], data, *(extra if process else ())))
    return cursor.lastrowid


def has_external(db, project, external_id):
    """Dedupe přijatých událostí (kancelář): `id` producenta je v projektu nejvýš jednou."""
    return db.execute("SELECT 1 FROM opora_events WHERE project_id=? AND external_id=?",
                      (project, external_id)).fetchone() is not None


def last_by_source(db, project, workspace):
    """{source: poslední `at`} v rozsahu; NULL zdroj je Opora (zdraví živého procesu)."""
    rows = db.execute("SELECT COALESCE(source,'opora') AS src, MAX(at) FROM opora_events"
                      " WHERE project_id=? AND workspace_id=? GROUP BY src", (project, workspace)).fetchall()
    return {row[0]: row[1] for row in rows}


def prune(db, cutoff_at, max_rows):
    """Retention: drop events older than `cutoff_at` and everything beyond the newest `max_rows`."""
    db.execute("DELETE FROM opora_events WHERE at<?", (cutoff_at,))
    db.execute("DELETE FROM opora_events WHERE id<=(SELECT MAX(id) FROM opora_events)-?", (max_rows,))


def page(db, project, workspace, since, limit, node=None):
    """Events after `since` in cursor order, plus the outbox bounds needed to detect a retention gap."""
    condition, parameters = "project_id=? AND id>?", [project, since]
    if workspace is not None:
        condition, parameters = condition + " AND workspace_id=?", [*parameters, workspace]
    if node is not None:
        condition, parameters = condition + " AND node_id=?", [*parameters, node]
    rows = db.execute("SELECT " + ",".join(ALL) + " FROM opora_events WHERE " + condition
                      + " ORDER BY id LIMIT ?", (*parameters, limit)).fetchall()
    bounds = db.execute("SELECT MIN(id), MAX(id) FROM opora_events").fetchone()
    return [public(tuple(row)) for row in rows], bounds[0], bounds[1]


def head(db):
    """Highest event id in the outbox (0 when empty): the cursor of the snapshot read on `db`."""
    return db.execute("SELECT COALESCE(MAX(id), 0) FROM opora_events").fetchone()[0]


def last_of_execution(db, project, workspace, execution_id, kind):
    """`(at, data)` of the execution's newest event of `kind` in the scope, or None."""
    row = db.execute("SELECT at, data FROM opora_events WHERE project_id=? AND workspace_id=? AND kind=?"
                     " AND execution_id=? ORDER BY id DESC LIMIT 1",
                     (project, workspace, kind, execution_id)).fetchone()
    return None if row is None else (row[0], json.loads(row[1]))


def last_event_at(db, project, workspace):
    """`{nodeId: at}` of each card's newest event in the scope (one grouped SELECT)."""
    rows = db.execute("SELECT node_id, at FROM opora_events WHERE id IN (SELECT MAX(id) FROM opora_events"
                      " WHERE project_id=? AND workspace_id=? AND node_id IS NOT NULL GROUP BY node_id)",
                      (project, workspace)).fetchall()
    return {row[0]: row[1] for row in rows}


def last_step_at(db, project, workspace):
    """`{nodeId: at}` nejnovější události kroku (`step.*`) každé karty prostoru; spouštěč `card.stalled`."""
    rows = db.execute("SELECT node_id, MAX(at) FROM opora_events WHERE project_id=? AND workspace_id=?"
                      " AND node_id IS NOT NULL AND kind LIKE 'step.%' GROUP BY node_id", (project, workspace)).fetchall()
    return {row[0]: row[1] for row in rows}
