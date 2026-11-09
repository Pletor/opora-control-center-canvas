"""Observed native documents and proposed state, with no writes during planning."""
from copy import deepcopy

from backend.canvas.graph import digest
from backend.canvas.opora_graph_complete_build import validate_content
from backend.editor.brief_vault.brief_vault_refs import resolve_plan_refs, validate_refs
from backend.editor.node.node_specs import EMPTY_FIELDS


def observe(canvas, project, workspace, built, revision, *, track_research=True):
    if any(expected != revision for expected in built.extend_revisions):
        raise ValueError("Complete plan has stale expectedRevision state.")
    documents = []
    for node in built.nodes:
        documents.append(_document(canvas, project, workspace, node["id"], "spec", 0,
                                   built.specs.get(node["id"], dict(EMPTY_FIELDS))))
        if node["id"] in built.texts:
            documents.append(_document(canvas, project, workspace, node["id"], "text", 0, built.texts[node["id"]]))
    for node, kind, expected, value in built.documents:
        documents.append(_document(canvas, project, workspace, node, kind, expected, value))
    resolve_plan_refs(canvas.db_for(project), project, workspace, built)
    fragments = {node: deepcopy(built.state["nodes"][node]["fragmentRefs"]) for node in built.fragment_refs}
    result = {"documents": documents, "fragments": fragments}
    if track_research:
        from backend.editor.research.fragment_evidence import observe as observe_research
        explicit = {}
        for node, requested in built.fragment_refs.items():
            requested = requested if isinstance(requested, list) else [requested]
            identifiers = {ref["fragmentId"] for ref in requested}
            explicit[node] = [ref for ref in fragments[node] if ref["fragmentId"] in identifiers]
        result["researchEvidenceByNode"] = observe_research(canvas.db_for(project), project, workspace, explicit)
    return result


def _document(canvas, project, workspace, node, kind, expected, value):
    owner = canvas.document_workspace(project, workspace, node)
    if owner != workspace:
        raise ValueError("Complete plan cannot change shared architecture documents.")
    current = (canvas.specs if kind == "spec" else canvas.texts).read((project, workspace, node))
    if current["revision"] != expected:
        raise ValueError("Complete plan document revision changed.")
    field = "fields" if kind == "spec" else "text"
    if kind == "spec" and not isinstance(value, dict):
        raise ValueError("Specification fields must be an object.")
    return {"nodeId": node, "kind": kind, "ownerWorkspace": owner, "expectedRevision": expected,
            "before": deepcopy(current[field]), "value": {**current[field], **value} if kind == "spec" else value}


def apply_inputs(project, workspace, built, inputs):
    """Restore observed documents and pinned fragments during immutable offline validation."""
    if "researchEvidenceByNode" in inputs:
        from backend.editor.research.fragment_evidence import validate_shape
        validate_shape(inputs["researchEvidenceByNode"], inputs["fragments"])
    wanted = [(node["id"], "spec") for node in built.nodes]
    wanted += [(node["id"], "text") for node in built.nodes if node["id"] in built.texts]
    wanted += [(node, kind) for node, kind, _, _ in built.documents]
    docs = inputs["documents"]
    if len(docs) != len(wanted) or {(doc["nodeId"], doc["kind"]) for doc in docs} != set(wanted):
        raise ValueError("Complete plan document scope mismatch.")
    requested = {(node["id"], "spec"): (0, built.specs.get(node["id"], dict(EMPTY_FIELDS))) for node in built.nodes}
    requested.update({(node["id"], "text"): (0, built.texts[node["id"]]) for node in built.nodes if node["id"] in built.texts})
    requested.update({(node, kind): (expected, value) for node, kind, expected, value in built.documents})
    for doc in docs:
        if set(doc) != {"nodeId", "kind", "ownerWorkspace", "expectedRevision", "before", "value"} or doc["ownerWorkspace"] != workspace:
            raise ValueError("Invalid complete document input.")
        expected, value = requested[(doc["nodeId"], doc["kind"])]
        proposed = {**doc["before"], **value} if doc["kind"] == "spec" else value
        if doc["expectedRevision"] != expected or doc["value"] != proposed:
            raise ValueError("Complete document differs from original plan.")
        (built.specs if doc["kind"] == "spec" else built.texts)[doc["nodeId"]] = deepcopy(doc["value"])
    if set(inputs["fragments"]) != set(built.fragment_refs):
        raise ValueError("Complete fragment scope mismatch.")
    for node, refs in inputs["fragments"].items():
        validate_refs(refs)
        previous = {ref["fragmentId"]: ref for ref in built.state["nodes"][node].get("fragmentRefs", [])}
        requested_refs = built.fragment_refs[node]
        requested_refs = requested_refs if isinstance(requested_refs, list) else [requested_refs]
        expected_ids = set(previous) | {ref["fragmentId"] for ref in requested_refs}
        if {ref["fragmentId"] for ref in refs} != expected_ids:
            raise ValueError("Complete fragment provenance mismatch.")
        by_id = {ref["fragmentId"]: ref for ref in refs}
        for requested_ref in requested_refs:
            if "revision" in requested_ref and by_id[requested_ref["fragmentId"]]["revision"] != requested_ref["revision"]:
                raise ValueError("Complete fragment revision mismatch.")
        built.state["nodes"][node]["fragmentRefs"] = deepcopy(refs)
        built.state_changed = True
    validate_content(project, workspace, built)
    return {"documents": deepcopy(docs), "after": deepcopy(built.state), "afterDigest": digest(built.state)}
