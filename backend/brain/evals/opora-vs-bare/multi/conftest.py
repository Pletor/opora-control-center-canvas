"""Importní cesty pro testy evalu o víc sezeních (multi/ a nadřazený harness)."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
MULTI = Path(__file__).resolve().parent
for p in (str(MULTI.parent), str(MULTI)):
    if p not in sys.path:
        sys.path.insert(0, p)
