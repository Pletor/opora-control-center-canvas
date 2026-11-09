"""Finite library operation validation, scoped preimages and native mutation/readback."""
from copy import deepcopy
import hashlib
import json

from backend.flow import library, workflows
from backend.flow.graph_check import FlowInvalid
from backend.brain_opora.determinism.gate_payloads import GateError

OPERATIONS = {"folder_create", "folder_update", "folder_delete", "flow_create", "flow_adopt", "flow_contribute", "flow_promote"}


def folder_digest(value):
    fields = {key: value[key] for key in ("id", "owner", "slug", "title", "description", "order")}
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(operation, data):
    from backend.api.flow.library_routes import FolderIn, FolderPatch, FlowIn, PromoteIn
    models = {"folder_create": FolderIn, "folder_update": FolderPatch, "flow_create": FlowIn,
              "flow_contribute": FlowIn, "flow_promote": PromoteIn}
    identifiers = {"folder_update": "folder_id", "folder_delete": "folder_id", "flow_adopt": "workflow_id",
                   "flow_contribute": "workflow_id", "flow_promote": "workflow_id"}
    if operation not in OPERATIONS or not isinstance(data, dict):
        raise FlowInvalid("Unknown library operation.")
    values = dict(data)
    expected = values.pop("expectedFolderDigest", None) if operation in ("folder_update", "folder_delete") else None
    if expected is not None and (not isinstance(expected, str) or len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected)):
        raise FlowInvalid("expectedFolderDigest must be a native SHA256 digest.")
    identity = identifiers.get(operation)
    identifier = values.pop(identity, None) if identity else None
    if identity and (not isinstance(identifier, str) or not identifier.strip()):
        raise FlowInvalid("A native library identifier is required.")
    if operation in models:
        model = models[operation]
        if values.keys() - model.model_fields.keys():
            raise FlowInvalid("Unknown library operation fields.")
        values = model.model_validate(values).model_dump(exclude_none=True)
        if "title" in values and not values["title"].strip():
            raise FlowInvalid("A nonempty title is required.")
    elif operation == "flow_adopt":
        if values.keys() - {"nodeId"} or ("nodeId" in values and (not isinstance(values["nodeId"], str) or not values["nodeId"].strip())):
            raise FlowInvalid("Adoption accepts only an optional native nodeId.")
    elif values:
        raise FlowInvalid("Unknown library operation fields.")
    return {**values, **({identity: identifier} if identity else {}), **({"expectedFolderDigest": expected} if expected is not None else {})}


def source(db, project, workflow_id):
    row = library._workflow(db, workflow_id)
    if row["project_id"] not in (None, project) or (row["project_id"] is None and library.part_of(db, workflow_id) is None):
        raise GateError(403, "gate_scope", "Source belongs to another project.", "Use own project or shared library content.")
    return row


def folder(db, operation, data):
    if operation in ("folder_update", "folder_delete"):
        return library.get_folder(db, data["folder_id"])
    if operation in ("flow_create", "flow_contribute") or (operation == "flow_promote" and data.get("folder")):
        return library.get_folder(db, data["folder"])
    if operation == "flow_promote":
        row = library._workflow(db, data["workflow_id"])
        match = workflows.LIBRARY_OWNER.fullmatch(row["owner_ref"] or "")
        if not match or match.group(1) != "agent":
            raise FlowInvalid("Only an agent library flow can be promoted.")
        found = db.execute("SELECT id FROM flow_library_folders WHERE owner='human' AND slug=?", (match.group(2),)).fetchone()
        if found is None:
            raise workflows.FlowNotFound("Select an existing human library folder.")
        return library.get_folder(db, found[0])
    return None


