"""Native reversible drawing and shared-position writes with scoped durable replay."""
from copy import deepcopy
from backend.canvas.payload_errors import NextStep
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.editor.node.node_journal import NodeJournal
from backend.editor.node.drawing_files import decode_file

# OP-B171BE.draft: native stores remain authoritative; a receipt never fabricates a successful write.
CONTRACTS = {
    "canvas_routes.save_drawing_file": contract(("file",), effect="draft-asset",
        cas="native immutable file ID rejects different bytes", replay=True, output="Native uploaded file ID with verified bytes"),
    "node_routes.save_node_journal": contract(("node", "day", "expected_revision", "text"), effect="journal",
        cas="native per-node/day expected_revision", replay=True, output="Verified native journal revision and day index"),
    "canvas_routes.save_drawing": contract(("layer", "expected_revision", "scene"), effect="draft",
        cas="native drawing expected_revision", replay=True, output="Verified native local drawing revision"),
    "canvas_routes.graph_positions": contract(("digest", "positions"), effect="shared-layout",
        cas="native graph digest", replay=True, output="Verified persisted x/y positions; accepted authority unchanged"),
}


for _contract in CONTRACTS.values():
    _contract["test"] = "backend/api/brain_opora/test_canvas_capability_drafts.py"


def _snapshot(service, project, workspace, capability, data):
    if capability == "canvas_routes.save_drawing":
        return service.drawing(project, workspace, data["layer"])
    if capability == "node_routes.save_node_journal":
        return NodeJournal(service).access(project, workspace, data["node"], data["day"])
    if capability == "canvas_routes.save_drawing_file":
        identifier, _, _ = decode_file(data["file"])
        return service.drawing_file_list(project, workspace, identifier)
    view = service.view(project, workspace)
    return {"digest": view["digest"], "graph": deepcopy(view["graph"])}


def _verify(capability, data, before, after, result):
    if capability == "canvas_routes.save_drawing":
        valid = (after == result and result["revision"] == data["expected_revision"] + 1
                 and result["scene"] == data["scene"])
    elif capability == "node_routes.save_node_journal":
        valid = (after == result and result["revision"] == data["expected_revision"] + 1
                 and result["text"] == data["text"])
    elif capability == "canvas_routes.save_drawing_file":
        expected = data["file"]
        valid = result == {"id": expected["id"]} and len(after["files"]) == 1 and all(
            after["files"][0][key] == expected[key] for key in ("id", "mimeType", "dataURL"))
    else:
        positions = {item["id"]: (item["x"], item["y"]) for item in result["positions"]}
        expected = deepcopy(before["graph"])
        for node in expected["nodes"]:
            if node["id"] in positions:
                node["x"], node["y"] = positions[node["id"]]
        valid = after["digest"] == result["digest"] and after["graph"] == expected
    if not valid:
        raise NextStep("Native draft readback differs from the write result.", code="operation_incomplete",
                       hint="Inspect the existing native data and pending receipt; do not create a duplicate operation.")


def write(service, project, workspace, session, capability, data, request_id):
    from backend.brain_opora.canvas_capabilities.native_journal import run
    payload = {"project": project, "workspace": workspace, **data}
    def action():
        if capability == "canvas_routes.save_drawing":
            return service.drawing(project, workspace, data["layer"], payload)
        if capability == "node_routes.save_node_journal":
            return NodeJournal(service).access(project, workspace, data["node"], data["day"], payload)
        if capability == "canvas_routes.save_drawing_file":
            return service.drawing_file(payload)
        return service.save_positions(project, workspace, data["positions"], data["digest"], actor="agent")
    return run(service, project, workspace, session, capability, data, request_id,
        snapshot=lambda: _snapshot(service, project, workspace, capability, data), action=action,
        verify=lambda before, after, result: _verify(capability, data, before, after, result))
