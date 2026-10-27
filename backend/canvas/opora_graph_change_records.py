"""Re-derive graph change evidence when reading content-addressed v2 records."""
import json

from backend.canvas.graph import digest, validate_graph
from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_graph_change_additions import validate_origin
from backend.canvas.opora_graph_change_build import build
from backend.canvas.opora_graph_change_safety import preflight
from backend.canvas.opora_graph_change_state import validate_review
from backend.canvas.opora_graph_records import validate_documents
from backend.editor.node.node_specs import validate_payload


def validate_record(record):
    try:
        _validate(record)
    except (KeyError, TypeError, RecursionError) as exc:
        raise ValueError("Invalid graph change record.") from exc


def _validate(record):
    project, workspace = scope(record)
    json.dumps(record, allow_nan=False)
    if type(record.get("schemaVersion")) is not int or record["schemaVersion"] != 2 or record.get("kind") != "graph-changes":
        raise ValueError("Invalid graph change kind/version.")
    for key in ("parentRevision", "parentGraphManifestId"):
        identifier(record[key])
    identifier(record["supersedes"], nullable=True)
    if record["requiresBaseAdoption"] is not False or record["adoptionDocuments"] != []:
        raise ValueError("Graph changes require an existing accepted manifest.")
    for key in ("acceptedGraph", "baseGraph", "resultGraph", "acceptedResultGraph"):
        validate_graph(record[key])
    if record["graphDigest"] != digest(record["baseGraph"]):
        raise ValueError("Graph change base digest mismatch.")
    validate_origin(record)
    rebuilt = build(record["acceptedGraph"], record["baseGraph"], record["plan"], {}, previous=record)
    for key in ("plan", "resultGraph", "acceptedResultGraph", "changes", "preconditions", "additions"):
        if rebuilt[key] != record[key]:
            raise ValueError("Graph change derived evidence mismatch.")
    ids = {item["id"] for item in record["additions"]["nodes"]}
    specs = record["specifications"]
    if len(specs) != len(ids) or {item["nodeId"] for item in specs} != ids:
        raise ValueError("Every added node requires one specification.")
    for item in specs:
        validate_payload({"project": project, "workspace": workspace, "node": item["nodeId"],
                          "expected_revision": 0, "fields": item["fields"]})
    for node in record["additions"]["nodes"]:
        if node["kind"] not in ("node", "sector", "area") or not set(node) <= {
            "id", "parentId", "kind", "name", "purpose", "x", "y", "size", "sourceRef", "memberOf"
        }:
            raise ValueError("Invalid persisted node addition.")
    for edge in record["additions"]["edges"]:
        if not set(edge) <= {"id", "source", "target", "port", "carries"} or edge.get("port", "next") != "next":
            raise ValueError("Invalid persisted edge addition.")
    validate_review(record["stateEffects"])
    state = record["stateEffects"]
    checked, memberships = preflight(record["acceptedGraph"], record["baseGraph"], record["resultGraph"],
        record["acceptedResultGraph"], state["before"], set(state["removedNodeIds"]), set(state["removedEdgeIds"]),
        adopt_architecture=record["plan"]["adoptArchitectureContext"])
    if checked != state["checkedNodeIds"] or memberships != state["effects"]["areaMembershipChanges"]:
        raise ValueError("State safety evidence differs from reviewed graphs.")
    validate_documents(record["architectureDocuments"], project, workspace)
    architecture = record["changes"]["architectureContext"]
    expected = {node["id"] for node in architecture["workingBefore"]["nodes"]} if architecture else set()
    if {item["nodeId"] for item in record["architectureDocuments"]} != expected:
        raise ValueError("Architecture dependency document scope mismatch.")
    for stored, planned in (("removedNodeIds", "removeNodes"), ("removedEdgeIds", "removeEdges")):
        if sorted(record["stateEffects"][stored]) != sorted(record["plan"][planned]):
            raise ValueError("State cleanup scope differs from graph operations.")
    if sorted(record["stateEffects"]["rewiredEdgeIds"]) != sorted(item["id"] for item in record["plan"]["updateEdges"]):
        raise ValueError("Edge report cleanup scope mismatch.")
