"""Hlavní složka projektu `projects/<project-id>/`: jediné místo, kde se všechno o projektu odehrává.

Zná cesty uvnitř složky a `project.json` (identita: ID, název, zdroj, nastavení). Nic jiného.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SOURCE_KINDS = ("git", "local", "empty")
SUBFOLDERS = ("main", "worktrees", "canvas", "nodes", "sectors", "processes", "memory", "packets", "maps", "runs", "oporahub")


def valid_project_id(value: str) -> str:
    if not isinstance(value, str) or not PROJECT_ID.match(value):
        raise ValueError("Neplatné ID projektu.")
    return value


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProjectFolder:
    def __init__(self, data_root: Path, project_id: str):
        self.id = valid_project_id(project_id)
        self.data_root = Path(data_root).resolve()
        self.path = self.data_root / "projects" / self.id

    # cesty uvnitř složky – jediný zdroj pravdy o rozložení
    @property
    def identity_file(self) -> Path:
        return self.path / "project.json"

    @property
    def main(self) -> Path:
        return self.path / "main"

    @property
    def worktrees(self) -> Path:
        return self.path / "worktrees"

    @property
    def canvas(self) -> Path:
        return self.path / "canvas"

    @property
    def processes(self) -> Path:
        return self.path / "processes"

    @property
    def memory(self) -> Path:
        return self.path / "memory"

    @property
    def packets(self) -> Path:
        return self.path / "packets"

    @property
    def maps(self) -> Path:
        return self.path / "maps"

    @property
    def runs(self) -> Path:
        return self.path / "runs"

    @property
    def oporahub(self) -> Path:
        return self.path / "oporahub"

    @property
    def database(self) -> Path:
        return self.path / "project.sqlite"

    def node(self, node_id: str) -> Path:
        if not isinstance(node_id, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", node_id):
            raise ValueError("Neplatné ID uzlu.")
        return self.path / "nodes" / node_id

    def workspace_graph(self, workspace_id: str) -> Path:
        """Graf plátna Git pracovního prostoru. Leží v datech plátna, ne v cílovém repu (to má jen kód)."""
        if not isinstance(workspace_id, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", workspace_id):
            raise ValueError("Neplatné ID pracovního prostoru.")
        return self.canvas / "workspaces" / workspace_id / "graph.json"

    def external_task(self, workspace_id: str, node_id: str) -> Path:
        """Markdown zadání pro externího agenta; patří do dat plátna, cílové repo zůstává čisté."""
        for value in (workspace_id, node_id):
            if not isinstance(value, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", value):
                raise ValueError("Neplatné ID pracovního prostoru nebo uzlu.")
        return self.packets / "external-tasks" / workspace_id / f"{node_id}.md"

    def storyboard(self, workspace_id: str, node_id: str) -> Path:
        """Storyboard karty (momenty, komentáře a šipky člověka); patří do dat plátna."""
        for value in (workspace_id, node_id):
            if not isinstance(value, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", value):
                raise ValueError("Neplatné ID pracovního prostoru nebo uzlu.")
        return self.canvas / "workspaces" / workspace_id / "storyboards" / f"{node_id}.json"

    def storyboard(self, workspace_id: str, node_id: str) -> Path:
        """Storyboard karty (momenty, komentáře a šipky člověka); patří do dat plátna."""
        for value in (workspace_id, node_id):
            if not isinstance(value, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", value):
                raise ValueError("Neplatné ID pracovního prostoru nebo uzlu.")
        return self.canvas / "workspaces" / workspace_id / "storyboards" / f"{node_id}.json"

    def sector(self, sector_id: str) -> Path:
        if not isinstance(sector_id, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", sector_id):
            raise ValueError("Neplatné ID sektoru.")
        return self.path / "sectors" / sector_id

    def exists(self) -> bool:
        return self.identity_file.is_file()

    def create(self, name: str, source_kind: str, source: str = "", *, branch: str = "", settings: dict | None = None) -> dict:
        if self.exists():
            raise ValueError("Složka projektu už existuje.")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Název projektu musí mít 1–120 znaků.")
        if source_kind not in SOURCE_KINDS:
            raise ValueError("Druh zdroje musí být git, local nebo empty.")
        stamp = now()
        identity = {
            "id": self.id,
            "name": name.strip(),
            "source": {"kind": source_kind, "value": source, "branch": branch},
            "settings": {"goal": "", "platform": "web", "revision": 1, **(settings or {})},
            "createdAt": stamp,
            "updatedAt": stamp,
        }
        for folder in SUBFOLDERS:
            (self.path / folder).mkdir(parents=True, exist_ok=True)
        self._write(identity)
        return identity

    def read(self) -> dict:
        try:
            return json.loads(self.identity_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError("Projekt neexistuje.") from None

    def update(self, **changes) -> dict:
        identity = self.read()
        if "name" in changes:
            name = changes.pop("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 120:
                raise ValueError("Název projektu musí mít 1–120 znaků.")
            identity["name"] = name.strip()
        if "settings" in changes:
            identity["settings"] = {**identity["settings"], **changes.pop("settings")}
        if changes:
            raise ValueError("Lze měnit jen name a settings.")
        identity["updatedAt"] = now()
        self._write(identity)
        return identity

    def summary(self) -> dict:
        """Co vidí frontend: název vždy, ID jen jako klíč."""
        identity = self.read()
        return {"id": identity["id"], "name": identity["name"], "sourceKind": identity["source"]["kind"], "path": str(self.path)}

    def _write(self, identity: dict) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        tmp = self.identity_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.identity_file)
