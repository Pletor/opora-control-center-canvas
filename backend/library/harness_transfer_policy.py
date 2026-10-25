"""Reviewed, sanitized transfer metadata; this policy never fetches content or grants eligibility."""
import os
import re

from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_execution_observer_auth import strict_json
from backend.canvas.opora_verification_validation import identity

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/+\-]{0,199}")
_DIGEST = re.compile(r"[a-f0-9]{64}")
_ENV = "OPORA_HARNESS_TRANSFER"
_LIMIT = 64 * 1024


def _identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid Harness transfer identifier.")
    return value


def _parse(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > _LIMIT:
        raise ValueError("Harness transfer policy exceeds 64 KiB or is not text.")
    document = strict_json(raw)
    if not isinstance(document, dict) or set(document) != {"schema", "publications"} or document["schema"] != "harness.transfer-policy/1":
        raise ValueError("Invalid Harness transfer policy fields or schema.")
    entries = document["publications"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
        raise ValueError("Harness transfer policy requires 1 to 16 publications.")

    checked, publication_ids = [], set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "problem", "candidate", "sources"}:
            raise ValueError("Invalid Harness transfer publication fields.")
        publication_id = _identifier(entry["id"])
        problem = _identifier(entry["problem"])
        if publication_id in publication_ids:
            raise ValueError("Duplicate Harness transfer publication ID.")
        publication_ids.add(publication_id)

        candidate = entry["candidate"]
        if not isinstance(candidate, dict) or set(candidate) != {"id", "digest"}:
            raise ValueError("Invalid Harness transfer candidate fields.")
        candidate_id = _identifier(candidate["id"])
        if not isinstance(candidate["digest"], str) or not _DIGEST.fullmatch(candidate["digest"]):
            raise ValueError("Invalid Harness transfer candidate digest.")

        sources = entry["sources"]
        if not isinstance(sources, list) or not 1 <= len(sources) <= 8:
            raise ValueError("Harness transfer publication requires 1 to 8 sources.")
        normalized_sources, source_keys = [], set()
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"project", "workspace", "verificationId"}:
                raise ValueError("Invalid Harness transfer source fields.")
            scope(source)
            identity(source["verificationId"])
            key = (source["project"], source["workspace"], source["verificationId"])
            if key in source_keys:
                raise ValueError("Duplicate Harness transfer source.")
            source_keys.add(key)
            normalized_sources.append(dict(source))

        checked.append({"id": publication_id, "problem": problem,
                        "candidate": {"id": candidate_id, "digest": candidate["digest"]},
                        "sources": normalized_sources})
    return checked


def publication(identifier):
    """Return one fully validated publication from server-owned configuration."""
    raw = os.environ.get(_ENV, "")
    if not raw:
        raise ValueError("Harness transfer policy is disabled.")
    requested = _identifier(identifier)
    entries = _parse(raw)  # Validate every entry before selecting any one publication.
    for entry in entries:
        if entry["id"] == requested:
            return entry
    raise ValueError("Harness transfer publication is unavailable.")
