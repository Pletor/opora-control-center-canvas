"""Rozdělení fragmentu bez ztráty zadání: texty dětí spojené `SEPARATOR` == text rodiče.

`parts` zadá agent nebo člověk ručně; `splitter: "heading-number"` rozdělí text před každým
řádkem s číslem kapitoly (`3.37 Version activation`), který začíná po prázdném řádku. Jen tak
jde invariant spojení splnit vždy: číslo uvnitř odstavce zůstane v předchozí části.
"""

import re

from backend.editor.brief_vault.brief_vault_model import MAX_TITLE, fail, text_of

SEPARATOR = "\n\n"
SPLITTERS = ("heading-number",)
MAX_PARTS = 500
HEADING = re.compile(r"\d+(\.\d+)* \S")


def _title_of(text, fallback):
    first = next((line.strip() for line in text.split("\n") if line.strip()), "")
    return (first or fallback)[:MAX_TITLE]


def heading_parts(text):
    """Části textu podle čísel kapitol; úvod před první kapitolou je samostatná část."""
    starts = [0] if HEADING.match(text) else []
    position = text.find(SEPARATOR)
    while position != -1:
        start = position + len(SEPARATOR)
        if HEADING.match(text, start) and (not starts or starts[-1] != start):
            starts.append(start)
        position = text.find(SEPARATOR, position + 1)
    if not starts:
        return []
    bounds = ([0] if starts[0] != 0 else []) + starts
    parts = []
    for index, start in enumerate(bounds):
        end = bounds[index + 1] - len(SEPARATOR) if index + 1 < len(bounds) else len(text)
        chunk = text[start:end]
        parts.append({"title": _title_of(chunk, "Úvod" if index == 0 and start not in starts else "Část"), "text": chunk})
    return parts


def split_parts(payload, parent_text):
    """Části ze zápisu `split`; při nesouladu spojení s textem rodiče ValueError (HTTP 409)."""
    if ("parts" in payload) == ("splitter" in payload):
        fail("split očekává buď parts, nebo splitter.")
    if "splitter" in payload:
        if payload["splitter"] not in SPLITTERS:
            fail("splitter umí jen heading-number.")
        parts = heading_parts(parent_text)
    else:
        parts = payload["parts"]
        if not isinstance(parts, list):
            fail("parts musí být pole {title, text}.")
        for part in parts:
            if not isinstance(part, dict) or set(part) != {"title", "text"}:
                fail("každá část má právě title a text.")
            text_of(part["title"], MAX_TITLE, "title části", allow_empty=False)
            text_of(part["text"], 64000, "text části")
    if len(parts) < 2 or len(parts) > MAX_PARTS:
        fail(f"rozdělení potřebuje 2 až {MAX_PARTS} částí (nalezeno {len(parts)}).")
    if SEPARATOR.join(part["text"] for part in parts) != parent_text:
        fail("spojení textů částí (oddělovač prázdný řádek) se neshoduje s textem fragmentu; zadání by se ztratilo.")
    return parts
