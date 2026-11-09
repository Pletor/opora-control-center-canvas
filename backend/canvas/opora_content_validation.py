"""Bounded typed content entries and immutable proposal/manifest shapes."""
# ruff: noqa: TRY004 -- domain validation is mapped to an API conflict.
import re

from backend.canvas.graph import digest, valid_id
from backend.canvas.opora_change_validation import identifier, scope, subject
from backend.canvas.opora_commit_validation import _author
from backend.editor.agent_memory.desktop_v3_state import (
    ACTION_KEYS,
    BLOCK_KEYS,
    BRANCH_KEYS,
    IMAGE_KEYS,
    MATERIAL_KEYS,
    NODE_RULE_KEYS,
    PORT_KEYS,
    TODO_KEYS,
)
from backend.editor.node.drawings import _json_safe, validate_scene

CONFIG_FIELDS = {"actions", "rules", "blocks", "materials", "downloadsUrl"}
ENTRY_KEYS = {"kind", "target", "field", "ownerWorkspace", "value"}
PROPOSAL_KEYS = {"schemaVersion", "kind", "project", "workspace", "parentRevision", "graphDigest", "subject",
                 "by", "createdAt", "supersedes", "requiresBaseContentAdoption", "baseContentDigest", "baseContent", "changes"}
MANIFEST_KEYS = {"schemaVersion", "kind", "project", "workspace", "entries"}


def entry_key(entry):
    return entry["kind"], entry["target"], entry["field"]


def validate_value(kind, field, value):
    _json_safe(value)
    if kind == "text" and field == "text":
        if not isinstance(value, str) or len(value) > 64000 or "\0" in value:
            raise ValueError("Content text exceeds its typed limit.")
    elif kind == "drawing" and field == "scene":
        validate_scene(value)
    elif kind == "storyboard" and field == "storyboard":
        if value is not None:
            from backend.editor.storyboard.storyboard import validate_storyboard
            validate_storyboard(value)
    elif kind == "config" and field in CONFIG_FIELDS:
        if field == "downloadsUrl" and value is None:
            return
        if field == "downloadsUrl":
            if type(value) is not bool:
                raise ValueError("Content download URL flag must be boolean or null.")
        elif not isinstance(value, list) or len(value) > (50 if field == "materials" else 200):
            raise ValueError("Content configuration must be a bounded array.")
        else:
            keys = {"actions": ACTION_KEYS, "rules": NODE_RULE_KEYS, "materials": MATERIAL_KEYS}
            seen = set()
            for item in value:
                if not isinstance(item, dict) or (field in keys and set(item) != keys[field]):
                    raise ValueError("Invalid content configuration item shape.")
                if not valid_id(item.get("id")) or item["id"] in seen:
                    raise ValueError("Duplicate or invalid content configuration ID.")
                seen.add(item["id"])
                if field == "blocks":
                    state = item.get("state")
                    if (set(item) not in (BLOCK_KEYS, BLOCK_KEYS | {"ports"})
                            or not isinstance(state, dict) or set(state) != {"condition", "onMet", "onUnmet"}
                            or not isinstance(item.get("todos"), list)
                            or any(not isinstance(todo, dict) or set(todo) != TODO_KEYS - {"done"} for todo in item["todos"])
                            or not isinstance(item.get("images"), list)
                            or any(not isinstance(image, dict) or set(image) != IMAGE_KEYS for image in item["images"])
                            or not isinstance(item.get("ports", []), list)
                            or any(not isinstance(port, dict) or set(port) != PORT_KEYS for port in item.get("ports", []))
                            or any(not isinstance(state[key], dict) or set(state[key]) != BRANCH_KEYS for key in ("onMet", "onUnmet"))):
                        raise ValueError("Content blocks must exclude working progress.")
    else:
        raise ValueError("Unsupported content kind or field.")


def _target(item):
    kind, target = item.get("kind"), item.get("target")
    if not ((kind == "drawing" and target == "") or valid_id(target)):
        raise ValueError("Invalid content target.")


