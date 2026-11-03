"""Registr Brainu v registry.sqlite (§3.4, schéma `database/schema/brain_schema.py`).

Artefakt má ID `opora:brain:<kind>:<name>`, verze je SHA commitu v gitu Brainu (`store.py`) a pin
`opora:brain:<kind>:<name>@<sha12>`. Na artefakt je právě jedna `active` verze: `activate` předchozí vyřadí.
Funkce dostávají spojení na registry.sqlite (`CanvasService.db`); zámek drží volající.
"""

import json
import uuid
from datetime import UTC, datetime

KINDS = ("skill", "tool", "workflow", "subagent", "connector")
LINK_KINDS = ("log_event", "eval_run", "canvas_node")


def _now():
    return datetime.now(UTC).isoformat()


def artifact_id(kind, name):
    if kind not in KINDS:
        raise ValueError(f"Neznámý druh artefaktu {kind!r}.")
    return f"opora:brain:{kind}:{name}"


def pin(artifact, sha):
    return f"{artifact}@{sha[:12]}"


def ensure_artifact(db, kind, plugin, name, project_types=()):
    """Artefakt (vytvoří, když chybí); vrací jeho ID."""
    aid = artifact_id(kind, name)
    with db:
        db.execute("INSERT OR IGNORE INTO brain_artifacts(id,kind,plugin,name,project_types,created_at) "
                   "VALUES(?,?,?,?,?,?)", (aid, kind, plugin, name, json.dumps(list(project_types)), _now()))
    return aid


def add_version(db, artifact, sha, content_ref, baseline_version_id=None):
    """Nová verze jako `candidate`; stejné SHA podruhé vrátí existující verzi. Vrací ID verze."""
    row = db.execute("SELECT id FROM brain_artifact_versions WHERE artifact_id=? AND version=?",
                     (artifact, sha)).fetchone()
    if row:
        return row["id"]
    vid = uuid.uuid4().hex
    with db:
        db.execute("INSERT INTO brain_artifact_versions(id,artifact_id,version,content_ref,status,baseline_version_id,"
                   "created_at) VALUES(?,?,?,?,'candidate',?,?)",
                   (vid, artifact, sha, content_ref, baseline_version_id, _now()))
    return vid


def activate(db, version_id):
    """Verze se stane aktivní, dosavadní aktivní verze artefaktu jde do `retired` (jedna transakce)."""
    row = db.execute("SELECT artifact_id FROM brain_artifact_versions WHERE id=?", (version_id,)).fetchone()
    if row is None:
        raise LookupError("Verze artefaktu neexistuje.")
    with db:
        db.execute("UPDATE brain_artifact_versions SET status='retired' WHERE artifact_id=? AND status='active' "
                   "AND id<>?", (row["artifact_id"], version_id))
        db.execute("UPDATE brain_artifact_versions SET status='active' WHERE id=?", (version_id,))


def rollback(db, artifact):
    """Návrat na předchozí aktivní verzi (nejnovější `retired` starší než aktivní), bez evalu; vrací ID verze.
    LookupError, když artefakt nemá aktivní verzi nebo předchozí verzi."""
    current = db.execute("SELECT created_at, rowid FROM brain_artifact_versions WHERE artifact_id=? AND status='active'",
                         (artifact,)).fetchone()
    row = current and db.execute(
        "SELECT id FROM brain_artifact_versions WHERE artifact_id=? AND status='retired' AND (created_at<? OR "
        "(created_at=? AND rowid<?)) ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (artifact, current["created_at"], current["created_at"], current["rowid"])).fetchone()
    if row is None:
        raise LookupError("Artefakt nemá předchozí aktivní verzi.")
    activate(db, row["id"])
    return row["id"]


def version(db, version_id):
    """Verze s artefaktem: `{id, artifact_id, plugin, name, version, content_ref, status, baseline_version_id}`."""
    row = db.execute("SELECT v.id, v.artifact_id, a.plugin, a.name, v.version, v.content_ref, v.status, "
                     "v.baseline_version_id FROM brain_artifact_versions v JOIN brain_artifacts a ON a.id=v.artifact_id "
                     "WHERE v.id=?", (version_id,)).fetchone()
    return dict(row) if row else None


def link(db, version_id, target_kind, target_ref):
    if target_kind not in LINK_KINDS:
        raise ValueError(f"Neznámý druh vazby {target_kind!r}.")
    with db:
        db.execute("INSERT INTO brain_links(id,version_id,target_kind,target_ref,created_at) VALUES(?,?,?,?,?)",
                   (uuid.uuid4().hex, version_id, target_kind, target_ref, _now()))


def _artifact(row, active):
    value = {key: row[key] for key in ("id", "kind", "plugin", "name", "created_at")}
    value["project_types"] = json.loads(row["project_types"])
    value["active"] = active and {**active, "pin": pin(row["id"], active["version"])}
    return value


def _version(row):
    return {key: row[key] for key in ("id", "version", "content_ref", "status", "eval_score", "baseline_version_id",
                                      "created_at")}


def active(db, artifact):
    """Aktivní verze artefaktu: `{artifact_id, plugin, name, version, content_ref, pin}`; None bez aktivní verze."""
    row = db.execute("SELECT a.plugin, a.name, v.version, v.content_ref FROM brain_artifacts a JOIN "
                     "brain_artifact_versions v ON v.artifact_id=a.id AND v.status='active' WHERE a.id=?",
                     (artifact,)).fetchone()
    if row is None:
        return None
    return {"artifact_id": artifact, **dict(row), "pin": pin(artifact, row["version"])}


def list_artifacts(db):
    rows = db.execute("SELECT * FROM brain_artifacts ORDER BY plugin, name").fetchall()
    actives = {row["artifact_id"]: _version(row) for row in
               db.execute("SELECT * FROM brain_artifact_versions WHERE status='active'")}
    return [_artifact(row, actives.get(row["id"])) for row in rows]


def get_artifact(db, artifact):
    """Artefakt s verzemi (nejnovější první) a vazbami každé verze; None, když neexistuje."""
    row = db.execute("SELECT * FROM brain_artifacts WHERE id=?", (artifact,)).fetchone()
    if row is None:
        return None
    versions = [_version(item) for item in db.execute(
        "SELECT * FROM brain_artifact_versions WHERE artifact_id=? ORDER BY created_at DESC, rowid DESC", (artifact,))]
    for version in versions:
        version["pin"] = pin(artifact, version["version"])
        version["links"] = [dict(item) for item in db.execute(
            "SELECT id, target_kind, target_ref, created_at FROM brain_links WHERE version_id=? ORDER BY created_at",
            (version["id"],))]
    value = _artifact(row, next((v for v in versions if v["status"] == "active"), None))
    return {**value, "versions": versions}
