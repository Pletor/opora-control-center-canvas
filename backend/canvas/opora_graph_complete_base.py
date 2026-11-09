"""Explicit immutable adoption of legacy content, using native content proposal semantics."""
from backend.canvas.graph import digest
from backend.canvas.opora_content_changes import manifest_entries
from backend.canvas.opora_content_sources import capture_content
from backend.canvas.opora_content_validation import validate_record
from database.repositories.opora_changesets import ChangesetRepository


def observe(canvas, project, workspace, graph):
    repo = ChangesetRepository(canvas.db_for(project), project, workspace)
    missing = manifest_entries(repo, repo.head()) is None
    entries = capture_content(canvas, project, workspace, graph)[0] if missing else []
    return {"requiresAdoption": missing, "digest": digest(entries), "entries": entries}


def validate(base, project, workspace):
    if (not isinstance(base, dict) or set(base) != {"requiresAdoption", "digest", "entries"}
            or type(base["requiresAdoption"]) is not bool or digest(base["entries"]) != base["digest"]
            or (not base["requiresAdoption"] and base["entries"] != [])):
        raise ValueError("Invalid reviewed content baseline.")
    validate_record({"schemaVersion": 1, "kind": "content-manifest", "project": project,
                     "workspace": workspace, "entries": base["entries"]}, manifest=True)
