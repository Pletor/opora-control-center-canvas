"""Outbox zkušenosti strážců pro OpenViking (`guard_experience`, kurzory `guard_experience_cursor`).

Vzor `database/repositories/harness_memory.py`: `enqueue` je idempotentní (zdroj nejvýš jednou), `claim` bere řádek
nárokem na 300 s (propadlý nárok vezme další průchod), `finish` zapíše výsledek jen držitel nároku; `retry` odkládá
2^pokusů s (nejvýš hodinu), `waiting-role` hodinu. Transakci vlastní volající.
"""
import json
import uuid

KEY = "project_id=? AND source=? AND source_id=?"
LEASE_S = 300
WAITING_ROLE_S = 3600
DUE = "((state IN ('pending','retry','waiting-role') AND next_attempt<=?) OR (state='working' AND lease_until<=?))"


def cursor(db, project, source):
    """Kam strážce ve zdroji dočetl; None = ještě nikdy (první běh)."""
    row = db.execute("SELECT cursor FROM guard_experience_cursor WHERE project_id=? AND source=?",
                     (project, source)).fetchone()
    return None if row is None else row[0]


def move_cursor(db, project, source, value):
    db.execute("INSERT INTO guard_experience_cursor(project_id,source,cursor) VALUES(?,?,?) ON CONFLICT(project_id,"
               "source) DO UPDATE SET cursor=excluded.cursor", (project, source, value))


def enqueue(db, project, source, source_id, workspace, node, payload, at):
    db.execute("INSERT OR IGNORE INTO guard_experience VALUES(?,?,?,?,?,?,'pending',0,0,'',0,'','','',?)",
               (project, source, source_id, workspace, node,
                json.dumps(payload, ensure_ascii=False, sort_keys=True), at))


def claim(db, project, now):
    row = db.execute("SELECT source,source_id FROM guard_experience WHERE project_id=? AND " + DUE
                     + " ORDER BY source,source_id LIMIT 1", (project, now, now)).fetchone()
    if row is None:
        return None
    key, owner = (project, *row), uuid.uuid4().hex
    changed = db.execute("UPDATE guard_experience SET state='working',attempts=attempts+1,lease_owner=?,lease_until=?"
                         " WHERE " + KEY + " AND " + DUE, (owner, now + LEASE_S, *key, now, now)).rowcount
    if not changed:
        return None
    value = db.execute("SELECT workspace_id,node_id,payload,attempts,role_id FROM guard_experience WHERE " + KEY,
                       key).fetchone()
    return {"key": key, "owner": owner, "workspace": value[0], "node": value[1], "payload": json.loads(value[2]),
            "attempts": value[3], "role": value[4]}


def finish(db, job, state, now, *, error="", role="", uri=""):
    delay = (min(3600, 2 ** min(job["attempts"], 11)) if state == "retry"
             else WAITING_ROLE_S if state == "waiting-role" else 0)
    return db.execute("UPDATE guard_experience SET state=?,next_attempt=?,lease_owner='',lease_until=0,role_id=?,uri=?,"
                      "error=? WHERE " + KEY + " AND lease_owner=?",
                      (state, now + delay, role, uri, error, *job["key"], job["owner"])).rowcount


def states(db, project):
    """{state: počet} řádků projektu (přehled pro testy a ladění)."""
    return dict(db.execute("SELECT state, COUNT(*) FROM guard_experience WHERE project_id=? GROUP BY state",
                           (project,)).fetchall())


def pin_role(db, job, role):
    """Role se připne před zápisem, aby opakování po ztracené odpovědi psalo pod stejnou rolí."""
    db.execute("UPDATE guard_experience SET role_id=? WHERE " + KEY + " AND lease_owner=?", (role, *job["key"], job["owner"]))
