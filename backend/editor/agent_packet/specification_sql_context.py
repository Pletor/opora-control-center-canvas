"""Private pure semantic projection. This is not execution authority or source coverage."""
import copy

from backend.canvas.graph import digest, valid_id
from backend.editor.agent_memory.desktop_v3_state import (
    default_state,
    fill_defaults,
    validate_state,
)
from backend.editor.agent_packet.desktop_v3_packets import memory_for
from backend.editor.agent_packet.sector_status import sector_blockers, sector_status
from backend.editor.agent_packet.specification_context import _instructions
from backend.editor.agent_packet.specification_scope import project_graph, select_scope
from backend.editor.agent_packet.specification_sql_rows import (
    composed_graph,
    decode,
    latest,
    validate_rows,
)
from backend.editor.node.drawings import validate_scene
from backend.editor.node.node_specs import EMPTY_FIELDS, validate_payload
from backend.project_setup.project_hub import ARCHITECTURES, DEFAULT_SETTINGS, TENANCIES


def _document(rows, table, workspace, identifier, field, default):
    key = "layer_id" if table == "drawing_revisions" else "node_id"
    row = latest(rows, table, workspace_id=workspace, **{key: identifier})
    value = row[field] if row else copy.deepcopy(default)
    if row and field != "text":
        value = decode(value)
    revision = row["revision"] if row else 0
    if field == "fields":
        validate_payload({"project": "unused", "workspace": "unused", "node": identifier,
                          "expected_revision": revision, "fields": value})
    elif field == "scene":
        validate_scene(value)
    elif not isinstance(value, str) or len(value) > 64000 or "\0" in value:
        raise ValueError("Invalid SQL context text.")
    return {"revision": revision, field: value, "available": True}


def _project(rows, project, metadata):
    if (not isinstance(metadata, dict) or metadata.get("id") != project
            or not isinstance(metadata.get("name"), str)):
        raise ValueError("Frozen project identity and name are required.")
    values = dict(DEFAULT_SETTINGS)
    settings = latest(rows, "project_settings")
    if settings:
        values.update(goal=settings["goal"], platform=settings["platform"])
    profile = latest(rows, "project_profile")
    if profile:
        values.update(architecture=profile["architecture"] if profile["architecture"] in ARCHITECTURES else "",
                      tenancy=profile["tenancy"] if profile["tenancy"] in TENANCIES else "")
    return {"id": project, "name": metadata["name"], "revision": settings["revision"] if settings else 0,
            "settings": values}


def _memory(state, cards, paths, upstream):
    # The reader redacts IDs too. Benign positional IDs safely recover PRIVATE originals.
    temporary = {**state, **{key: [{**item, "id": f"scope_{key}_{position}"}
                                  for position, item in enumerate(state[key])]
                            for key in ("rules", "decisions")}}
    selected = memory_for({"revision": 0, "state": temporary}, cards, paths, "")
    recovered = {key: [state[key][int(item["id"].rsplit("_", 1)[1])] for item in selected[key]]
                 for key in ("rules", "decisions")}
    rules, decisions = recovered["rules"], recovered["decisions"]
    return {"rules": rules,
            "settings": state["settings"],
            "decisions": [item for item in decisions
                          if item.get("by") != "agent" or item.get("nodeId") in upstream]}


def project_sql_context(rows, project, workspace, node_id, *, metadata):
    """Return raw semantic data, never suitable for an unauthenticated/public response.

    Caller supplies a bounded transaction snapshot and frozen registry identity. Registry
    lifecycle, external files and accepted lineage need independent validation. No I/O.
    """
    if not all(valid_id(value) for value in (project, workspace, node_id)):
        raise ValueError("Invalid SQL context scope.")
    if workspace in {"main", "architecture"}:
        raise ValueError("SQL context requires a writable workspace.")
    validate_rows(rows, project)
    graph, architecture_ids = composed_graph(rows, workspace)
    selection = select_scope(graph, node_id)
    stored = latest(rows, "desktop_v3_state", workspace_id=workspace)
    state = fill_defaults(decode(stored["state"])) if stored else default_state()
    validate_state(state)
    by_id = {node["id"]: node for node in graph["nodes"]}
    cards = [node_id, *sorted(set(selection["cardIds"]) - {node_id})]
    descendants = next(item["nodeIds"] for item in selection["predicates"] if item["type"] == "descendants")
    descendants = {node_id, *descendants}
    upstream = {edge["source"] for edge in graph["edges"] if edge["target"] in descendants
                and edge["source"] not in descendants and edge.get("port") != "flow"}
    paths = [(by_id[identifier].get("sourceRef") or {}).get("path", "") for identifier in cards]
    documents, owners = [], []
    for identifier in sorted(cards):
        owner = "architecture" if identifier in architecture_ids else workspace
        owners.append({"nodeId": identifier, "specWorkspace": owner, "textWorkspace": owner})
        documents.append({"nodeId": identifier,
                          "spec": _document(rows, "node_spec_revisions", owner, identifier, "fields", EMPTY_FIELDS),
                          "content": _document(rows, "node_text_revisions", owner, identifier, "text", ""),
                          "instructions": _instructions(state["nodes"].get(identifier, {}))})
    drawings = [{"layer": identifier, "workspace": workspace,
                 **_document(rows, "drawing_revisions", workspace, identifier, "scene", {"elements": []}),
                 "imageContentsIncluded": False} for identifier in ["", *sorted(cards)]]
    statuses = sector_status(graph, state)
    # Only facts read by target/predecessor eligibility; unrelated work state stays outside.
    facts = [{"nodeId": identifier,
              "done": {key: state["nodes"].get(identifier, {}).get("done", {}).get(key)
                       for key in ("confirmed", "by")},
              "scenarioRun": {key: state["nodes"].get(identifier, {}).get("scenarioRun", {}).get(key)
                              for key in ("command", "failed")}}
             for identifier in selection["gatingIds"]]
    result = {"schema": "opora.private-sql-context/1", "scope": {
        "project": project, "workspace": workspace, "nodeId": node_id},
        "selection": selection, **project_graph(graph, selection, redact=False),
        "project": _project(rows, project, metadata), "owners": owners,
        **_memory(state, cards, paths, upstream), "cards": documents, "drawings": drawings,
        "eligibility": {"facts": facts, "blockers": sector_blockers(graph, state, node_id, statuses)},
        "referencesPolicy": "reference-only; external content is not captured or verified"}
    return copy.deepcopy(result)


def sql_context_digest(rows, project, workspace, node_id, *, metadata):
    """SHA256 of PRIVATE pre-redaction semantics; never a public capability."""
    return digest(project_sql_context(rows, project, workspace, node_id, metadata=metadata))
