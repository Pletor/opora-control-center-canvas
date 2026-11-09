"""Recompute execution input identity exclusively from its immutable snapshot."""
from backend.canvas.graph import digest

SCHEMA = "opora.execution-inputs/1"


def context_version(snapshot):
    specification = digest(snapshot["specification"])
    if "inputContextSchema" not in snapshot:
        return specification
    if snapshot["inputContextSchema"] != SCHEMA:
        raise ValueError("Unknown execution input context schema.")
    scopes = []
    for item in snapshot.get("affectedElements", []):
        scope = item["scope"]
        if scope["contextVersion"] != digest(scope["specification"]):
            raise ValueError("Affected execution scope identity is invalid.")
        scopes.append(scope["contextVersion"])
    return digest({"specification": specification, "affectedScopes": scopes,
                   "researchEvidence": snapshot.get("researchEvidence"),
                   "storyboards": snapshot["storyboards"]})
