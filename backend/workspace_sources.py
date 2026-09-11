"""Skutečný pracovní strom; nikdy nečte obsah ani nespouští projektový kód."""

import os
import re
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Query
from pathspec import GitIgnoreSpec

RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.IGNORECASE)

NOISE_DIRECTORIES = frozenset({
    'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache', '.ruff_cache',
    '.mypy_cache', '.cache', 'dist', 'build', '.next', '.nuxt', '.data', '.worktrees',
})


def working_ignore_specs(root, target):
    """Čte pouze omezené .gitignore uvnitř ověřené cesty; funguje i bez Git repo."""
    result = []
    directories = [root]
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        directories.append(current)
    for directory in directories:
        ignore = directory / '.gitignore'
        if not ignore.exists() and not ignore.is_symlink():
            continue
        if reparse(ignore) or not ignore.is_file():
            raise ValueError('Filtr nelze načíst: .gitignore není bezpečný běžný soubor.')
        with ignore.open('rb') as stream:
            content = stream.read(262145)
        if len(content) > 262144:
            raise ValueError('Filtr .gitignore překročil limit 256 KiB.')
        try:
            spec = GitIgnoreSpec.from_lines(content.decode('utf-8-sig').splitlines())
        except (UnicodeError, ValueError) as exc:
            raise ValueError('Filtr .gitignore nelze zpracovat.') from exc
        result.append((directory, spec))
    return result


def working_hidden(root, entry, specs):
    """Filtr prezentace není oprávnění ke čtení nebo důkaz nepoužívaného kódu."""
    relative = Path(entry['path'])
    if any(part.casefold() in NOISE_DIRECTORIES for part in relative.parts):
        return True
    if relative.name.casefold() == '.env' or relative.name.casefold().startswith('.env.'):
        return True
    # Ignorovaný rodič nelze znovu zahrnout pouhou negací potomka.
    for candidate in [*reversed(relative.parents), relative]:
        if candidate == Path('.'):
            continue
        ignored = False
        is_directory = candidate != relative or entry['kind'] == 'directory'
        for directory, spec in specs:
            absolute = root / candidate
            if not absolute.is_relative_to(directory) or absolute == directory:
                continue
            name = absolute.relative_to(directory).as_posix() + ('/' if is_directory else '')
            for pattern in spec.patterns:
                if pattern.include is not None and pattern.match_file(name) is not None:
                    ignored = pattern.include
        if ignored:
            return True
    return False


class SourceMissing(ValueError):
    """Zdroj (kořen nebo cesta) prostě není přítomen; není to porušení hranice.

    Zůstává ValueError, takže HTTP odpověď je dál 409 se stejnou hláškou; volající,
    kteří mají vlastní uložená data (dokumentace), si tento případ mohou odchytit
    a zůstat čitelní, aniž by se změkčily kontroly traversalu a reparse bodů.
    """


def relative_path(value):
    if not isinstance(value, str) or len(value.encode("utf-8")) > 2048:
        raise ValueError("Neplatná relativní cesta.")
    if value == "":
        return value
    for part in value.split("/"):
        if (not part or part in {".", ".."} or part.lower() == ".git"
                or part.endswith((".", " ")) or RESERVED.match(part)
                or len(part.encode("utf-8")) > 255
                or any(ord(c) < 32 or c in '\\:*?"<>|' for c in part)):
            raise ValueError("Neplatná relativní cesta.")
    return value


