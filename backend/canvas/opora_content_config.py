"""Pure configuration merge and validation for accepted card-content changes."""
from copy import deepcopy

from backend.canvas.graph import validate_graph
from backend.editor.agent_memory.desktop_v3_state import (
    check_node_branches,
    default_done,
    validate_state,
)

CONFIG_FIELDS = ("actions", "rules", "blocks", "materials", "downloadsUrl")


def _nodes(graph):
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise TypeError("Content scope requires a validated graph.")
    nodes = {item.get("id"): item for item in graph["nodes"] if isinstance(item, dict)}
    if len(nodes) != len(graph["nodes"]) or any(not isinstance(key, str) for key in nodes):
        raise ValueError("Content graph identities are invalid.")
    return nodes


def _empty_node():
    return {"phase": "discover", "criteria": [], "steps": [], "actions": [], "rules": []}


def _content_blocks(proposed, old):
    old_by_id = {item["id"]: item for item in old}
    result = deepcopy(proposed)
    for block in result:
        previous = old_by_id.get(block["id"])
        old_state = previous.get("state", {}) if previous else {}
        block_state = block.setdefault("state", {})
        block_state["status"] = old_state.get("status", "open")
        block_state["note"] = old_state.get("note", "")
        old_todos = {item["id"]: item for item in previous.get("todos", [])} if previous else {}
        for todo in block.get("todos", []):
            todo["done"] = old_todos.get(todo["id"], {}).get("done", False)
    return result


def preview_config_changes(source_state, changes, graph):
    """Pure config merge/validation shared by proposal preview and transactional writes."""
    nodes = _nodes(graph)
    validate_graph(graph)
    state = deepcopy(source_state)
    validate_state(state)
    grouped = {}
    for change in changes:
        if (not isinstance(change, dict) or change.get("kind") != "config"
                or change.get("target") not in nodes or change.get("field") not in CONFIG_FIELDS):
            raise ValueError("Unsupported config preview change.")
        grouped.setdefault(change["target"], {})[change["field"]] = deepcopy(change.get("value"))
    for target, fields in grouped.items():
        node = state.setdefault("nodes", {}).setdefault(target, _empty_node())
        node.setdefault("actions", [])
        node.setdefault("rules", [])
        if "blocks" in fields:
            fields["blocks"] = _content_blocks(fields["blocks"], node.get("blocks", []))
            if node.get("done", default_done())["confirmed"] and fields["blocks"] != node.get("blocks", []):
                raise ValueError("Closed card blocks and ports are read-only; reopen the card first.")
        for field, value in fields.items():
            if field == "downloadsUrl" and value is None:
                node.pop(field, None)
            else:
                node[field] = value
    validate_state(state)
    check_node_branches(state, set(nodes))
    for edge in graph.get("edges", []):
        if edge.get("port") != "block":
            continue
        source = state.get("nodes", {}).get(edge["source"], {})
        block = next((item for item in source.get("blocks", [])
                      if item["id"] == edge.get("sourceBlockId")), None)
        if block is None or not any(port["id"] == edge.get("sourcePortId")
                                    for port in block.get("ports", [])):
            raise ValueError("Card config would orphan a graph block-port edge.")
    return state
