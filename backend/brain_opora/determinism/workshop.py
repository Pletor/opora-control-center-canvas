"""Data dílny srdce (docs/brain-heart.md §3b): velký kontext pro `ctx <name>`, deterministicky a bez modelu.

`context` vrátí seznam položek jednoho druhu: `tasks` (všechny úkoly s tělem a reportem), `tickets` (všechny lístky
pracovního prostoru), `journal` (celý deník dávek), `messages` (zprávy člověka v prostoru), `rules` a `decisions`
(paměť Desktop v3) a `tree` (soubory zdroje `{path, size, mtime}` bez `node_modules`, `.git` a výstupu buildu,
nejvýš `TREE_CAP`). Nástroj srdce je zapíše do `brain/dilna/data/<name>.json`; do okna modelu nejdou.
`plan-of` (docs/brain-heart-orchestrator.md §9 O7) je plán jiného projektu (uzly plátna se zadáním a vazbami) jako data,
např. k převodu plánu lokální Ample do Ample git: výchozí je celý plán zhuštěně (`PLAN_OF_SHORT` znaků na text, kroky jen
titulky), `node` dá plné zadání jednoho podstromu; strop `PLAN_OF_BYTES` a co se nevešlo, jmenuje poslední položka.
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
PLAN_OF_SHORT = 200  # zhuštěný plán: purpose, goal, acceptance a titulek kroku
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


def _clip(value, limit=PLAN_OF_TEXT):
    text = value if isinstance(value, str) else ""
    return text if len(text) <= limit else text[:limit] + "…"


def _steps(fields):
    return [step for step in (fields.get("steps") or []) if isinstance(step, dict)]


def _spec(fields):
    steps = [{key: step.get(key) for key in ("id", "order", "title", "acceptance", "dependsOn") if key in step}
             for step in _steps(fields)][:PLAN_OF_STEPS]
    return {"goal": _clip(fields.get("goal")), "non_goals": _clip(fields.get("non_goals")),
            "acceptance": _clip(fields.get("acceptance")), "steps": steps}


def _brief(fields):
    """Zhuštěné zadání: cíl a přijetí do `PLAN_OF_SHORT` znaků, kroky jen titulky (všechny)."""
    return {"goal": _clip(fields.get("goal"), PLAN_OF_SHORT), "acceptance": _clip(fields.get("acceptance"), PLAN_OF_SHORT),
            "steps": [_clip(step.get("title"), PLAN_OF_SHORT) for step in _steps(fields)]}


def _home(service, project):
    """Výchozí prostor cizího plánu: `main` u git projektu, jinak `draft`."""
    try:
        kind = service.project_hub.settings(project)["project"]["sourceKind"]
    except Exception:  # noqa: BLE001 - pseudo-projekt draft a nečitelné nastavení = lokální plán
        return "draft"
    return "main" if kind == "git" else "draft"


def plan_of(service, project, workspace=None, node=None):
    """Plán projektu `project` jako data v pořadí grafu.

    Výchozí je celý plán zhuštěně, ať se vejde i 150–300 karet: `{id, kind, name, path (jména předků › …), parent,
    sector, architecture, site?, purpose, goal, acceptance (do `PLAN_OF_SHORT` znaků), steps [titulky], next[]}`.
    `node` dá plné zadání jen toho uzlu a jeho podstromu: `{…, purpose, spec{goal, non_goals, acceptance, steps[{id,
    order, title, acceptance, dependsOn}]}}`. Nad `PLAN_OF_BYTES` JSONu je poslední položka `{truncated: true, total,
    shown, cut: [{id, name}], hint}` a jmenuje každý vynechaný uzel. Neznámý projekt, prostor nebo uzel je 404."""
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    workspace = workspace or _home(service, project)
    try:
        graph = service.view(project, workspace)["graph"]
    except (ValueError, KeyError) as error:
        raise GateError(404, "workspace_not_found", f"Plán prostoru {workspace!r} nejde přečíst: {error}",
                        "Prostory projektu: GET /api/project-workspaces?project=<id>.") from None
    nodes = {item["id"]: item for item in graph["nodes"]}
    owned = {item["id"] for item in split(graph)[0]["nodes"]}
    after = {}
    for edge in graph["edges"]:
        after.setdefault(edge.get("source"), []).append(edge.get("target"))

    def ancestors(item):
        found, parent = [], nodes.get(item.get("parentId"))
        while parent is not None and len(found) < len(nodes):
            found.append(parent)
            parent = nodes.get(parent.get("parentId"))
        return found

    def sector(item):
        return next((parent["id"] for parent in ancestors(item) if parent.get("kind") == "sector"), None)

    chosen = graph["nodes"]
    if node is not None:
        if node not in nodes:
            raise GateError(404, "node_not_found", f"Uzel {node!r} v plánu prostoru {workspace!r} není.",
                            "ID uzlů má zhuštěný plán: ctx plan-of --project <id> (pole id).")
        chosen = [item for item in graph["nodes"]
                  if item["id"] == node or any(parent["id"] == node for parent in ancestors(item))]

    def entry(item, fields):
        base = {"id": item["id"], "kind": item.get("kind"), "name": item.get("name") or "",
                "path": " › ".join(parent.get("name") or "" for parent in reversed(ancestors(item))),
                "parent": item.get("parentId"), "sector": sector(item), "architecture": item["id"] in owned}
        if isinstance(item.get("site"), dict):
            base["site"] = {key: item["site"][key] for key in ("kind", "path") if key in item["site"]}
        if node is None:
            base.update({"purpose": _clip(item.get("purpose"), PLAN_OF_SHORT), **_brief(fields)})
        else:
            base.update({"purpose": _clip(item.get("purpose")), "spec": _spec(fields)})
        base["next"] = after.get(item["id"], [])
        return base

    items, cut, size = [], [], 2
    with service.reading(project):
        for item in chosen:
            if cut:
                cut.append({"id": item["id"], "name": item.get("name") or ""})
                continue
            wid = ARCHITECTURE_WID if item["id"] in owned else workspace
            row = entry(item, service.specs.read((project, wid, item["id"]))["fields"])
            size += len(json.dumps(row, ensure_ascii=False).encode("utf-8")) + 1
            if size > PLAN_OF_BYTES:
                cut.append({"id": item["id"], "name": item.get("name") or ""})
                continue
            items.append(row)
    if cut:
        items.append({"truncated": True, "total": len(chosen), "shown": len(items), "cut": cut,
                      "hint": "Vynechané uzly přečti po podstromech: ctx plan-of --project <id> --node <id>."})
    return items


def context(service, project, workspace, name, of=None, of_workspace=None, of_node=None):
    """Položky jednoho druhu dílny. Neznámý druh 422 `invalid_payload`, neznámý projekt 404.
    `plan-of` čte projekt `of` (a jeho prostor `of_workspace`, podstrom `of_node`), ne projekt srdce."""
    if name not in NAMES:
        raise invalid(f"Neznámý druh kontextu {name!r}.", "Druhy: " + ", ".join(NAMES) + ".")
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    if name == "plan-of":
        if not isinstance(of, str) or not of:
            raise invalid("plan-of potřebuje projekt (?of=<id>).", "python opora_heart.py ctx plan-of --project <id>.")
        return plan_of(service, of, of_workspace or None, of_node or None)
    if name in ("tasks", "tickets"):
        return _rows(service, project, workspace, name)
    if name in ("rules", "decisions"):
        return _memory(service, project, workspace, name)
    if name == "tree":
        root = _source(service, project, workspace)
        return tree(root) if root else []
    brain = brain_files.brain_dir(service, project)
    return brain_files.journal(brain, None) if name == "journal" else brain_files.messages(brain, workspace, None)
