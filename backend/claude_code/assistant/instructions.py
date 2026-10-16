"""Výchozí Pokyny asistenta (docs/asistent.md §14.1): text ze souboru `instructions.md` vedle modulu.

Malý modul bez závislostí na zbytku asistenta, aby ho `memory_service` mohl importovat bez cyklu.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_FILE = Path(__file__).with_name("instructions.md")
_cache = {}


def default_assistant_instructions():
    """Výchozí pokyny (UTF-8); čtou se jednou a drží se v modulu."""
    if "text" not in _cache:
        _cache["text"] = DEFAULT_FILE.read_text(encoding="utf-8")
    return _cache["text"]
