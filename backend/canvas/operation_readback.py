"""Read native stores before marking an operation receipt complete."""
from backend.canvas.payload_errors import NextStep
from backend.editor.agent_memory.desktop_v3_state import fill_defaults
from copy import deepcopy


def verify_plan(service, store, project, workspace, built, wid_of, saved, revision):
    expected = built.new_graph()
    # save_graph rounds coordinates at persistence; ordering is not graph content.
    nodes = {node["id"]: {**node, "x": round(node["x"]), "y": round(node["y"])}
             for node in expected["nodes"]}
    edges = {edge["id"]: edge for edge in expected["edges"]}
    actual = saved["graph"]
    valid = (len(actual["nodes"]) == len(nodes) and len(actual["edges"]) == len(edges)
             and nodes == {node["id"]: node for node in actual["nodes"]}
             and edges == {edge["id"]: edge for edge in actual["edges"]})
    state = store.current(project, workspace)
    valid = valid and state["revision"] == revision and state["state"] == fill_defaults(deepcopy(built.state))
    for node, fields in built.specs.items():
        valid = valid and service.specs.read((project, wid_of(node), node))["fields"] == fields
    for node, text in built.texts.items():
        valid = valid and service.texts.read((project, wid_of(node), node))["text"] == text
    if not valid:
        raise NextStep("Canvas write could not be verified; the pending receipt is retained.",
                       code="operation_incomplete", hint="Read graph and document revisions; reconcile before repeating this operation.")
