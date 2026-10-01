"""Striktní validace Hook control v1: žádné cesty ani identity z agentního textu."""

import os
import re
import uuid
from pathlib import Path

from backend.project.workspace.workspace_sources import relative_path, reparse

MAX_EVENT_BYTES = 128_000
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)
PATH_KEYS = ("file_path", "path", "notebook_path")
WRITE_TOOLS = frozenset({"Write", "Edit", "NotebookEdit"})
SCOPED_TOOLS = WRITE_TOOLS | frozenset({"Read", "Glob", "Grep", "LSP", "Lsp"})


def session_id(value):
    if not isinstance(value, str) or not UUID.fullmatch(value):
        raise ValueError("sessionId musí být UUID pro nový běh.")
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("sessionId musí být UUID pro nový běh.") from exc
    return value


def allowed_paths(value):
    if not isinstance(value, list) or not value or len(value) > 50:
        raise ValueError("allowedPaths musí být neprázdné pole nejvýše 50 relativních cest.")
    result = []
    for path in value:
        relative_path(path)
        if not path:
            raise ValueError("Kořen workspace nelze povolit jako allowedPath.")
        if path.casefold() not in {item.casefold() for item in result}:
            result.append(path)
    return result


def overlaps(left, right):
    left, right = left.casefold().strip("/"), right.casefold().strip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def is_under(path, prefixes):
    candidate = path.casefold().strip("/")
    return any(candidate == prefix.casefold().strip("/") or candidate.startswith(prefix.casefold().strip("/") + "/")
               for prefix in prefixes)


def safe_target(root, candidate):
    """Cesta z hooku je relativní a neprochází odkazy/junctions ani control soubory."""
    relative_path(candidate)
    path = root
    for part in candidate.split("/") if candidate else []:
        path = path / part
        if path.exists() and reparse(path):
            raise ValueError("Odkazy a junctiony nejsou povolené.")
    # Neexistující cíl se kontroluje přes rodiče; resolve nesmí dovolit traversal.
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("Cesta opouští pracovní prostor.")
    return candidate


def protected(path):
    lower = path.casefold().strip("/")
    return lower in {".claude/settings.json", ".claude/settings.local.json"} or lower.startswith(".opora-control/")


def event_shape(event):
    if not isinstance(event, dict) or len(event) > 30:
        raise ValueError("Hook event musí být omezený JSON objekt.")
    name = event.get("hook_event_name")
    if name not in {"SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop"}:
        raise ValueError("Neplatný hook event.")
    if not isinstance(event.get("session_id"), str) or not isinstance(event.get("cwd"), str):
        raise TypeError("Hook event nemá session_id nebo cwd.")
    if name != "Stop" and not isinstance(event.get("tool_name", ""), str):
        raise TypeError("Hook event nemá tool_name.")
    data = event.get("tool_input", {})
    if data is not None and (not isinstance(data, dict) or len(data) > 30):
        raise ValueError("tool_input musí být omezený objekt.")
    return name, event.get("tool_name", ""), data or {}


def cwd_matches(root, cwd):
    try:
        return Path(cwd).resolve() == root
    except (OSError, RuntimeError):
        return False


def bounded_text(value, limit=240):
    if not isinstance(value, str):
        return ""
    return value.replace("\x00", " ").replace("\r", " ").replace("\n", " ")[:limit]


def endpoint_is_loopback(value):
    return isinstance(value, str) and value.startswith("http://127.0.0.1:") and "/api/agent-hooks" in value


def private_file(path):
    if os.name != "nt":
        path.chmod(0o600)
