"""Fail-closed shape checks for content-addressed graph records and accepted documents."""
# ruff: noqa: TRY004 -- domain validation maps to HTTP 409.
import json

from backend.canvas.architecture_graph import split
from backend.canvas.graph import digest, valid_id, validate_graph
from backend.canvas.opora_change_validation import identifier, scope
from backend.editor.node.node_specs import validate_payload


def validate_documents(items, project, workspace):
    if not isinstance(items, list):
        raise ValueError("Invalid accepted documents.")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"nodeId", "ownerWorkspace", "revision", "fields"}:
            raise ValueError("Invalid accepted document.")
        if not valid_id(item["nodeId"]) or item["nodeId"] in seen:
            raise ValueError("Duplicate accepted document.")
        seen.add(item["nodeId"])
        scope({"project": project, "workspace": item["ownerWorkspace"]})
        validate_payload({"project": project, "workspace": workspace, "node": item["nodeId"],
                          "expected_revision": item["revision"], "fields": item["fields"]})


def combined(manifest):
    return {key: [*manifest["architectureContext"][key], *manifest["graph"][key]] for key in ("nodes", "edges")}


def validate_record(record, *, manifest=False):
    project, workspace = scope(record)
    try:
        json.dumps(record, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Graph record requires finite JSON.") from exc
    if (type(record.get("schemaVersion")) is not int or record["schemaVersion"] != 1
            or record.get("kind") != ("graph-manifest" if manifest else "graph-additions")):
        raise ValueError("Invalid graph record kind/version.")
    if manifest:
        validate_graph(combined(record))
        if split(combined(record)) != (record["architectureContext"], record["graph"]):
            raise ValueError("Manifest content must not own architecture sites.")
        return
    identifier(record["parentRevision"], nullable=True)
    identifier(record["parentGraphManifestId"], nullable=True)
    identifier(record["supersedes"], nullable=True)
    validate_graph(record["baseGraph"])
    if record["graphDigest"] != digest(record["baseGraph"]):
        raise ValueError("Observed base graph digest mismatch.")
    graph = {key: [*record["baseGraph"][key], *record["additions"][key]] for key in ("nodes", "edges")}
    validate_graph(graph)
    for node in record["additions"]["nodes"]:
        if (node["kind"] not in ("node", "sector", "area")
                or not set(node) <= {"id", "parentId", "kind", "name", "purpose", "x", "y", "size", "sourceRef", "memberOf"}):
            raise ValueError("Unsupported persisted graph addition.")
    for edge in record["additions"]["edges"]:
        if not set(edge) <= {"id", "source", "target", "port"} or edge.get("port", "next") != "next":
            raise ValueError("Unsupported persisted edge addition.")
    if type(record["requiresBaseAdoption"]) is not bool or record["requiresBaseAdoption"] != (record["parentGraphManifestId"] is None):
        raise ValueError("Invalid graph adoption declaration.")
    validate_documents(record["adoptionDocuments"], project, workspace)
    specs = record["specifications"]
    ids = {item["id"] for item in record["additions"]["nodes"]}
    if not isinstance(specs, list) or len(specs) != len(ids) or {item["nodeId"] for item in specs} != ids:
        raise ValueError("Every added node requires exactly one specification.")
    for item in specs:
        validate_payload({"project": project, "workspace": workspace, "node": item["nodeId"],
                          "expected_revision": 0, "fields": item["fields"]})


def accepted_record(repo, record_id):
    record = repo.read(record_id)
    validate_accepted(record, repo.scope)
    return record


def validate_accepted(record, record_scope):
    if record.get("kind") not in ("baseline", "acceptance", "graph-acceptance", "graph-baseline"):
        raise ValueError("Invalid accepted revision kind.")
    identifier(record.get("parentRevision"), nullable=record["kind"] in ("baseline", "graph-baseline"))
    validate_documents(record.get("documents"), *record_scope)
    identifier(record.get("graphManifestId"), nullable=True)
    identifier(record.get("contentManifestId"), nullable=True)
    if record["kind"] in ("graph-acceptance", "graph-baseline"):
        identifier(record.get("graphManifestId"))
    if record["kind"] == "graph-baseline" and record.get("parentRevision") is not None:
        raise ValueError("Invalid graph baseline ancestry.")
    if record["kind"] != "baseline":
        identifier(record.get("proposalId"))
    elif record.get("parentRevision") is not None or record.get("proposalId") is not None:
        raise ValueError("Invalid baseline ancestry.")
    return record


def preserved_manifest(repo, record_id):
    """Spec-only acceptance carries verified graph authority without adopting live edits."""
    record = accepted_record(repo, record_id)
    manifest_id = record.get("graphManifestId")
    result = preserved_content_manifest(repo, record_id)
    if manifest_id is not None:
        from database.repositories.opora_graph_proposals import GraphProposals
        GraphProposals(repo.db, *repo.scope).read(manifest_id, manifest=True)
        result["graphManifestId"] = manifest_id
    return result


def preserved_content_manifest(repo, record_id):
    if record_id is None:
        return {}
    record = accepted_record(repo, record_id)
    identifier = record.get("contentManifestId")
    if identifier is not None:
        from database.repositories.opora_content_records import ContentRecords
        ContentRecords(repo.db, *repo.scope).read(identifier, manifest=True)
        return {"contentManifestId": identifier}
    return {}
