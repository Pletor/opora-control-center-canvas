"""Zpráva a kontext plátna (docs/asistent.md §6).

UI ke zprávě přiloží, na co se uživatel dívá. Backend kontext ověří a vloží před text jako
`<opora_context>{json}</opora_context>`; je to údaj, ne pokyn. Do událostí jde jen text.
"""

from __future__ import annotations

import json

MAX_TEXT = 20000
MAX_TITLE = 80
MAX_IDS = 50
MAX_ID = 128
ENVIRONMENTS = ("project", "editor", "live")
CONTEXT_KEYS = ("projectId", "workspace", "layerId", "selectedNodeIds", "environment")


def _short_string(value, label, nullable=False):
    if nullable and (value is None or value == ""):
        return None  # kořenová vrstva plátna nemá ID
    if not isinstance(value, str) or not value or len(value) > MAX_ID or any(ord(c) < 32 or c in "<>" for c in value):
        raise ValueError(f"Kontext zprávy: neplatné pole {label}.")
    return value


def validate_text(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Zpráva asistentovi nesmí být prázdná.")
    if len(text) > MAX_TEXT:
        raise ValueError(f"Zpráva asistentovi může mít nejvýše {MAX_TEXT} znaků.")
    return text


def validate_title(title):
    """Ručně zadaný titulek úkolu: po oříznutí 1–80 znaků bez řídicích znaků."""
    clean = title.strip() if isinstance(title, str) else ""
    if not clean or len(clean) > MAX_TITLE or any(ord(c) < 32 or ord(c) == 127 for c in clean):
        raise ValueError(f"Titulek úkolu má mít 1 až {MAX_TITLE} znaků bez řídicích znaků.")
    return clean


def validate_context(context):
    if context is None:
        return None
    if not isinstance(context, dict):
        raise ValueError("Kontext zprávy musí být objekt.")
    unknown = set(context) - set(CONTEXT_KEYS)
    if unknown:
        raise ValueError("Kontext zprávy obsahuje neznámé pole: " + ", ".join(sorted(unknown)) + ".")
    clean = {}
    if "projectId" in context:
        clean["projectId"] = _short_string(context["projectId"], "projectId")
    if "workspace" in context:
        clean["workspace"] = _short_string(context["workspace"], "workspace")
    if "layerId" in context:
        clean["layerId"] = _short_string(context["layerId"], "layerId", nullable=True)
    if "selectedNodeIds" in context:
        ids = context["selectedNodeIds"]
        if not isinstance(ids, list) or len(ids) > MAX_IDS:
            raise ValueError(f"Kontext zprávy: selectedNodeIds je seznam nejvýše {MAX_IDS} ID.")
        clean["selectedNodeIds"] = [_short_string(item, "selectedNodeIds") for item in ids]
    if "environment" in context:
        if context["environment"] not in ENVIRONMENTS:
            raise ValueError("Kontext zprávy: environment je project, editor nebo live.")
        clean["environment"] = context["environment"]
    return clean


def compose(text, context):
    """Text, který jde na stdin procesu."""
    if not context:
        return text
    payload = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    block = f"<opora_context>{payload}</opora_context>"
    # Skilly jen pro uživatele (/wayfinder, /grill-me) CLI pozná, jen když zpráva lomítkem začíná.
    if text.lstrip().startswith("/"):
        return f"{text}\n\n{block}"
    return f"{block}\n\n{text}"