def observe(service, project, workspace, operation, data):
    """Only relevant scoped inputs; never expose other projects' structured lineage."""
    db = service.db
    target = folder(db, operation, data)
    owner = data["owner"] if operation == "folder_create" else target["owner"] if target else None
    if operation in ("folder_update", "folder_delete"):
        expected = data.get("expectedFolderDigest")
        if (owner == "agent" and expected is None) or (expected is not None and expected != folder_digest(target)):
            from backend.canvas.payload_errors import NextStep
            raise NextStep("Library folder changed since it was read.", code="library_folder_conflict",
                           hint="Read library_list again and use the folder revisionDigest as expectedFolderDigest.")
    if operation == "flow_promote" and owner != "human":
        raise FlowInvalid("Promotion targets the human library.")
    observed = {"folder": target}
    if "workflow_id" in data:
        row = source(db, project, data["workflow_id"])
        from backend.brain_opora.canvas_capabilities.library_reads import _meta, _source
        version = (library._source_version(db, data["workflow_id"]) if operation != "flow_promote" or
                   workflows.list_versions(db, data["workflow_id"]) else None)
        observed["source"] = {key: row[key] for key in ("id", "name", "description", "owner_ref", "project_id")}
        observed["version"] = ({**version, "meta": _meta(project, version.get("meta")),
                                "derived_from": _source(db, project, version.get("derived_from"))} if version else None)
        if operation == "flow_adopt":
            if row["project_id"] is not None or library.part_of(db, row["id"]) is None:
                raise FlowInvalid("Only shared library content can be adopted.")
            if data.get("nodeId") and not any(node["id"] == data["nodeId"] for node in service.view(project, workspace)["graph"]["nodes"]):
                raise GateError(403, "gate_scope", "Adoption target is not in this workspace.", "Choose an existing scoped node.")
        if operation == "flow_promote" and library.part_of(db, row["id"]) != "agent":
            raise FlowInvalid("Only agent library content can be promoted.")
    if operation == "folder_create":
        library._slug(data["slug"])
        observed["collision"] = [dict(row) for row in db.execute("SELECT id FROM flow_library_folders WHERE owner=? AND slug=?", (owner, data["slug"]))]
    elif operation == "folder_delete":
        observed["flows"] = [row["id"] for row in library._flows(db, owner, target["slug"])]
        if observed["flows"]:
            raise workflows.FlowConflict("Folder is not empty.", "folder_not_empty")
    elif operation in ("flow_create", "flow_contribute", "flow_promote"):
        slug = data.get("slug") or workflows.LIBRARY_OWNER.fullmatch(observed["source"]["owner_ref"]).group(3)
        library._slug(slug)
        ref = library.owner_ref(owner, target["slug"], slug)
        observed["collision"] = [row["id"] for row in db.execute("SELECT id FROM flow_workflows WHERE project_id IS NULL AND owner_ref=?", (ref,))]
    if observed.get("collision"):
        raise workflows.FlowConflict("Target name is already in use.", "owner_taken")
    return owner, observed


def apply(db, project, operation, data):
    if operation == "folder_create":
        return library.create_folder(db, data["owner"], data["slug"], data["title"], data.get("description", ""), data.get("order"))
    if operation == "folder_update":
        return library.update_folder(db, data["folder_id"], data.get("title"), data.get("description"), data.get("order"))
    if operation == "folder_delete":
        return library.delete_folder(db, data["folder_id"])
    if operation == "flow_create":
        return library.create_flow(db, data["folder"], data["slug"], data["title"], data.get("description"))
    if operation == "flow_adopt":
        return library.adopt(db, data["workflow_id"], project, data.get("nodeId"))
    if operation == "flow_contribute":
        return library.contribute(db, data["workflow_id"], data["folder"], data["slug"], data["title"])
    return library.promote(db, data["workflow_id"], data.get("folder"))


def readback(db, project, operation, result):
    if operation == "folder_delete":
        if db.execute("SELECT 1 FROM flow_library_folders WHERE id=?", (result["deleted"],)).fetchone():
            raise RuntimeError("Library deletion readback failed.")
        return result
    saved = library.get_folder(db, result["id"]) if operation.startswith("folder_") else library.flow_detail(db, result["id"])
    if saved != result:
        raise RuntimeError("Library write readback failed.")
    if not operation.startswith("folder_"):
        from backend.brain_opora.canvas_capabilities.library_reads import _summary
        return _summary(db, project, saved)
    return deepcopy(saved)
