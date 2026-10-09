"""One successor per configured port, on the first transition of its block to met."""

import copy
import json

TEMPLATE_FIELDS = {"name", "purpose", "spec", "text", "checks", "goal_mode"}


def validate_spawn(action):
    if not isinstance(action, dict) or set(action) != {"kind", "template"} or action["kind"] != "spawn":
        raise ValueError("onMet portu vyžaduje kind=spawn a template.")
    template = action["template"]
    if not isinstance(template, dict) or "name" not in template or set(template) - TEMPLATE_FIELDS:
        raise ValueError("Šablona vyžaduje name; podporuje purpose, spec, text, checks a goal_mode.")
    from backend.canvas.graph import validate_graph
    from backend.editor.node import node_specs, node_text
    node = {"id": "template", "parentId": None, "kind": "node", "name": template["name"],
            "purpose": template.get("purpose", ""), "x": 0, "y": 0,
            **{key: template[key] for key in ("checks", "goal_mode") if key in template}}
    validate_graph({"nodes": [node], "edges": []})
    scope = {"project": "draft", "workspace": "draft", "node": "template", "expected_revision": 0}
    if "spec" in template:
        if not isinstance(template["spec"], dict):
            raise ValueError("spec šablony musí být objekt.")
        node_specs.validate_payload({**scope, "fields": {**node_specs.EMPTY_FIELDS, **template["spec"]}})
    if "text" in template:
        node_text.validate_payload({**scope, "text": template["text"]})


def prepare_spawns(canvas, db, project, workspace, graph, previous, state):
    nodes, edges, origins = [], [], []
    next_x = {}
    by_id = {node["id"]: node for node in graph["nodes"]}
    for node_id, workflow in state["nodes"].items():
        old_blocks = {b["id"]: b for b in previous["nodes"].get(node_id, {}).get("blocks", [])}
        for block in workflow.get("blocks", []):
            if block["state"]["status"] != "met" or old_blocks.get(block["id"], {}).get("state", {}).get("status") == "met":
                continue
            for port in block.get("ports", []):
                if "onMet" not in port or port.get("status") == "rejected":
                    continue
                if db.execute("SELECT 1 FROM port_spawns WHERE project_id=? AND workspace_id=? AND node_id=? AND block_id=? AND port_id=?",
                              (project, workspace, node_id, block["id"], port["id"])).fetchone():
                    continue
                if node_id not in by_id:
                    raise ValueError("Port navazující karty musí patřit existujícímu uzlu.")
                source = by_id[node_id]
                parent = source["parentId"]
                if parent not in next_x:
                    next_x[parent] = max(n["x"] + n.get("size", {}).get("w", 360)
                                         for n in graph["nodes"] if n["parentId"] == parent) + 96
                ref = f"spawn-{len(nodes)}"
                nodes.append({"ref": ref, "kind": "node", "parent": "@" + source["parentId"] if source["parentId"] else None,
                              "position": {"x": next_x[parent], "y": source["y"]},
                              **copy.deepcopy(port["onMet"]["template"])})
                next_x[parent] += 456
                edges.append({"from": "@" + node_id, "to": ref, "port": "block", "block": block["id"], "blockPort": port["id"]})
                origins.append((node_id, block["id"], port["id"], ref))
    if not nodes:
        return None
    from backend.canvas.canvas_plan import _check_content, _check_graph
    from backend.canvas.canvas_plan_build import build
    from backend.canvas.canvas_plan_layout import layout
    built = build({"nodes": nodes, "edges": edges}, graph, state)
    _check_content(project, workspace, built)
    if layout(built.nodes, graph["nodes"], built.inside, built.positions) is not None:
        raise ValueError("Navazující karty nelze rozmístit.")
    _check_graph(canvas, project, workspace, graph, built)
    return built, origins


def persist_spawns(canvas, db, project, workspace, digest, prepared, stamp):
    if prepared is None:
        return
    built, origins = prepared
    for node_id, fields in built.specs.items():
        db.execute("INSERT INTO node_spec_revisions VALUES(?,?,?,?,?,?)", (project, workspace, node_id, 1, json.dumps(fields, ensure_ascii=False), stamp))
    for node_id, text in built.texts.items():
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", (project, workspace, node_id, 1, text, stamp))
    for node_id, block_id, port_id, ref in origins:
        db.execute("INSERT INTO port_spawns VALUES(?,?,?,?,?,?,?)", (project, workspace, node_id, block_id, port_id, built.refs[ref], stamp))
    canvas.save_graph(project, workspace, built.new_graph(), digest, _commit=False)
