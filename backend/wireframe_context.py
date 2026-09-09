"""Read-only, deterministic projection of a saved Excalidraw wireframe scene."""


def _label(element, bound_text):
    value = element.get("name") or element.get("text") or bound_text.get(element.get("id"))
    return value if isinstance(value, str) else ""


def _native(element, label):
    geometry = {key: element[key] for key in ("x", "y", "width", "height")}
    colors = {key: element.get(key) for key in ("strokeColor", "backgroundColor")}
    return {
        "id": element["id"], "type": element["type"], **geometry, **colors,
        "geometry": geometry, "colors": colors, "label": label, "frameId": element.get("frameId"),
    }


def wireframe_context(project, workspace, layer, drawing_snapshot):
    """Project saved scene only; metadata is copied as data and never evaluated."""
    scene = drawing_snapshot.get("scene", {}) if isinstance(drawing_snapshot, dict) else {}
    raw = scene.get("elements", []) if isinstance(scene, dict) else []
    elements = [item for item in raw if isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("type"), str)]
    bound_text = {item.get("containerId"): item.get("text") for item in elements if isinstance(item.get("containerId"), str) and isinstance(item.get("text"), str)}
    blocks, wire_elements, annotations = [], [], []
    frames = {}
    for item in elements:
        metadata = item.get("customData", {}).get("oporaWireframe") if isinstance(item.get("customData"), dict) else None
        native = _native(item, _label(item, bound_text))
        if not isinstance(metadata, dict):
            annotations.append(native)
            continue
        record = {**native, "wireframe": metadata}
        if metadata.get("role") == "block":
            blocks.append(record)
            frames[item["id"]] = native["geometry"]
        elif metadata.get("role") == "element":
            wire_elements.append(record)
        else:
            annotations.append(record)
    for item in wire_elements:
        frame = frames.get(item["frameId"])
        if frame is not None:
            geometry = item["geometry"]
            item["relative"] = {"x": geometry["x"] - frame["x"], "y": geometry["y"] - frame["y"], "width": geometry["width"], "height": geometry["height"]}
    return {
        "project": project,
        "workspace": workspace,
        "layer": layer,
        "drawingRevision": drawing_snapshot.get("revision", 0),
        "blocks": blocks,
        "elements": wire_elements,
        "annotations": annotations,
        "source": drawing_snapshot.get("source"),
    }
