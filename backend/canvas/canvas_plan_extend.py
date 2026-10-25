"""Append content to existing cards; document replacement requires explicit revisions.

`replaceBlocks: true` (with `blocks`) replaces the card's blocks instead of appending; it is refused while
a `block` edge still starts from one of the current blocks (the edge would point at nothing).

`layer` (frontend|backend|database|library) přepíše `card.layer` existující karty; bez něj se vrstva nemění.

`memberOf` (`@id` oblasti) zapíše výslovné logické členství uzlu nebo sektoru v oblasti, `null` ho zruší;
platnost (oblast se stejným rodičem) ověří `validate_graph` (docs/kontrakt-identity.md)."""

from backend.canvas.canvas_plan_fields import fail, fields, items_of, new_id, plan_ref
from backend.canvas.canvas_plan_links import PORT_FIELDS, blocks_of
from backend.canvas.graph import CARD_VALUES

EXTEND_FIELDS = {"node", "expectedRevision", "blocks", "ports", "rules", "spec", "text", "parent", "columns", "color", "fragmentRef",
                 "replaceBlocks", "layer", "memberOf"}


def extend_cards(built, extensions, existing):
    seen = set()
    for index, item in enumerate(extensions):
        label = f"extend[{index}]"
        fields(item, EXTEND_FIELDS, {"node", "expectedRevision"}, label)
        target = item["node"]
        if not isinstance(target, str) or not target.startswith("@") or target[1:] not in existing:
            fail(label, "node musí být @id existující karty.")
        node_id = target[1:]
        if node_id in seen:
            fail(label, "kartu lze rozšířit jen jednou v jedné dávce.")
        seen.add(node_id)
        if existing[node_id]["kind"] not in ("node", "sector", "area"):
            fail(label, "rozšířit lze jen uzel nebo sektor.")
        if type(item["expectedRevision"]) is not int or item["expectedRevision"] < 0:
            fail(label, "expectedRevision musí být nezáporná revize stavu.")
        built.extend_revisions.append(item["expectedRevision"])
        if existing[node_id]["kind"] == "area":
            if set(item) != {"node", "expectedRevision", "color"}:
                fail(label, "rozšíření oblasti podporuje pouze color.")
            existing[node_id]["color"] = item["color"]
            continue
        if "color" in item:
            fail(label, "color patří pouze oblasti.")
        if "columns" in item and "parent" not in item:
            fail(label, "columns vyžaduje cílovou oblast parent.")
        if "parent" in item:
            area = item["parent"]
            if not isinstance(area, str) or not area.startswith("@") or existing.get(area[1:], {}).get("kind") != "area":
                fail(label, "parent při přesunu musí být @id existující oblasti.")
            columns = item.get("columns", 2)
            group = built.layout_moves.setdefault(area, {"order": [], "columns": columns})
            if group["columns"] != columns:
                fail(label, "přesuny do téže oblasti musí mít stejný počet sloupců.")
            group["order"].append(target)
        cursor = node_id
        while cursor:
            if built.state["nodes"].get(cursor, {}).get("done", {}).get("confirmed"):
                fail(label, "uzavřenou kartu ani její potomky nelze rozšířit.")
            cursor = existing[cursor]["parentId"]
        if not set(item).intersection({"blocks", "ports", "rules", "spec", "text", "parent", "fragmentRef", "layer", "memberOf"}):
            fail(label, "rozšíření neobsahuje žádný obsah.")
        if "memberOf" in item:
            area = item["memberOf"]
            if area is None:
                existing[node_id].pop("memberOf", None)
            elif isinstance(area, str) and area.startswith("@") and existing.get(area[1:], {}).get("kind") == "area":
                existing[node_id]["memberOf"] = area[1:]
            else:
                fail(label, "memberOf musí být @id existující oblasti nebo null.")
        if "layer" in item:
            if item["layer"] not in CARD_VALUES["layer"] or existing[node_id]["kind"] != "node":
                fail(label, "layer je frontend / backend / database / library a patří uzlu.")
            if (existing[node_id].get("card") or {}).get("layer") != item["layer"]:
                existing[node_id]["card"] = {**(existing[node_id].get("card") or {}), "layer": item["layer"]}
        built.labels[node_id] = target
        workflow = built.state["nodes"].setdefault(node_id, {"phase": "discover", "criteria": [], "steps": []})
        if "fragmentRef" in item:
            built.fragment_refs[node_id] = item["fragmentRef"]
        blocks = workflow.setdefault("blocks", [])
        if "replaceBlocks" in item:
            if type(item["replaceBlocks"]) is not bool or "blocks" not in item:
                fail(label, "replaceBlocks je true/false a vyžaduje blocks.")
            if item["replaceBlocks"]:
                current = {block["id"] for block in blocks}
                if any(edge.get("source") == node_id and edge.get("sourceBlockId") in current
                       for edge in built.graph["edges"]):
                    fail(label, "replaceBlocks: z bloku karty vede vazba; nejdřív ji odpojte.")
                blocks.clear()
        offset = max((int(block["number"].split(".")[0]) for block in blocks), default=0)
        added = blocks_of(built, target, node_id, items_of(item.get("blocks", []), label, "blocks"))
        for position, block in enumerate(added, offset + 1):
            block["number"] = str(position)
        blocks.extend(added)
        for port_index, addition in enumerate(items_of(item.get("ports", []), label, "ports")):
            port_label = f"{label}.ports[{port_index}]"
            fields(addition, {"block", "ports"}, {"block", "ports"}, port_label)
            block_id = addition["block"]
            block = next((b for b in blocks if b["id"] == block_id), None)
            if block is None:
                fail(port_label, "blok karty neexistuje.")
            for port in items_of(addition["ports"], port_label, "ports"):
                fields(port, PORT_FIELDS, {"ref"}, port_label)
                block.setdefault("ports", []).append({"id": plan_ref(port["ref"], port_label), "label": port.get("label", ""),
                                                       **{key: port[key] for key in ("status", "reason", "onMet") if key in port}})
        for rule in items_of(item.get("rules", []), label, "rules"):
            fields(rule, {"text", "kind"}, {"text", "kind"}, label)
            built.state["rules"].append({"id": new_id(), **rule, "scope": "node", "target": node_id})
        for key in ("spec", "text"):
            if key in item:
                value_key = "fields" if key == "spec" else "text"
                fields(item[key], {"expectedRevision", value_key}, {"expectedRevision", value_key}, label)
                revision = item[key]["expectedRevision"]
                if type(revision) is not int or revision < 0:
                    fail(label, f"{key}.expectedRevision musí být nezáporné celé číslo.")
                built.documents.append((node_id, key, revision, item[key][value_key]))
        built.state_changed = True