def validate_entry(entry):
    if not isinstance(entry, dict) or entry.get("kind") not in {"text", "drawing", "storyboard", "config"}:
        raise ValueError("Invalid content entry.")
    native = entry["kind"] in {"text", "drawing", "storyboard"}
    if set(entry) != ENTRY_KEYS | ({"revision"} if native else set()):
        raise ValueError("Invalid content entry fields.")
    _target(entry)
    scope({"project": "content", "workspace": entry["ownerWorkspace"]})
    if native and (type(entry["revision"]) is not int or entry["revision"] < 0):
        raise ValueError("Invalid content source revision.")
    validate_value(entry["kind"], entry["field"], entry["value"])


def validate_entries(entries):
    if not isinstance(entries, list) or len(entries) > 16384:
        raise ValueError("Content manifest entry bound exceeded.")
    previous = None
    for entry in entries:
        validate_entry(entry)
        key = entry_key(entry)
        if previous is not None and key <= previous:
            raise ValueError("Content entry keys must be unique and sorted.")
        previous = key


def _change(change):
    if not isinstance(change, dict):
        raise ValueError("Invalid content change.")
    native = change.get("kind") in {"text", "drawing", "storyboard"}
    fields = {"kind", "target", "field", "value", "before", "acceptedBefore", "observedOwner", "observedRound"}
    if set(change) != fields | ({"observedRevision"} if native else set()):
        raise ValueError("Invalid content change fields.")
    entry = {key: change[key] for key in ("kind", "target", "field", "value")}
    entry["ownerWorkspace"] = change["observedOwner"]
    if native:
        entry["revision"] = change["observedRevision"]
    validate_entry(entry)
    validate_value(change["kind"], change["field"], change["before"])
    if change["acceptedBefore"] is not None:
        validate_entry(change["acceptedBefore"])
        if entry_key(change["acceptedBefore"]) != entry_key(change):
            raise ValueError("Accepted content precondition key differs.")
    number = change["observedRound"]
    if number is not None and (type(number) is not int or number < 1):
        raise ValueError("Invalid content round precondition.")
    if change["target"] == "" and number is not None:
        raise ValueError("Root drawing cannot own a card round.")


def validate_record(record, *, manifest=False):
    _json_safe(record)
    if not isinstance(record, dict) or set(record) - {"id"} != (MANIFEST_KEYS if manifest else PROPOSAL_KEYS):
        raise ValueError("Invalid immutable content record fields.")
    scope(record)
    if "id" in record:
        identifier(record["id"])
    if type(record["schemaVersion"]) is not int or record["schemaVersion"] != 1:
        raise ValueError("Unsupported content schema.")
    if record["kind"] != ("content-manifest" if manifest else "content-proposal"):
        raise ValueError("Invalid content record kind.")
    if manifest:
        validate_entries(record["entries"])
        return
    identifier(record["parentRevision"])
    identifier(record["supersedes"], nullable=True)
    if any(not isinstance(record[key], str) or not re.fullmatch(r"[a-f0-9]{64}", record[key])
           for key in ("graphDigest", "baseContentDigest")):
        raise ValueError("Invalid content base digest.")
    subject(record)
    _author(record["by"], allow_agent=True)
    if not isinstance(record["createdAt"], str) or not 1 <= len(record["createdAt"]) <= 80:
        raise ValueError("Invalid content timestamp.")
    if type(record["requiresBaseContentAdoption"]) is not bool:
        raise ValueError("Invalid content adoption marker.")
    validate_entries(record["baseContent"])
    if digest(record["baseContent"]) != record["baseContentDigest"]:
        raise ValueError("Content base digest mismatch.")
    changes = record["changes"]
    if not isinstance(changes, list) or not 1 <= len(changes) <= 128:
        raise ValueError("Content proposal change bound exceeded.")
    for change in changes:
        _change(change)
    keys = [entry_key(change) for change in changes]
    if len(set(keys)) != len(keys) or keys != sorted(keys):
        raise ValueError("Content change keys must be unique and sorted.")
