"""Data dílny srdce (docs/brain-heart.md §3b): velký kontext pro `ctx <name>`, deterministicky a bez modelu.

`context` vrátí seznam položek jednoho druhu: `tasks` (všechny úkoly s tělem a reportem), `tickets` (všechny lístky
pracovního prostoru), `journal` (celý deník dávek), `messages` (zprávy člověka v prostoru), `rules` a `decisions`
(paměť Desktop v3) a `tree` (soubory zdroje `{path, size, mtime}` bez `node_modules`, `.git` a výstupu buildu,
nejvýš `TREE_CAP`). Nástroj srdce je zapíše do `brain/dilna/data/<name>.json`; do okna modelu nejdou.
"""
import os
import stat

from backend.brain_opora.determinism import brain_files
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.project.workspace.workspace_sources import WorkspaceSources
from database.repositories.gate_tickets import GateTicketStore
from database.repositories.heart_tasks import HeartTaskStore

NAMES = ("tasks", "tickets", "journal", "messages", "rules", "decisions", "tree")
ROWS = 10_000  # strop řádků z databáze; dílna je pro velký kontext, ne pro nekonečný
TREE_CAP = 20_000
SKIP = {"node_modules", ".git", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".turbo", ".cache",
        "coverage", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache", "target"}


def _rows(service, project, workspace, name):
    with service.reading(project):
        db = service.db_for(project)
        if name == "tasks":
            return HeartTaskStore(db, project).list(workspace, limit=ROWS)
        return GateTicketStore(db, project).all(workspace, ROWS)


def _memory(service, project, workspace, name):
    store = getattr(service, "desktop_v3_state", None) or DesktopV3State(service)
    items = store.read(project, workspace)["state"].get(name) or []
    return [item for item in items if isinstance(item, dict)]


def _hidden(path):
    """Odkaz nebo junction se neprochází (zdroj nesmí vést ven)."""
    try:
        info = os.lstat(path)
    except OSError:
        return True
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0)
                                              & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def tree(root, cap=TREE_CAP):
    """Soubory pod `root` seřazené podle cesty `{path, size, mtime}`; bez `SKIP`, odkazů a nad `cap` položek."""
    found = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP and not _hidden(os.path.join(folder, name)))
        for name in sorted(files):
            path = os.path.join(folder, name)
            try:
                info = os.lstat(path)
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            found.append({"path": os.path.relpath(path, root).replace("\\", "/"), "size": info.st_size,
                          "mtime": int(info.st_mtime)})
            if len(found) >= cap:
                return sorted(found, key=lambda item: item["path"])
    return sorted(found, key=lambda item: item["path"])


def _source(service, project, workspace):
    try:
        return WorkspaceSources(service).root(project, workspace)
    except Exception:  # noqa: BLE001 - bez zdroje je strom prázdný, nikdy chyba
        return None


def context(service, project, workspace, name):
    """Položky jednoho druhu dílny. Neznámý druh 422 `invalid_payload`, neznámý projekt 404."""
    if name not in NAMES:
        raise invalid(f"Neznámý druh kontextu {name!r}.", "Druhy: " + ", ".join(NAMES) + ".")
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    if name in ("tasks", "tickets"):
        return _rows(service, project, workspace, name)
    if name in ("rules", "decisions"):
        return _memory(service, project, workspace, name)
    if name == "tree":
        root = _source(service, project, workspace)
        return tree(root) if root else []
    brain = brain_files.brain_dir(service, project)
    return brain_files.journal(brain, None) if name == "journal" else brain_files.messages(brain, workspace, None)
