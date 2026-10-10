"""Společné argumenty měřicích skriptů výkonu (karta P1, sektor Výkon a škálování).

Skripty měří jen na kopii dat (`data_copy.py`), nikdy na živém `.data/production`:
některé z nich na kopii zapisují (verze, rozhodnutí, pipeline).
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_DATA = REPO_ROOT / ".data" / "production"
# Výchozí měřený projekt Ample (960 MB, 177 verzí) a karta s bohatou historií zpráv.
AMPLE_PROJECT = "cc5f34ec07cd455ca5ad1a69af19022b"
AMPLE_NODE = "97cc644b-bba8-40a2-add3-257525c7781f"
WORKSPACE = "draft"


def copy_dir(value):
    """Adresář kopie dat; živá data odmítne, ať měření nikdy nesáhne na produkci."""
    path = Path(value).resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Adresář dat {value} neexistuje.")
    live = LIVE_DATA.resolve()
    if path == live or live in path.parents:
        raise argparse.ArgumentTypeError(
            "Měř na kopii dat (tools/perf/data_copy.py), ne na .data/production.")
    return str(path)


def parser(description):
    result = argparse.ArgumentParser(description=description)
    result.add_argument("data", type=copy_dir, help="adresář kopie dat")
    result.add_argument("--project", default=AMPLE_PROJECT)
    result.add_argument("--workspace", default=WORKSPACE)
    result.add_argument("--node", default=AMPLE_NODE)
    return result


def use_repo():
    """Moduly backendu importovatelné i při spuštění `python tools/perf/<skript>.py`."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
