"""Deterministic area grids and a read-only schematic SVG of one canvas layer."""

import copy
from html import escape

from backend.canvas.areas import area_of
from backend.canvas.canvas_plan_layout import AREA_PAD, CARD, GAP, _clear, body_rect, body_size
from backend.canvas.graph import valid_id, validate_graph


def identifier(value):
    if not isinstance(value, str) or not value.startswith("@") or not valid_id(value[1:]):
        raise ValueError("Očekávám odkaz @id.")
    return value[1:]


def arrange(graph, area_ref, order, columns, color=None):
    if not isinstance(order, list) or not 1 <= len(order) <= 200:
        raise ValueError("order musí obsahovat 1 až 200 karet.")
    if type(columns) is not int or not 1 <= columns <= 20:
        raise ValueError("columns musí být celé číslo 1 až 20.")
    ids = [identifier(ref) for ref in order]
    if len(ids) != len(set(ids)):
        raise ValueError("order obsahuje duplicitní kartu.")
    result = copy.deepcopy(graph)
    nodes = {node["id"]: node for node in result["nodes"]}
    area = nodes.get(identifier(area_ref))
    if not area or area["kind"] != "area":
        raise ValueError("Cílová oblast neexistuje.")
    if any(node_id not in nodes or nodes[node_id]["kind"] == "area" for node_id in ids):
        raise ValueError("Přesouvat lze existující karty nebo komentáře, ne oblasti.")
    if color is not None:
        area["color"] = color
    occupied = [body_rect(node) for node in result["nodes"] if node["id"] not in ids
                and node["id"] != area["id"] and node["parentId"] == area["parentId"] and node["kind"] != "area"]
    for index, node_id in enumerate(ids):
        node = nodes[node_id]
        node["parentId"] = area["parentId"]
        node["x"] = area["x"] + AREA_PAD + (index % columns) * (CARD[0] + GAP)
        node["y"] = area["y"] + AREA_PAD + (index // columns) * (CARD[1] + GAP)
        width, height = body_size(node)
        if node["x"] + width > area["x"] + area["size"]["w"] - AREA_PAD or node["y"] + height > area["y"] + area["size"]["h"] - AREA_PAD:
            raise ValueError("Mřížka se nevejde do oblasti; zvětšete oblast nebo změňte počet sloupců.")
        if not _clear(body_rect(node), occupied):
            raise ValueError("Mřížka koliduje s kartou mimo order; zahrňte ji do pořadí nebo zvolte jinou oblast.")
        if (area_of(node, result["nodes"]) or {}).get("id") != area["id"]:
            raise ValueError("Karta by připadla jiné překrývající se oblasti.")
        occupied.append(body_rect(node))
    validate_graph(result)
    return result


def layout_preview(graph, layer):
    if layer and not any(node["id"] == layer and node["kind"] in ("node", "sector") for node in graph["nodes"]):
        raise ValueError("Vrstva náhledu neexistuje.")
    nodes = [node for node in graph["nodes"] if node["parentId"] == (layer or None)]
    boxes = {node["id"]: body_rect(node) for node in nodes}
    x0 = min((box[0] for box in boxes.values()), default=0) - 24
    y0 = min((box[1] for box in boxes.values()), default=0) - 24
    x1 = max((box[0] + box[2] for box in boxes.values()), default=800) + 24
    y1 = max((box[1] + box[3] for box in boxes.values()), default=450) + 24
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="{x0} {y0} {x1-x0} {y1-y0}" role="img" aria-label="Schematický náhled plátna">',
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#64748b"/></marker></defs>']
    palette = {"indigo": "#6366f1", "teal": "#14b8a6", "amber": "#f59e0b", "rose": "#f43f5e", "violet": "#8b5cf6", "slate": "#64748b"}
    area_index = 0
    for node in sorted(nodes, key=lambda n: n["kind"] != "area"):
        x, y, width, height = boxes[node["id"]]
        area = node["kind"] == "area"
        area_index += int(area)
        prefix = (chr(0x2460 + area_index - 1) if area_index <= 20 else str(area_index)) + " " if area else ""
        color = palette.get(node.get("color", "slate"), "#64748b")
        parts.append(f'<g data-node-id="{escape(node["id"], quote=True)}"><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" fill="{("none" if area else "#f8fafc")}" stroke="{color}" stroke-width="2"' + (' stroke-dasharray="10 6"' if area else '') + '/>')
        parts.append(f'<text x="{x+12}" y="{y+25}" fill="#334155" font-size="18">{escape(prefix + node["name"][:48])}</text></g>')
    for edge in graph["edges"]:
        if edge["source"] not in boxes or edge["target"] not in boxes:
            continue
        a, b = boxes[edge["source"]], boxes[edge["target"]]
        parts.append(f'<path d="M{a[0]+a[2]} {a[1]+a[3]/2} L{b[0]} {b[1]+b[3]/2}" stroke="#64748b" stroke-width="2" fill="none" marker-end="url(#arrow)"/>')
    return "".join(parts) + "</svg>"


def apply_layout(canvas, payload, *, actor="system"):
    required = {"project", "workspace", "digest", "area", "order", "columns"}
    if not isinstance(payload, dict) or not required <= set(payload) or set(payload) - required - {"color", "dryRun"}:
        raise ValueError("Rozmístění vyžaduje project, workspace, digest, area, order, columns; volitelně color a dryRun.")
    if type(payload.get("dryRun", False)) is not bool:
        raise ValueError("dryRun musí být true/false.")
    project, workspace = payload["project"], payload["workspace"]
    with canvas.graph_lock_for(project):
        view = canvas.view(project, workspace)
        if view["readOnly"] or view["digest"] != payload["digest"]:
            raise ValueError("Plátno je pouze ke čtení nebo se změnilo.")
        graph = arrange(view["graph"], payload["area"], payload["order"], payload["columns"], payload.get("color"))
        canvas._verify_source_refs(project, workspace, view["graph"], graph)
        area = next(n for n in graph["nodes"] if n["id"] == identifier(payload["area"]))
        result = {"graph": graph, "moved": [identifier(ref) for ref in payload["order"]], "svg": layout_preview(graph, area["parentId"] or ""), "dryRun": payload.get("dryRun", False)}
        if result["dryRun"]:
            return {**result, "digest": view["digest"]}
        saved = canvas.save_graph(project, workspace, graph, payload["digest"], actor=actor)
        return {**result, "digest": saved["digest"]}