def reparse(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


class WorkspaceSources:
    def __init__(self, service):
        self.service = service

    def root(self, project, workspace):
        with self.service.lock:
            item = self.service.project_hub.settings(project)["project"]
            if item["sourceKind"] == "git":
                root, _ = self.service.location(project, workspace)
            else:
                if workspace != "draft":
                    raise ValueError("Tento projekt používá pracovní prostor draft.")
                root = Path(item["sourcePath"]) if item["sourcePath"] else None
        if root is None:
            return None
        if not root.is_dir():
            raise SourceMissing("Připojený zdroj není dostupný.")
        if reparse(root):
            raise ValueError("Kořen projektu nesmí být nahrazen odkazem.")
        canonical = root.resolve()
        if canonical != root.absolute():
            raise ValueError("Umístění projektu se změnilo; připojte jej znovu.")
        return canonical

    def target(self, root, path):
        target = root
        for part in path.split("/") if path else []:
            target = target / part
            if reparse(target):
                raise ValueError("Odkazy a junctiony nelze otevřít.")
        target = target.resolve(strict=True)
        if not target.is_relative_to(root):
            raise ValueError("Cesta opouští připojený projekt.")
        return target

    def open_file(self, payload):
        """Otevře ověřenou položku či složku, nikdy ne její obsah jako program."""
        if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "path", "action"}:
            raise ValueError("Otevření vyžaduje project, workspace, path a action.")
        path = relative_path(payload["path"])
        action = payload["action"]
        if not isinstance(action, str) or action not in {"vscode", "folder", "folder-vscode", "workspace-vscode"}:
            raise ValueError("Neplatná akce otevření.")
        if not all(isinstance(payload[key], str) and payload[key] for key in ("project", "workspace")):
            raise ValueError("Vyberte projekt a pracovní prostor.")
        if action == "workspace-vscode" and (path or payload["workspace"] in {"draft", "main"}):
            raise ValueError("Nové okno vyžaduje kořen konkrétního worktree.")
        if not path and action != "workspace-vscode":
            raise ValueError("Vyberte soubor nebo složku.")
        if os.name != "nt":
            raise ValueError("Otevírání souborů je dostupné pouze v lokální aplikaci na Windows.")
        try:
            with self.service.graph_lock:
                root = self.root(payload["project"], payload["workspace"])
                if root is None:
                    raise ValueError("Projekt nemá připojený zdrojový adresář.")
                target = self.target(root, path)
                if not target.is_file() and not target.is_dir():
                    raise ValueError("Vybraná položka není soubor ani složka.")
                folder = target if target.is_dir() else target.parent
                if action == "workspace-vscode":
                    # Jen instalovaný editor, nikoli code.cmd nalezený v pracovním stromu/PATH.
                    candidates = [Path(os.environ[key]) / suffix for key, suffix in (
                        ("LOCALAPPDATA", "Programs/Microsoft VS Code/Code.exe"),
                        ("PROGRAMFILES", "Microsoft VS Code/Code.exe"),
                        ("PROGRAMFILES(X86)", "Microsoft VS Code/Code.exe"),
                    ) if os.environ.get(key)]
                    editor = next((candidate for candidate in candidates if candidate.is_file()), None)
                    if editor is None:
                        raise ValueError("Instalace VS Code nebyla nalezena ve standardním umístění.")
                    environment = dict(os.environ)
                    environment.pop("ELECTRON_RUN_AS_NODE", None)
                    subprocess.Popen([str(editor), "--new-window", str(folder)], shell=False,
                                     cwd=str(editor.parent), env=environment,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    destination = str(folder) if action == "folder" else "vscode://file/" + quote(
                        (folder if action == "folder-vscode" else target).as_posix(), safe="/:")
                    os.startfile(destination)
        except OSError as exc:
            raise ValueError("Soubor nelze otevřít. Ověřte jeho dostupnost a instalaci VS Code pro akci vscode.") from exc
        return {"project": payload["project"], "workspace": payload["workspace"],
                "path": path, "action": action, "status": "requested"}

    def tree(self, project, workspace, path="", offset=0, limit=200, visibility="all"):
        path = relative_path(path)
        root = self.root(project, workspace)
        if root is None:
            return {"root": None, "path": path, "entries": [], "total": 0,
                    "hasMore": False, "nextOffset": None, "available": False, "observedAt": None}
        target = self.target(root, path)
        if not target.is_dir():
            raise ValueError("Strom vyžaduje složku.")
        entries = []
        with os.scandir(target) as children:
            for child in children:
                if child.name.lower() == ".git":
                    continue
                linked = reparse(Path(child.path))
                kind = "link" if linked else "directory" if child.is_dir(follow_symlinks=False) else "file"
                entries.append({"name": child.name, "path": f"{path}/{child.name}" if path else child.name,
                                "kind": kind, "blocked": linked})
        hidden_count = 0
        if visibility == 'working':
            specs = working_ignore_specs(root, target)
            filtered = [entry for entry in entries if not working_hidden(root, entry, specs)]
            hidden_count = len(entries) - len(filtered)
            entries = filtered
        priorities = {'src': 0, 'backend': 1} if visibility == 'working' and not path else {}
        entries.sort(key=lambda entry: (entry["kind"] != "directory", priorities.get(entry['name'], 2), entry["name"].casefold(), entry["name"]))
        more = offset + limit < len(entries)
        return {"root": str(root), "path": path, "entries": entries[offset:offset + limit], "total": len(entries),
                "hasMore": more, "nextOffset": offset + limit if more else None,
                "available": True, "observedAt": datetime.now(UTC).isoformat(),
                "visibility": visibility, "hiddenCount": hidden_count}


def create_workspace_router(service):
    router = APIRouter(prefix="/api/workspace")
    sources = WorkspaceSources(service)

    @router.post("/open-file")
    def open_file(payload: dict):
        return sources.open_file(payload)

    @router.get("/tree")
    def tree(project: str, workspace: str, path: str = "", offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500), visibility: Literal['all', 'working'] = 'all'):
        return sources.tree(project, workspace, path, offset, limit, visibility)

    from .workspace_documents import WorkspaceDocuments

    documents = WorkspaceDocuments(service, sources)

    @router.get("/document")
    def document(project: str, workspace: str, path: str = ""):
        return documents.read(project, workspace, path)

    @router.post("/document")
    def save_document(payload: dict):
        return documents.save(payload)

    return router
