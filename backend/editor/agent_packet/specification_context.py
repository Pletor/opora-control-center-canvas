"""Canonical, local specification captured independently of agent work and layout.

The digest binds an assignment, not an implementation: no Git HEAD, execution status,
agent scratchpad, result history or network-recalled memory participates. References
remain references; capturing a specification never claims their contents were read.
"""

import copy

from backend.canvas.areas import area_of
from backend.canvas.graph import digest, valid_id
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.desktop_v3_packets import ancestor_ids, memory_for, redact_deep

SCHEMA = "opora.specification-context/1"
PRESENTATION = {"x", "y", "size", "color", "blockOffsets"}


def _node(node, nodes):
    result = {key: value for key, value in node.items() if key not in PRESENTATION | {"card"}}
    # Layer affects the responsibility; suggested model, due date and work status do not.
    if (node.get("card") or {}).get("layer"):
        result["layer"] = node["card"]["layer"]
    area = area_of(node, nodes)
    result["areaId"] = area["id"] if area else None
    return result


def _instructions(node_state):
    """Keep task content, discard check marks and agent-reported progress."""
    result = {key: copy.deepcopy(node_state.get(key, []))
              for key in ("criteria", "steps", "actions", "rules", "blocks", "materials")}
    for criterion in result["criteria"]:
        criterion.pop("checked", None)
    for step in result["steps"]:
        step.pop("done", None)
    for block in result["blocks"]:
        block["state"].pop("status", None)
        for todo in block.get("todos", []):
            todo.pop("done", None)
    return result


def _navigation(nodes):
    """Page order is specification; ordinary card order and coordinates are layout."""
    by_id = {node["id"]: node for node in nodes}
    domains = {}
    for node in nodes:
        if (node.get("site") or {}).get("kind") != "page":
            continue
        parent_page = None
        cursor = by_id.get(node["parentId"])
        while cursor is not None:
            kind = (cursor.get("site") or {}).get("kind")
            if kind == "application":
                domains.setdefault(cursor["id"], []).append({
                    "nodeId": node["id"], "parentPageId": parent_page,
                })
                break
            if kind == "page" and parent_page is None:
                parent_page = cursor["id"]
            cursor = by_id.get(cursor["parentId"])
    return [{"domainId": identifier, "pages": domains[identifier]}
            for identifier in sorted(domains)]


def capture_specification(canvas, project, workspace, node_id):
    """Return the version and frozen canonical data under the existing reentrant locks."""
    if not all(valid_id(value) for value in (project, workspace, node_id)):
        raise ValueError("Neplatný rozsah specifikace.")
    with canvas.graph_lock, canvas.lock:
        view = canvas.view(project, workspace)
        graph = view["graph"]
        by_id = {node["id"]: node for node in graph["nodes"]}
        if node_id not in by_id:
            raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
        lineage = [node_id, *ancestor_ids(by_id, node_id)]
        related = set(lineage)
        # A sector handoff includes the whole fractal subtree, not only its first layer.
        descendants, pending = {node_id}, [node_id]
        while pending:
            parent_id = pending.pop()
            for child in graph["nodes"]:
                if child["parentId"] == parent_id and child["id"] not in descendants:
                    descendants.add(child["id"])
                    pending.append(child["id"])
        related.update(descendants)
        for edge in graph["edges"]:
            if descendants.intersection((edge["source"], edge["target"])):
                related.update((edge["source"], edge["target"]))
        config = canvas.project_hub.settings(project)
        stored = DesktopV3State(canvas).read(project, workspace)
        context_ids = [node_id, *sorted(related - {node_id})]
        paths = [(by_id[identifier].get("sourceRef") or {}).get("path", "") for identifier in context_ids]
        memory = memory_for(stored, context_ids, paths, "")
        cards = []
        for identifier in sorted(related):
            spec = canvas.node_spec(project, workspace, identifier)
            text = canvas.texts.read((project, workspace, identifier)) if not view["readOnly"] else {}
            cards.append({
                "nodeId": identifier,
                "spec": {"revision": spec["revision"], "fields": spec["fields"],
                         "available": spec.get("available", True)},
                "content": {"revision": text.get("revision", 0), "text": text.get("text", ""),
                            "available": not view["readOnly"]},
                "instructions": _instructions(stored["state"]["nodes"].get(identifier, {})),
            })
        drawings = []
        for layer in ["", *sorted(related)]:
            drawing = canvas.drawing(project, workspace, layer)
            drawings.append({
                "layer": layer, "revision": drawing["revision"],
                "available": drawing.get("available", True),
                # Geometry inside a design drawing is task content, unlike card layout.
                "scene": drawing["scene"],
                "imageContentsIncluded": False,
            })
        specification = redact_deep({
            "schema": SCHEMA,
            "scope": {"project": project, "workspace": workspace, "nodeId": node_id},
            "project": {
                "id": project, "name": config.get("project", {}).get("name", ""),
                "revision": config.get("revision", 0), "settings": config.get("settings", {}),
            },
            "ancestors": list(reversed(lineage[1:])),
            "graph": {
                "nodes": [_node(node, graph["nodes"]) for node in sorted(graph["nodes"], key=lambda n: n["id"])],
                "edges": sorted(graph["edges"], key=lambda edge: edge["id"]),
            },
            # Persisted graph array order drives the domain map's page navigation.
            # Omit the projection for legacy graphs without pages.
            **({"navigation": _navigation(graph["nodes"])}
               if any((node.get("site") or {}).get("kind") == "page" for node in graph["nodes"]) else {}),
            "rules": memory["rules"], "settings": memory["settings"],
            # Agent proposals are work output until a human accepts them as specification.
            "decisions": [item for item in memory["decisions"] if item.get("by") != "agent"],
            "cards": cards,
            "drawings": drawings,
            "referencesPolicy": "reference-only; external content is not captured or verified",
        })
        return {"contextVersion": digest(specification), "specification": specification}
