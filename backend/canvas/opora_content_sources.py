"""Native readers and transactional writers for accepted card content proposals."""
import json
from copy import deepcopy
from datetime import UTC, datetime

from backend.canvas.authority import acts_as_human
from backend.canvas.graph import validate_graph
from backend.canvas.opora_content_config import CONFIG_FIELDS, preview_config_changes
from backend.canvas.opora_content_source_bounds import preflight_source_bytes
from backend.editor.agent_memory.desktop_v3_state import default_state, validate_state
from backend.editor.agent_packet.specification_context import _instructions
from backend.editor.node.drawing_transaction import (
    save_in_transaction as save_drawing_in_transaction,
)
from backend.editor.node.drawings import DrawingStore
from backend.editor.node.node_text import NodeTextStore

MAX_ENTRIES = 16384
MAX_BYTES = 8 * 1024 * 1024


def normalize_config(node_state):
    """Return task configuration using the same progress-stripping rule as `_instructions`."""
    value = _instructions(deepcopy(node_state or {}))
    value.pop("round", None)
    return {field: value.get(field) for field in CONFIG_FIELDS}


NATIVE_EMPTY = (("text", "text", ""), ("drawing", "scene", {"elements": []}), ("storyboard", "storyboard", None))


def native_empty(node, workspace):
    """Nativní prázdný obsah karty, kterou nikdo nepsal: prázdný text, prázdná kresba, žádný storyboard."""
    return {(kind, node, field): {"kind": kind, "target": node, "field": field, "ownerWorkspace": workspace,
                                  "revision": 0, "value": deepcopy(value)} for kind, field, value in NATIVE_EMPTY}


def _nodes(graph):
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise TypeError("Content scope requires a validated graph.")
    nodes = {item.get("id"): item for item in graph["nodes"] if isinstance(item, dict)}
    if len(nodes) != len(graph["nodes"]) or any(not isinstance(key, str) for key in nodes):
        raise ValueError("Content graph identities are invalid.")
    return nodes


def _owner(canvas, project, workspace, kind, target, nodes):
    if kind == "drawing":
        if target and target not in nodes:
            raise ValueError("Drawing layer is outside the current graph.")
        return workspace
    if target not in nodes:
        raise ValueError("Content target is outside the current graph.")
    return canvas.document_workspace(project, workspace, target) if kind == "text" else workspace


def _round(state, target):
    value = state.get("nodes", {}).get(target, {}).get("round")
    return value.get("number") if isinstance(value, dict) else None


def _read_entry(canvas, project, workspace, kind, target, field, nodes, owners, state):
    if kind == "text" and field == "text":
        owner = owners.get((kind, target))
        if owner is None:
            owner = _owner(canvas, project, workspace, kind, target, nodes)
        current = NodeTextStore(canvas).read((project, owner, target))
        return {"kind": kind, "target": target, "field": field, "ownerWorkspace": owner,
                "value": current["text"], "revision": current["revision"]}
    if kind == "drawing" and field == "scene":
        owner = owners.get((kind, target), workspace)
        if target and target not in nodes:
            raise ValueError("Drawing layer is outside the current graph.")
        current = DrawingStore(canvas).read((project, owner, target))
        return {"kind": kind, "target": target, "field": field, "ownerWorkspace": owner,
                "value": current["scene"], "revision": current["revision"]}
    if kind == "storyboard" and field == "storyboard":
        if target not in nodes or nodes[target]["kind"] not in ("node", "sector"):
            raise ValueError("Storyboard target is outside the current graph.")
        from backend.editor.storyboard.storyboard import StoryboardService
        current = StoryboardService(canvas).source(project, workspace, target)
        return {"kind": kind, "target": target, "field": field, "ownerWorkspace": workspace,
                "value": current["storyboard"], "revision": current["revision"]}
    if kind == "config" and field in CONFIG_FIELDS:
        owner = owners.get((kind, target))
        if owner is None:
            owner = workspace
        if target not in nodes:
            raise ValueError("Content target is outside the current graph.")
        config = normalize_config(state.get("nodes", {}).get(target, {}))
        return {"kind": kind, "target": target, "field": field, "ownerWorkspace": owner,
                "value": config[field]}
    raise ValueError("Unsupported content source kind, target or field.")


def read_entry(canvas, project, workspace, kind, target, field):
    view = canvas.view(project, workspace)
    if workspace in {"main", "architecture"} or view["readOnly"]:
        raise ValueError("Content source workspace is read-only.")
    nodes = _nodes(view["graph"])
    state = _state(canvas, canvas.db_for(project), project, workspace)[1]
    owners = {}
    if kind == "text" and target in nodes:
        owners[(kind, target)] = canvas.document_workspace(project, workspace, target)
    return _read_entry(canvas, project, workspace, kind, target, field, nodes, owners, state)


def before_precondition(canvas, project, workspace, kind, target, field):
    view = canvas.view(project, workspace)
    if workspace in {"main", "architecture"} or view["readOnly"]:
        raise ValueError("Content source workspace is read-only.")
    nodes = _nodes(view["graph"])
    owners = {}
    if kind == "text" and target in nodes:
        owners[(kind, target)] = canvas.document_workspace(project, workspace, target)
    state = _state(canvas, canvas.db_for(project), project, workspace)[1]
    entry = _read_entry(canvas, project, workspace, kind, target, field, nodes, owners, state)
    result = {"ownerWorkspace": entry["ownerWorkspace"], "observedOwner": entry["ownerWorkspace"]}
    if "revision" in entry:
        result["observedRevision"] = entry["revision"]
    result["observedRound"] = _round(state, target)
    return {**entry, **result}


