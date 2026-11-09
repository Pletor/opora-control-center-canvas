"""Finite access to the existing versioned Storyboard service."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.editor.storyboard.storyboard import StoryboardService

CONTRACTS = {
    "storyboard_routes.storyboard_read": contract(("nodeId",), ("revision",), types={"revision": "integer"}),
    "storyboard_routes.storyboard_write": contract(("nodeId", "expected_revision", "storyboard"),
        effect="draft", replay=True, cas="Native Storyboard expected_revision"),
}


def invoke(service, project, workspace, session, capability, data, request_id):
    native = StoryboardService(service)
    snapshot = lambda: native.read(project, workspace, data["nodeId"])
    if capability.endswith("storyboard_read"):
        return {"state": "read", "result": native.read(project, workspace, data["nodeId"], data.get("revision"))}
    def verify(before, after, result):
        # Saving null over an already absent scene is a native no-op.
        expected = data["expected_revision"] + (0 if data["storyboard"] is None and before["storyboard"] is None else 1)
        if result != {"revision": after["revision"]} or after["revision"] != expected:
            raise ValueError("Storyboard native readback differs.")
    return run(service, project, workspace, session, capability, data, request_id,
        snapshot=snapshot, action=lambda: native.save({"project": project, "workspace": workspace, **data}), verify=verify)
