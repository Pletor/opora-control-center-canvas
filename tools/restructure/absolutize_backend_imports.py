"""Přepíše `from .mod import X` na `from backend.mod import X` ve všech backend/*.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(rb"^(\s*)from \.(\w+) import", re.M)
PATTERN_BARE = re.compile(rb"^(\s*)from \. import (.+)$", re.M)
changed = 0
for path in sorted((ROOT / "backend").rglob("*.py")):
    raw = path.read_bytes()
    new = PATTERN.sub(rb"\1from backend.\2 import", raw)
    new = PATTERN_BARE.sub(rb"\1from backend import \2", new)
    if new != raw:
        path.write_bytes(new)
        changed += 1
print(f"rewritten files: {changed}")
