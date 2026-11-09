"""Canonical, local specification captured independently of agent work and layout.

The digest binds an assignment, not an implementation: no Git HEAD, execution status,
agent scratchpad, result history or network-recalled memory participates. References
remain references; capturing a specification never claims their contents were read.
"""

import copy

from backend.canvas.areas import area_of
from backend.canvas.graph import digest, valid_id
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.assignment_scope import scoped_specification, without_journeys
from backend.editor.agent_packet.desktop_v3_packets import ancestor_ids, memory_for, redact_deep

SCHEMA = "opora.specification-context/1"
PRESENTATION = {"x", "y", "size", "color", "blockOffsets"}


def _node(node, nodes):
    result = {key: value for key, value in without_journeys(node).items() if key not in PRESENTATION | {"card"}}
    # Layer affects the responsibility; suggested model, due date and work status do not.
    if (node.get("card") or {}).get("layer"):
        result["layer"] = node["card"]["layer"]
    # Technology, states and the realized page section describe what to build (architektura-pro-agenty §3.3);
    # `effort` is the heart's difficulty of the card that the office turns into worker model/effort
    # (brain-heart-orchestrator §12). Absent keys stay absent so the digest of a card without them does not change.
    for key in ("tech", "states", "section", "effort"):
        if key in (node.get("card") or {}):
            result[key] = node["card"][key]
    area = area_of(node, nodes)
    result["areaId"] = area["id"] if area else None
    return result


def _instructions(node_state):
    """Keep task content, discard check marks and agent-reported progress."""
    result = {key: copy.deepcopy(node_state.get(key, []))
              for key in ("actions", "rules", "blocks", "materials")}
    if "downloadsUrl" in node_state:
        result["downloadsUrl"] = node_state["downloadsUrl"]
    # Starší číslo kola karty je součást zadání (kola jsou zrušená, klíč se nemění; card_round_legacy.py).
    if "round" in node_state:
        result["round"] = node_state["round"]["number"]
    for block in result["blocks"]:
        block["state"].pop("status", None)
        block["state"].pop("note", None)
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
                # Popisek v menu jen když ho člověk nastavil; bez něj se položka nemění (stejný digest).
                domains.setdefault(cursor["id"], []).append({
                    "nodeId": node["id"], "parentPageId": parent_page,
                    **({"navLabel": node["site"]["navLabel"]} if "navLabel" in node["site"] else {}),
                })
                break
            if kind == "page" and parent_page is None:
                parent_page = cursor["id"]
            cursor = by_id.get(cursor["parentId"])
    return [{"domainId": identifier, "pages": domains[identifier]}
            for identifier in sorted(domains)]


def _graph_part(canvas, project, workspace, view):
    """Redigovaná projekce celého grafu (a navigace stránek) je pro všechny karty stejná: počítá se
    jednou na digest grafu (karta P3) a je sdílená, jen ke čtení. Redakce je po hodnotách, takže
    výsledek je totožný s redakcí celé specifikace najednou."""
    key = ("spec-graph", project, workspace)
    cached = canvas.read_cache.get(key, view["digest"])
    if cached is not None:
        return cached
    graph = view["graph"]
    part = {"graph": redact_deep({
        "nodes": [_node(node, graph["nodes"]) for node in sorted(graph["nodes"], key=lambda n: n["id"])],
        "edges": sorted(graph["edges"], key=lambda edge: edge["id"]),
    })}
    # Persisted graph array order drives the domain map's page navigation.
    # Omit the projection for legacy graphs without pages.
    if any((node.get("site") or {}).get("kind") == "page" for node in graph["nodes"]):
        part["navigation"] = redact_deep(_navigation(graph["nodes"]))
    return canvas.read_cache.put(key, view["digest"], part)


def _card(canvas, project, workspace, view, stored, identifier):
    spec = canvas.node_spec(project, workspace, identifier)
    text = canvas.texts.read((project, canvas.document_workspace(project, workspace, identifier), identifier)) if not view["readOnly"] else {}
    return redact_deep({
        "nodeId": identifier,
        "spec": {"revision": spec["revision"], "fields": spec["fields"],
                 "available": spec.get("available", True)},
        "content": {"revision": text.get("revision", 0), "text": text.get("text", ""),
                    "available": not view["readOnly"]},
        "instructions": _instructions(stored["state"]["nodes"].get(identifier, {})),
    })


def _drawing(canvas, project, workspace, layer):
    drawing = canvas.drawing(project, workspace, layer)
    return redact_deep({
        "layer": layer, "revision": drawing["revision"],
        "available": drawing.get("available", True),
        # Geometry inside a design drawing is task content, unlike card layout.
        "scene": drawing["scene"],
        "imageContentsIncluded": False,
    })


def capture_specification(canvas, project, workspace, node_id):
    """Return the version and frozen canonical data under the existing reentrant locks."""
    if not all(valid_id(value) for value in (project, workspace, node_id)):
        raise ValueError("Neplatný rozsah specifikace.")
    # Each related card's spec and drawing reads the view again; under the project lock that rebuilt it per card.
    with canvas.reading(project), canvas.steady_reads(project):
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
            if (descendants.intersection((edge["source"], edge["target"]))
                    or edge.get("relation") == "requires" and edge["source"] in lineage):
                related.update((edge["source"], edge["target"]))
        config = canvas.project_hub.settings(project)
        stored = DesktopV3State(canvas).read(project, workspace)
        context_ids = [node_id, *sorted(related - {node_id})]
        paths = [(by_id[identifier].get("sourceRef") or {}).get("path", "") for identifier in context_ids]
        memory = memory_for(stored, context_ids, paths, "")
        upstream_ids = {edge["source"] for edge in graph["edges"]
                        if edge["target"] in descendants and edge["source"] not in descendants
                        and edge.get("port") != "flow"}
        # Redaction is per value, so each card and drawing is redacted on its own; a steady block
        # (agent-state over every card) builds each related card and layer once, not once per capture.
        cards = [canvas.steady_value(project, ("spec-card", workspace, identifier),
                                     lambda key=identifier: _card(canvas, project, workspace, view, stored, key))
                 for identifier in sorted(related)]
        drawings = [canvas.steady_value(project, ("spec-drawing", workspace, layer),
                                        lambda key=layer: _drawing(canvas, project, workspace, key))
                    for layer in ["", *sorted(related)]]
        shared = _graph_part(canvas, project, workspace, view)
        head = redact_deep({
            "schema": SCHEMA,
            "scope": {"project": project, "workspace": workspace, "nodeId": node_id},
            "project": {
                "id": project, "name": config.get("project", {}).get("name", ""),
                "revision": config.get("revision", 0), "settings": config.get("settings", {}),
            },
            "ancestors": list(reversed(lineage[1:])),
        })
        specification = {**head, **shared, **redact_deep({
            "rules": memory["rules"], "settings": memory["settings"],
            # Own agent proposals remain output; incoming decisions are assumptions of this task.
            "decisions": [item for item in memory["decisions"]
                          if item.get("by") != "agent" or item.get("nodeId") in upstream_ids],
            "referencesPolicy": "reference-only; external content is not captured or verified",
        }), "cards": cards, "drawings": drawings}
        specification = scoped_specification(specification)
        from backend.canvas.storyboard_evidence import collect as storyboard_inputs
        storyboards = [item for item in storyboard_inputs(canvas, project, workspace, related, graph) if item["revision"] > 0]
        if storyboards:
            specification["storyboards"] = storyboards
        return {"contextVersion": digest(specification), "specification": specification}
