"""Záloha a návrat migrace architektury (`docs/domeny-a-worktree.md` §5, body 4 a 6).

Záloha je konzistentní snímek pořízený pod zámkem grafu projektu: `project.sqlite` přes SQLite
backup API, kopie všech `canvas/workspaces/<wid>/graph.json` a `manifest.json` (cesty, sha256,
soubory, které neexistovaly). Po dokončení migrace se do manifestu zapíše stav „po“; `down()`
odmítne návrat, když se od té doby kterýkoli krytý soubor změnil (jinak by smazal novou práci),
ledaže volající řekne `force`. Grafy prostorů se vrací bajtově, databáze stránku po stránce přes
backup API do živého spojení (obsah všech tabulek je stejný jako před migrací).
"""

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime

from backend.canvas.workspace_graph_storage import refuse_authority_restore
from database.schema.project_initialization import restore_project_backup

BACKUP_ID = re.compile(r"^architecture-\d{8}T\d{6}Z-[0-9a-f]{8}$")
MANIFEST = "manifest.json"
DATABASE = "project.sqlite"
# Stav migrace se do otisku databáze nepočítá: mění ho sama migrace, ne práce v projektu.
STATE_ROWS = 'INSERT INTO "architecture_migrations"'


def now():
    return datetime.now(UTC).isoformat()


def new_backup_id():
    return "architecture-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def backup_dir(service, pid, backup_id):
    if not isinstance(backup_id, str) or not BACKUP_ID.match(backup_id):
        raise ValueError("Neplatné ID zálohy migrace.")
    return service.folder(pid).canvas / "backups" / backup_id


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha256(path.read_bytes()) if path.is_file() else None


def database_digest(db):
    """Otisk obsahu všech tabulek projektu (bez stavu migrace); nezávisí na WAL ani checkpointu."""
    digest = hashlib.sha256()
    for line in db.iterdump():
        if not line.startswith(STATE_ROWS):
            digest.update(line.encode("utf-8") + b"\n")
    return digest.hexdigest()


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(".restore-" + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _inside(folder, relative):
    path = (folder.path / relative).resolve()
    if not path.is_relative_to(folder.path.resolve()):
        raise ValueError("Cesta v manifestu zálohy míří mimo složku projektu.")
    return path


def read_manifest(service, pid, backup_id):
    path = backup_dir(service, pid, backup_id) / MANIFEST
    if not path.is_file():
        raise ValueError("Záloha migrace neexistuje.")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("project") != pid:
        raise ValueError("Záloha patří jinému projektu.")
    return manifest


def _write_manifest(service, pid, manifest):
    path = backup_dir(service, pid, manifest["backupId"]) / MANIFEST
    _write_atomic(path, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))


def take_backup(service, pid, workspaces, backup_id):
    """Snímek projektu před migrací. Volající drží `graph_lock_for(pid)`; `workspaces` = ID Git prostorů."""
    folder = service.folder(pid)
    target = backup_dir(service, pid, backup_id)
    target.mkdir(parents=True, exist_ok=False)
    with service.lock_for(pid):
        db = service.db_for(pid)
        copy = sqlite3.connect(target / DATABASE)
        try:
            db.backup(copy)
            copy.execute("PRAGMA journal_mode=DELETE")  # samostatný soubor bez -wal vedle sebe
        finally:
            copy.close()
        before = database_digest(db)
    files = []
    for wid in workspaces:
        path = service.graph_file(pid, wid)
        data = path.read_bytes() if path.is_file() else None
        if data is not None:
            _write_atomic(target / "workspaces" / wid / "graph.json", data)
        files.append({
            "workspace": wid,
            "path": path.relative_to(folder.path).as_posix(),
            "existed": data is not None,
            "sha256": sha256(data) if data is not None else None,
        })
    manifest = {
        "backupId": backup_id,
        "project": pid,
        "createdAt": now(),
        "database": {"file": DATABASE, "sha256": file_sha(target / DATABASE), "digest": before},
        "files": files,
        "missing": [item["path"] for item in files if not item["existed"]],
        "after": None,
        "restoredAt": None,
    }
    _write_manifest(service, pid, manifest)
    return manifest


def _current(service, pid, manifest):
    folder = service.folder(pid)
    with service.lock_for(pid):
        database = database_digest(service.db_for(pid))
    return {"database": database, "files": {item["path"]: file_sha(_inside(folder, item["path"])) for item in manifest["files"]}}


def seal(service, pid, backup_id):
    """Zapíše do manifestu stav po migraci; podle něj `down()` pozná pozdější změny."""
    manifest = read_manifest(service, pid, backup_id)
    manifest["after"] = {**_current(service, pid, manifest), "at": now()}
    _write_manifest(service, pid, manifest)
    return manifest


def changes_since_migration(service, pid, manifest):
    after = manifest["after"]
    current = _current(service, pid, manifest)
    changed = [path for path, sha in current["files"].items() if after["files"].get(path) != sha]
    if current["database"] != after["database"]:
        changed.insert(0, DATABASE)
    return changed


def down(service, pid, backup_id, force=False):
    """Vrátí projekt do stavu zálohy. Bez `force` jen tehdy, když se po migraci nic nezměnilo."""
    with service.graph_lock_for(pid):
        with service.lock_for(pid):
            refuse_authority_restore(service.db_for(pid))
        manifest = read_manifest(service, pid, backup_id)
        target = backup_dir(service, pid, backup_id)
        if not force:
            if manifest.get("restoredAt"):
                raise ValueError("Tato záloha už byla vrácena.")
            if manifest.get("after") is None:
                raise ValueError("Migrace nedoběhla do konce; návrat bez kontroly změn jde jen s force.")
            changed = changes_since_migration(service, pid, manifest)
            if changed:
                raise ValueError("Od dokončení migrace se změnilo: " + ", ".join(changed[:10])
                                 + ". Návrat by tyto změny smazal; použijte force.")
        if file_sha(target / DATABASE) != manifest["database"]["sha256"]:
            raise ValueError("Záloha databáze je poškozená (nesedí sha256).")
        blobs = {}
        for item in manifest["files"]:
            if item["existed"]:
                data = (target / "workspaces" / item["workspace"] / "graph.json").read_bytes()
                if sha256(data) != item["sha256"]:
                    raise ValueError(f"Záloha grafu {item['path']} je poškozená (nesedí sha256).")
                blobs[item["path"]] = data
        folder = service.folder(pid)
        with service.lock_for(pid):
            db = service.db_for(pid)
            restore_project_backup(db, target / DATABASE)
        for item in manifest["files"]:
            path = _inside(folder, item["path"])
            if item["existed"]:
                _write_atomic(path, blobs[item["path"]])
            else:
                path.unlink(missing_ok=True)
        manifest["restoredAt"] = now()
        _write_manifest(service, pid, manifest)
        return {
            "project": pid,
            "phase": "restored",
            "backup": backup_id,
            "restored": [DATABASE, *(item["path"] for item in manifest["files"] if item["existed"])],
            "removed": manifest["missing"],
            "message": "Projekt je vrácený do stavu před migrací architektury.",
        }
