"""Data dílny srdce (docs/brain-heart.md §3b): velký kontext pro `ctx <name>`, deterministicky a bez modelu.

`context` vrátí seznam položek jednoho druhu: `tasks` (všechny úkoly s tělem a reportem), `tickets` (všechny lístky
pracovního prostoru), `journal` (celý deník dávek), `messages` (zprávy člověka v prostoru), `rules` a `decisions`
(paměť Desktop v3) a `tree` (soubory zdroje `{path, size, mtime}` bez `node_modules`, `.git` a výstupu buildu,
nejvýš `TREE_CAP`). Nástroj srdce je zapíše do `brain/dilna/data/<name>.json`; do okna modelu nejdou.
`plan-of` (docs/brain-heart-orchestrator.md §9 O7) je plán jiného projektu (uzly plátna se zadáním a vazbami) jako data,
např. k převodu plánu lokální Ample do Ample git; strop `PLAN_OF_BYTES`.
"""
import json
import os
import stat

from backend.brain_opora.determinism import brain_files
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.architecture_graph import split
from backend.canvas.project_architecture import ARCHITECTURE_WID
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.project.workspace.workspace_sources import WorkspaceSources
from database.repositories.gate_tickets import GateTicketStore
from database.repositories.heart_tasks import HeartTaskStore

NAMES = ("tasks", "tickets", "journal", "messages", "rules", "decisions", "tree", "plan-of")
ROWS = 10_000  # strop řádků z databáze; dílna je pro velký kontext, ne pro nekonečný
TREE_CAP = 20_000
PLAN_OF_BYTES, PLAN_OF_TEXT, PLAN_OF_STEPS = 300_000, 2000, 30  # plán jiného projektu: celý JSON, text pole, kroky
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


def _clip(value):
    text = value if isinstance(value, str) else ""
    return text if len(text) <= PLAN_OF_TEXT else text[:PLAN_OF_TEXT] + "…"


def _spec(fields):
    steps = [{key: step.get(key) for key in ("id", "order", "title", "acceptance", "dependsOn") if key in step}
             for step in (fields.get("steps") or []) if isinstance(step, dict)][:PLAN_OF_STEPS]
    return {"goal": _clip(fields.get("goal")), "non_goals": _clip(fields.get("non_goals")),
            "acceptance": _clip(fields.get("acceptance")), "steps": steps}


def _home(service, project):
    """Výchozí prostor cizího plánu: `main` u git projektu, jinak `draft`."""
    try:
        kind = service.project_hub.settings(project)["project"]["sourceKind"]
    except Exception:  # noqa: BLE001 - pseudo-projekt draft a nečitelné nastavení = lokální plán
        return "draft"
    return "main" if kind == "git" else "draft"


def plan_of(service, project, workspace=None):
    """Plán projektu `project` jako data: uzly plátna `{id, kind, name, purpose, parent, sector, architecture, site?,
    spec{goal, non_goals, acceptance, steps}, next[]}` v pořadí grafu, nejvýš `PLAN_OF_BYTES` JSONu (poslední položka
    `{truncated: true, total}` řekne, že zbytek chybí). Neznámý projekt nebo prostor je 404."""
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    workspace = workspace or _home(service, project)
    try:
        graph = service.view(project, workspace)["graph"]
    except (ValueError, KeyError) as error:
        raise GateError(404, "workspace_not_found", f"Plán prostoru {workspace!r} nejde přečíst: {error}",
                        "Prostory projektu: GET /api/project-workspaces?project=<id>.") from None
    nodes = {node["id"]: node for node in graph["nodes"]}
    owned = {node["id"] for node in split(graph)[0]["nodes"]}
    after = {}
    for edge in graph["edges"]:
        after.setdefault(edge.get("source"), []).append(edge.get("target"))

    def sector(node):
        parent = nodes.get(node.get("parentId"))
        while parent is not None and parent.get("kind") != "sector":
            parent = nodes.get(parent.get("parentId"))
        return parent["id"] if parent else None

    items, size = [], 2
    with service.reading(project):
        for node in graph["nodes"]:
            wid = ARCHITECTURE_WID if node["id"] in owned else workspace
            item = {"id": node["id"], "kind": node.get("kind"), "name": node.get("name") or "",
                    "purpose": _clip(node.get("purpose")), "parent": node.get("parentId"), "sector": sector(node),
                    "architecture": node["id"] in owned,
                    "spec": _spec(service.specs.read((project, wid, node["id"]))["fields"]),
                    "next": after.get(node["id"], [])}
            if isinstance(node.get("site"), dict):
                item["site"] = {key: node["site"][key] for key in ("kind", "path") if key in node["site"]}
            size += len(json.dumps(item, ensure_ascii=False).encode("utf-8")) + 1
            if size > PLAN_OF_BYTES:
                items.append({"truncated": True, "total": len(graph["nodes"]), "shown": len(items)})
                break
            items.append(item)
    return items


def context(service, project, workspace, name, of=None, of_workspace=None):
    """Položky jednoho druhu dílny. Neznámý druh 422 `invalid_payload`, neznámý projekt 404.
    `plan-of` čte projekt `of` (a jeho prostor `of_workspace`), ne projekt srdce."""
    if name not in NAMES:
        raise invalid(f"Neznámý druh kontextu {name!r}.", "Druhy: " + ", ".join(NAMES) + ".")
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    if name == "plan-of":
        if not isinstance(of, str) or not of:
            raise invalid("plan-of potřebuje projekt (?of=<id>).", "python opora_heart.py ctx plan-of --project <id>.")
        return plan_of(service, of, of_workspace or None)
    if name in ("tasks", "tickets"):
        return _rows(service, project, workspace, name)
    if name in ("rules", "decisions"):
        return _memory(service, project, workspace, name)
    if name == "tree":
        root = _source(service, project, workspace)
        return tree(root) if root else []
    brain = brain_files.brain_dir(service, project)
    return brain_files.journal(brain, None) if name == "journal" else brain_files.messages(brain, workspace, None)
