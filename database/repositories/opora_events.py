"""OporaHub events outbox rows (docs/oporahub-events.md); writers own the transaction, readers page by cursor."""
import json

COLUMNS = ("id", "at", "project_id", "workspace_id", "kind", "node_id", "execution_id", "step_id", "pr_number",
           "stage", "health", "actor_kind", "actor_name", "data")


def public(row):
    """The exact event DTO of the live feed; optional fields are present as null."""
    value = dict(zip(COLUMNS, row))
    return {"id": value["id"], "at": value["at"], "kind": value["kind"], "projectId": value["project_id"],
            "workspaceId": value["workspace_id"], "nodeId": value["node_id"], "executionId": value["execution_id"],
            "stepId": value["step_id"], "prNumber": value["pr_number"], "stage": value["stage"],
            "health": value["health"], "actor": {"kind": value["actor_kind"], "name": value["actor_name"]},
            "data": json.loads(value["data"])}


def insert(db, event):
    """Append one event; returns its cursor id. The caller's transaction commits or rolls it back."""
    data = json.dumps(event["data"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cursor = db.execute("INSERT INTO opora_events(" + ",".join(COLUMNS[1:]) + ") VALUES("
                        + ",".join("?" * (len(COLUMNS) - 1)) + ")",
                        (event["at"], event["projectId"], event["workspaceId"], event["kind"], event["nodeId"],
                         event["executionId"], event["stepId"], event["prNumber"], event["stage"], event["health"],
                         event["actor"]["kind"], event["actor"]["name"], data))
    return cursor.lastrowid


def prune(db, cutoff_at, max_rows):
    """Retention: drop events older than `cutoff_at` and everything beyond the newest `max_rows`."""
    db.execute("DELETE FROM opora_events WHERE at<?", (cutoff_at,))
    db.execute("DELETE FROM opora_events WHERE id<=(SELECT MAX(id) FROM opora_events)-?", (max_rows,))


def page(db, project, workspace, since, limit):
    """Events after `since` in cursor order, plus the outbox bounds needed to detect a retention gap."""
    condition, parameters = "project_id=? AND id>?", [project, since]
    if workspace is not None:
        condition, parameters = condition + " AND workspace_id=?", [*parameters, workspace]
    rows = db.execute("SELECT " + ",".join(COLUMNS) + " FROM opora_events WHERE " + condition
                      + " ORDER BY id LIMIT ?", (*parameters, limit)).fetchall()
    bounds = db.execute("SELECT MIN(id), MAX(id) FROM opora_events").fetchone()
    return [public(tuple(row)) for row in rows], bounds[0], bounds[1]
