"""Skutečný pracovní strom; nikdy nečte obsah ani nespouští projektový kód."""

import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Query

RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.IGNORECASE)


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

    def tree(self, project, workspace, path="", offset=0, limit=200):
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
        entries.sort(key=lambda entry: (entry["kind"] != "directory", entry["name"].casefold(), entry["name"]))
        more = offset + limit < len(entries)
        return {"root": str(root), "path": path, "entries": entries[offset:offset + limit], "total": len(entries),
                "hasMore": more, "nextOffset": offset + limit if more else None,
                "available": True, "observedAt": datetime.now(UTC).isoformat()}


def create_workspace_router(service):
    router = APIRouter(prefix="/api/workspace")
    sources = WorkspaceSources(service)

    @router.get("/tree")
    def tree(project: str, workspace: str, path: str = "", offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500)):
        return sources.tree(project, workspace, path, offset, limit)

    from .workspace_documents import WorkspaceDocuments

    documents = WorkspaceDocuments(service, sources)

    @router.get("/document")
    def document(project: str, workspace: str, path: str = ""):
        return documents.read(project, workspace, path)

    @router.post("/document")
    def save_document(payload: dict):
        return documents.save(payload)

    return router
