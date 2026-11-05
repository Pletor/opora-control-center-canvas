"""Velín V2: srdce, fronta, dávky, brána a prompt srdce z Brainu pro `GET /api/pletor/heart`. Jen čte; zdroj, který
selže, vrátí `{error}` místo dat (kontrakt docs/navrhy/2026-11-05-pletor-opora-dashboard.md)."""
from backend.agi_pletor.context import heart_line
from backend.brain_opora.determinism import gate_setting
from backend.brain_opora.heart import batch

HEART_SKILL = "opora:brain:skill:heart"
BATCHES = 20
BATCH_KEYS = ("id", "startedAt", "finishedAt", "at", "status", "summary", "costUsd", "ok")


def safe(read):
    try:
        return read()
    except Exception as error:  # noqa: BLE001 – jedna sekce nesmí shodit celou routu
        return {"error": str(error) or type(error).__name__}


def _status(heart, project):
    status = heart.status(project)
    return {**{key: value for key, value in status.items() if key != "batches"}, **heart_line(status)}


def _queue(heart, project):
    # Fronta srdce je `pending[project] = [(workspace, item, due)]`, takže jde po prostorech.
    with heart.lock:
        items = list(heart.pending.get(project, []))
    counts = {}
    for workspace, _item, _due in items:
        counts[workspace] = counts.get(workspace, 0) + 1
    return [{"workspace": workspace, "pending": count} for workspace, count in counts.items()]


def _batches(heart, project):
    try:
        found = batch.read_journal(heart.brain(project), BATCHES)  # heart.status drží jen posledních 5
    except Exception:  # noqa: BLE001 – bez deníku zbývá výřez ze stavu
        found = heart.status(project).get("batches") or []
    return [{key: entry[key] for key in BATCH_KEYS if key in entry} for entry in found[-BATCHES:]]


def _brain(service):
    with service.registry_lock:
        row = service.db.execute(
            "SELECT version, created_at FROM brain_artifact_versions WHERE artifact_id=? AND status='active' "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (HEART_SKILL,)).fetchone()
    return {"version": row["version"], "activatedAt": row["created_at"]} if row else None


def heart_view(service, heart, project, workspace):
    return {"status": safe(lambda: _status(heart, project)), "queue": safe(lambda: _queue(heart, project)),
            "batches": safe(lambda: _batches(heart, project)), "gate": safe(lambda: gate_setting.is_on(service, project)),
            "brain": safe(lambda: _brain(service))}
