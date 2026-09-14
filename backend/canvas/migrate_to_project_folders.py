"""Jednorázová migrace: centrální canvas.sqlite → registry.sqlite + projects/<id>/project.sqlite + project.json.

Spouští ji CanvasService automaticky, když v datovém kořeni leží canvas.sqlite a registry.sqlite ještě ne.
Stará databáze se nemaže, přejmenuje se na canvas.sqlite.migrated-<čas>.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from backend.canvas.project_folder import ProjectFolder
from database.schema.project_schema import (
    PROJECT_SCHEMA,
    PROJECT_TABLES,
    REGISTRY_SCHEMA,
    REGISTRY_TABLES,
)


def _tables(db: sqlite3.Connection) -> set[str]:
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in db.execute(f"PRAGMA table_info({table})")]


def _copy_rows(source: sqlite3.Connection, target: sqlite3.Connection, table: str, where: str = "", params=()) -> int:
    if table not in _tables(source):
        return 0
    columns = [c for c in _columns(source, table) if c in _columns(target, table)]
    if not columns:
        return 0
    names = ",".join(columns)
    rows = source.execute(f"SELECT {names} FROM {table} {where}", params).fetchall()
    if rows:
        target.executemany(f"INSERT OR IGNORE INTO {table}({names}) VALUES({','.join('?' * len(columns))})", rows)
    return len(rows)


def merge_duplicate_git_projects(registry: sqlite3.Connection, legacy: sqlite3.Connection) -> list[tuple[str, str]]:
    """Stejná URL vícekrát: zůstane záznam s workspaces nebo nastavením, ostatní se archivují. Vrací (ponechaný, archivovaný)."""
    merged = []
    groups: dict[str, list[str]] = {}
    for row in registry.execute("SELECT id, url FROM projects WHERE url != '' ORDER BY rowid"):
        groups.setdefault(row[1].rstrip("/").removesuffix(".git").casefold(), []).append(row[0])
    for ids in groups.values():
        if len(ids) < 2:
            continue

        def weight(pid: str) -> int:
            score = registry.execute("SELECT COUNT(*) FROM workspaces WHERE project_id=?", (pid,)).fetchone()[0] * 10
            if "project_settings" in _tables(legacy):
                score += legacy.execute("SELECT COUNT(*) FROM project_settings WHERE project_id=?", (pid,)).fetchone()[0]
            return score

        keep = max(ids, key=weight)
        for pid in ids:
            if pid != keep:
                registry.execute(
                    "INSERT OR IGNORE INTO archived_projects VALUES(?,?,?)",
                    (pid, json.dumps({"mergedInto": keep}), datetime.now(UTC).isoformat()),
                )
                merged.append((keep, pid))
    return merged


def migrate(data_root: Path) -> dict:
    data_root = Path(data_root)
    legacy_path = data_root / "canvas.sqlite"
    registry_path = data_root / "registry.sqlite"
    if not legacy_path.exists() or registry_path.exists():
        return {"migrated": False}
    legacy = sqlite3.connect(legacy_path)
    legacy.row_factory = sqlite3.Row
    registry = sqlite3.connect(registry_path)
    registry.executescript(REGISTRY_SCHEMA)
    counts = {table: _copy_rows(legacy, registry, table) for table in REGISTRY_TABLES}
    merged = merge_duplicate_git_projects(registry, legacy)
    registry.commit()

    project_ids = {"draft"}
    project_ids.update(r[0] for r in registry.execute("SELECT id FROM projects"))
    for table, column in PROJECT_TABLES.items():
        if table in _tables(legacy):
            project_ids.update(r[0] for r in legacy.execute(f"SELECT DISTINCT {column} FROM {table}") if r[0])

    folders = 0
    for pid in sorted(project_ids):
        try:
            folder = ProjectFolder(data_root, pid)
        except ValueError:
            continue
        if not folder.exists():
            project = registry.execute("SELECT name, url, branch, repo FROM projects WHERE id=?", (pid,)).fetchone()
            source = registry.execute("SELECT source_kind, source_path FROM project_sources WHERE project_id=?", (pid,)).fetchone()
            if pid == "draft":
                meta = registry.execute("SELECT name FROM builtin_project_metadata WHERE project_id='draft'").fetchone()
                folder.create(meta[0] if meta else "Lokální návrh", "empty")
            elif source is not None:
                folder.create(project[0] if project else pid, source[0], source[1] or "")
            else:
                folder.create(project[0] if project else pid, "git", project[1] if project else "", branch=(project[2] if project else "") or "")
        db = sqlite3.connect(folder.database)
        db.executescript(PROJECT_SCHEMA)
        for table, column in PROJECT_TABLES.items():
            _copy_rows(legacy, db, table, f"WHERE {column}=?", (pid,))
        db.commit()
        db.close()
        folders += 1

    legacy.close()
    registry.close()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    legacy_path.rename(data_root / f"canvas.sqlite.migrated-{stamp}")
    return {"migrated": True, "projects": folders, "registry": counts, "merged": merged}
