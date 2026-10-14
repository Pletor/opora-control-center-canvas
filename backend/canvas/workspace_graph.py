"""Úložiště grafu plátna pro Git pracovní prostor: v datech plátna, nikdy v cílovém repu.

Cílové repo nese jen kód. Graf pracovního prostoru leží v
`projects/<id>/canvas/workspaces/<workspace>/graph.json` vedle `project.sqlite`.
Starší verze plátna psaly `opora-canvas.json` do kořene worktree; ten se jednorázově
převezme: dokud v datech graf není, čte se starý soubor, a první uložení ho převezme do dat.
Starý soubor ve worktree se nemaže ani nepřepisuje.
"""

import os
import uuid

LEGACY_GRAPH_FILE = "opora-canvas.json"
MAX_GRAPH_BYTES = 2_000_000


def read_graph_file(path):
    """Surový text grafu, nebo None, když soubor neexistuje."""
    if path.is_symlink():
        raise ValueError("Graf nesmí být symbolický odkaz.")
    if not path.exists():
        return None
    if path.stat().st_size > MAX_GRAPH_BYTES:
        raise ValueError("Graf je příliš velký.")
    return path.read_text(encoding="utf-8")


def read_workspace_graph(stored, worktree):
    """(raw, origin) pro pracovní prostor. origin: "data", "legacy" (převzetí čeká na uložení) nebo None."""
    raw = read_graph_file(stored)
    if raw is not None:
        return raw, "data"
    legacy = read_graph_file(worktree / LEGACY_GRAPH_FILE)
    return (legacy, "legacy") if legacy is not None else (None, None)


def write_workspace_graph(stored, text):
    """Atomický zápis do dat plátna (tmp ve stejné složce + os.replace)."""
    stored.parent.mkdir(parents=True, exist_ok=True)
    temp = stored.with_name(".graph-" + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, stored)
    finally:
        temp.unlink(missing_ok=True)
