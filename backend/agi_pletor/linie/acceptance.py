"""Nasazené SHA (kontrakt velin-git-linie §5): `<pletor>/linie/deployed.json` `{sha, at}`; zapisuje jen člověk.

Přijetí revize se přesunulo k ticketu (`tickets.work.acceptance`, docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §2).
"""
import json
import re
from pathlib import Path

FILE = "deployed.json"
SHA = re.compile(r"[0-9a-f]{7,40}")


def _path(folder):
    return Path(folder) / "linie" / FILE


def read_deployed(folder):
    """`{sha, at}`, nebo None (chybějící či vadný soubor = nic nenasazeno)."""
    try:
        value = json.loads(_path(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) and isinstance(value.get("sha"), str) else None


def set_deployed(folder, sha, now):
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("sha je 7–40 znaků 0-9a-f.")
    path = _path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    value = {"sha": sha, "at": now}
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)  # celý soubor, nebo nic
    return value
