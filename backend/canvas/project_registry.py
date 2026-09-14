"""Registr projektů `registry.sqlite` v datovém kořeni: jen ID, název, zdroj a cesta složky.

Duplicity nesmí existovat: stejný zdroj (URL nebo kanonická cesta, bez ohledu na velikost písmen)
je odmítnut. Vše ostatní o projektu žije v jeho složce (ProjectFolder).
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path

from backend.canvas.project_folder import SOURCE_KINDS, ProjectFolder, valid_project_id


def canonical_source(kind: str, value: str) -> str:
    if kind not in SOURCE_KINDS:
        raise ValueError("Druh zdroje musí být git, local nebo empty.")
    if kind == "git":
        return value.strip().rstrip("/").removesuffix(".git").casefold()
    if kind == "local":
        return str(Path(value).resolve()).replace("\\", "/").casefold()
    return ""


class ProjectRegistry:
    def __init__(self, data_root: Path):
        self.data_root = Path(data_root).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.data_root / "registry.sqlite", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, source_kind TEXT NOT NULL,"
            " source_key TEXT NOT NULL, folder TEXT NOT NULL, created_at TEXT NOT NULL);"
            "CREATE UNIQUE INDEX IF NOT EXISTS projects_source ON projects(source_kind, source_key) WHERE source_key != '';"
            "CREATE TABLE IF NOT EXISTS archived_projects(project_id TEXT PRIMARY KEY, archived_at TEXT NOT NULL);"
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def folder(self, project_id: str) -> ProjectFolder:
        return ProjectFolder(self.data_root, project_id)

    def register(self, name: str, source_kind: str, source: str = "", *, project_id: str | None = None, branch: str = "", settings: dict | None = None) -> dict:
        project_id = valid_project_id(project_id or uuid.uuid4().hex)
        key = canonical_source(source_kind, source)
        with self.lock:
            if key:
                existing = self.db.execute("SELECT id, name FROM projects WHERE source_kind=? AND source_key=?", (source_kind, key)).fetchone()
                if existing:
                    raise ValueError(f"Tento zdroj už je připojený jako projekt „{existing['name']}“. Duplicity nejsou povoleny.")
            folder = self.folder(project_id)
            identity = folder.create(name, source_kind, source, branch=branch, settings=settings)
            self.db.execute(
                "INSERT INTO projects VALUES(?,?,?,?,?,?)",
                (project_id, identity["name"], source_kind, key, str(folder.path), identity["createdAt"]),
            )
            self.db.commit()
        return identity

    def rename(self, project_id: str, name: str) -> dict:
        with self.lock:
            identity = self.folder(project_id).update(name=name)
            self.db.execute("UPDATE projects SET name=? WHERE id=?", (identity["name"], project_id))
            self.db.commit()
        return identity

    def get(self, project_id: str) -> dict:
        with self.lock:
            row = self.db.execute("SELECT * FROM projects WHERE id=?", (valid_project_id(project_id),)).fetchone()
        if row is None:
            raise ValueError("Projekt neexistuje.")
        return dict(row)

    def list(self, include_archived: bool = False) -> list[dict]:
        sql = "SELECT p.* FROM projects p"
        if not include_archived:
            sql += " WHERE p.id NOT IN (SELECT project_id FROM archived_projects)"
        with self.lock:
            rows = self.db.execute(sql + " ORDER BY p.name COLLATE NOCASE, p.id").fetchall()
        return [dict(row) for row in rows]

    def archive(self, project_id: str, at: str) -> None:
        self.get(project_id)
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO archived_projects VALUES(?,?)", (project_id, at))
            self.db.commit()

    def is_archived(self, project_id: str) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM archived_projects WHERE project_id=?", (project_id,)).fetchone() is not None
