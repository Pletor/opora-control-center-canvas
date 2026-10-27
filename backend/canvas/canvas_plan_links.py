"""Bloky s porty a vazby dávky plánu: blok dostane UUID, port si nechá svůj `ref` jako id
a vazba `block` míří na blok a port zdroje — z dávky podle refů, u existující karty podle id."""

from backend.canvas.canvas_plan_fields import fail, fields, items_of, new_id, plan_ref

BLOCK_FIELDS = {"ref", "title", "text", "condition", "ports"}
PORT_FIELDS = {"ref", "label", "status", "reason", "onMet"}
EDGE_FIELDS = {"from", "to", "port", "block", "blockPort", "carries"}
NO_BRANCH = {"kind": "none", "targetId": "", "note": ""}


def blocks_of(built, ref, node_id, items):
    blocks = []
    for index, item in enumerate(items):
        fields(item, BLOCK_FIELDS, {"ref", "title"}, f"{ref}.blocks[{index}]")
        label = f"{ref}/{plan_ref(item['ref'], f'{ref}.blocks[{index}]')}"
        if label in built.blocks:
            fail(label, "duplicitní ref bloku.")
        block_id = new_id()
        built.blocks[label] = block_id
        built.labels[block_id] = label
        ports = []
        for port_index, port in enumerate(items_of(item.get("ports", []), label, "ports")):
            fields(port, PORT_FIELDS, {"ref"}, f"{label}.ports[{port_index}]")
            # Id portu je jeho `ref`: unikátní jen uvnitř bloku a volající ho zná bez odpovědi.
            ports.append({"id": plan_ref(port["ref"], f"{label}.ports[{port_index}]"), "label": port.get("label", ""),
                          **{key: port[key] for key in ("status", "reason", "onMet") if key in port}})
        blocks.append({
            "id": block_id, "number": str(index + 1), "title": item["title"], "text": item.get("text", ""),
            "tags": [], "todos": [], "images": [],
            "state": {"status": "open", "condition": item.get("condition", ""),
                      "onMet": dict(NO_BRANCH), "onUnmet": dict(NO_BRANCH)},
            "parentBlockId": "", "ports": ports,
        })
    return blocks


def edge_of(built, item, label, resolve):
    fields(item, EDGE_FIELDS, {"from", "to"}, label)
    source, target = resolve(item["from"], label), resolve(item["to"], label)
    port = item.get("port", "next")
    edge = {"id": new_id(), "source": source, "target": target, "port": port}
    if port == "block":
        if "block" not in item or "blockPort" not in item:
            fail(label, "vazba block vyžaduje block a blockPort zdroje.")
        edge["sourceBlockId"], edge["sourcePortId"] = _source_port(built, source, item, label)
    elif "block" in item or "blockPort" in item:
        fail(label, "block a blockPort patří jen k vazbě s portem block.")
    # Druh toku jen přenese, nikdy nedoplní; jeho hodnotu a port hlídá `validate_graph`.
    if "carries" in item:
        edge["carries"] = item["carries"]
    built.labels[edge["id"]] = label
    built.edges.append(edge)


def _source_port(built, source, item, label):
    """Blok a port zdroje: z dávky podle `ref`, u existující karty podle id ve stavu."""
    if source in built.labels and built.labels[source] in built.refs:
        block_id = built.blocks.get(f"{built.labels[source]}/{item['block']}")
    else:
        block_id = built.blocks.get(f"@{source}/{item['block']}", item["block"])
    blocks = built.state["nodes"].get(source, {}).get("blocks", [])
    block = next((entry for entry in blocks if entry["id"] == block_id), None)
    if block is None:
        fail(label, f"zdroj vazby nemá blok {item['block']!r}.")
    if not any(port["id"] == item["blockPort"] for port in block.get("ports", [])):
        fail(label, f"blok {item['block']!r} nemá port {item['blockPort']!r}.")
    return block_id, item["blockPort"]
