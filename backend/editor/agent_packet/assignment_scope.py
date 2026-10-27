"""Task-local comparison of current and legacy immutable assignment snapshots."""

import json

from backend.canvas.graph import digest


def without_journeys(node):
    """Uzel bez cest zákazníka aplikace (`site.journeys`): cesty nejsou zadání karty, karta je dostane odvozené
    v `node-brief.architecture` (architektura-pro-agenty §4), takže přidání cesty `contextVersion` nemění."""
    site = node.get("site")
    if isinstance(site, dict) and "journeys" in site:
        return {**node, "site": {key: value for key, value in site.items() if key != "journeys"}}
    return node


def scoped_specification(specification):
    """Project the graph using the captured context, never today's graph or card content.

    Old records included every graph node. Keep those records immutable; use the same
    projection on both sides for comparison. Ordered navigation remains significant.
    Customer journeys of an application are not part of a card's assignment (`without_journeys`);
    records captured while they still were compare equal once they are dropped on both sides.
    """
    if not isinstance(specification, dict) or "cards" not in specification:
        return specification
    graph = specification["graph"]
    related = {card["nodeId"] for card in specification["cards"]}
    areas = {node.get("areaId") for node in graph["nodes"] if node["id"] in related}
    flows = [edge for edge in graph["edges"] if edge.get("port") == "flow"
             and areas.intersection((edge["source"], edge["target"]))]
    endpoints = {identifier for edge in flows for identifier in (edge["source"], edge["target"])}
    flow_ids = {edge["id"] for edge in flows}
    return {**specification, "graph": {
        "nodes": sorted((without_journeys(node) for node in graph["nodes"] if node["id"] in related | areas | endpoints),
                        key=lambda node: node["id"]),
        "edges": sorted((edge for edge in graph["edges"]
                         if edge["id"] in flow_ids or
                         (edge["source"] in related and edge["target"] in related)),
                        key=lambda edge: edge["id"]),
    }}


def same_assignment(original, current):
    before = original.get("specification")
    return (original.get("contextVersion") == current["contextVersion"]
            or (before is not None and digest(scoped_specification(before))
                == digest(scoped_specification(current["specification"]))))


def compatible_capture(canvas, project, workspace, node, version, current):
    """Accept a legacy version only with a server-stored, same-scope unchanged baseline.

    Return the original capture so result provenance still matches its original digest.
    Unknown versions and actual task changes fail closed; state CAS remains independent.
    """
    if version == current["contextVersion"]:
        return current
    for table in ("assignment_snapshots", "agent_result_records"):
        rows = canvas.db_for(project).execute(
            f"SELECT record FROM {table} WHERE project_id=? AND workspace_id=? AND node_id=?",
            (project, workspace, node),
        )
        for row in rows:
            record = json.loads(row["record"])
            if (record.get("binding") == "bound" and record.get("contextVersion") == version
                    and record.get("specification") is not None
                    and digest(record["specification"]) == version
                    and same_assignment(record, current)):
                return {"contextVersion": version, "specification": record["specification"]}
    return None