def capture_content(canvas, project, workspace, graph):
    """Capture complete current text/drawing/config entries plus source preconditions."""
    nodes = _nodes(graph)
    view = canvas.view(project, workspace)
    if workspace in {"main", "architecture"} or view["readOnly"] or view["graph"] != graph:
        raise ValueError("Content source workspace or graph is stale/read-only.")
    state = _state(canvas, canvas.db_for(project), project, workspace)[1]
    owners = {("text", target): canvas.document_workspace(project, workspace, target) for target in nodes}
    node_ids = sorted(nodes)
    db = canvas.db_for(project)
    imported = {row[0] for row in db.execute("SELECT DISTINCT node_id FROM storyboard_revisions WHERE project_id=? AND workspace_id=?", (project, workspace))}
    legacy_bytes = 0
    for identifier in set(node_ids) - imported:
        path = canvas.folder(project).storyboard(workspace, identifier)
        if path.exists():
            legacy_bytes += path.stat().st_size
    if not preflight_source_bytes(db, project, workspace, node_ids, owners, MAX_BYTES, legacy_bytes):
        raise ValueError("Content manifest exceeds the byte limit.")
    entries, observations = [], {}
    for target in sorted(nodes):
        for kind, field in (("text", "text"), ("drawing", "scene"),
                            *((("storyboard", "storyboard"),) if nodes[target]["kind"] in ("node", "sector") else ()),
                            *(('config', field) for field in CONFIG_FIELDS)):
            entry = _read_entry(canvas, project, workspace, kind, target, field, nodes, owners, state)
            entries.append(entry)
            observations[(kind, target, field)] = {**entry, "round": _round(state, target)}
    root = _read_entry(canvas, project, workspace, "drawing", "", "scene", nodes, owners, state)
    entries.append(root)
    observations[("drawing", "", "scene")] = {**root, "round": None}
    entries.sort(key=lambda item: (item["kind"], item["target"], item["field"]))
    if len(entries) > MAX_ENTRIES:
        raise ValueError("Content manifest exceeds the entry limit.")
    size = len(json.dumps(entries, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))
    if size > MAX_BYTES:
        raise ValueError("Content manifest exceeds the byte limit.")
    return entries, observations


def _state(canvas, db, project, workspace):
    row = db.execute("SELECT revision,state FROM desktop_v3_state WHERE project_id=? AND workspace_id=?",
                     (project, workspace)).fetchone()
    if row is None:
        return 0, default_state()
    state = json.loads(row["state"])
    validate_state(state)
    return row["revision"], state


def write_changes_in_transaction(canvas, db, project, workspace, changes, actor, graph):
    """Apply accepted native source changes; the caller owns BEGIN/COMMIT and locks."""
    if not acts_as_human(actor) or not db.in_transaction:
        raise ValueError("Content writes require a human and the caller's SQL transaction.")
    nodes = _nodes(graph)
    validate_graph(graph)
    view = canvas.view(project, workspace)
    if workspace in {"main", "architecture"} or view["readOnly"] or view["graph"] != graph:
        raise ValueError("Content source workspace or graph is stale/read-only.")
    if not isinstance(changes, list) or len(changes) > 128:
        raise ValueError("Content changes must be a bounded list.")
    seen, configs = set(), {}
    state_revision, state = _state(canvas, db, project, workspace)
    validate_state(state)
    for change in changes:
        if not isinstance(change, dict):
            raise TypeError("Invalid content change.")
        kind, target, field = change.get("kind"), change.get("target"), change.get("field")
        key = (kind, target, field)
        if key in seen:
            raise ValueError("Duplicate content change.")
        seen.add(key)
        current = _read_entry(canvas, project, workspace, kind, target, field, nodes, {}, state)
        expected_revision = change.get("observedRevision")
        if "revision" in current and expected_revision != current["revision"]:
            raise ValueError("Content source revision changed after proposal review.")
        if change.get("observedRound") != _round(state, target):
            raise ValueError("Content source round changed after proposal review.")
        if change.get("observedOwner") != current["ownerWorkspace"] or change.get("before") != current["value"]:
            raise ValueError("Content source changed after proposal review.")
        if kind == "text":
            NodeTextStore(canvas).save_in_transaction(
                (project, current["ownerWorkspace"], target), expected_revision, change.get("value"))
        elif kind == "drawing":
            save_drawing_in_transaction(canvas, db, (project, workspace, target), expected_revision,
                                        change.get("value"), datetime.now(UTC).isoformat())
        elif kind == "storyboard":
            from backend.editor.storyboard.storyboard import StoryboardService
            StoryboardService(canvas).save_in_transaction(project, workspace, target, expected_revision, change.get("value"))
        elif kind == "config":
            fields = configs.setdefault(target, {})
            fields[field] = deepcopy(change.get("value"))
        else:
            raise ValueError("Unsupported content source kind.")
    if configs:
        state = preview_config_changes(state, [
            {"kind": "config", "target": target, "field": field, "value": value}
            for target, fields in configs.items() for field, value in fields.items()
        ], graph)
        db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
                   (project, workspace, state_revision + 1,
                    json.dumps(state, ensure_ascii=False, allow_nan=False), datetime.now(UTC).isoformat()))
