"""Společné argumenty měřicích skriptů výkonu (karta P1, sektor Výkon a škálování).

Skripty měří jen na kopii dat (`data_copy.py`), nikdy na živých datech (`.data/production`
ani na datové složce z opora.toml / opora.local.toml, která může ležet mimo repozitář):
některé z nich na kopii zapisují (verze, rozhodnutí, pipeline).
"""
import argparse
import statistics
import sys
from pathlib import Path

# Windows konzole (cp1250) neumí znaky jako ≤; výstup měření jde vždy v UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_DATA = REPO_ROOT / ".data" / "production"
# Výchozí měřený projekt Ample (960 MB, 177 verzí) a karta s bohatou historií zpráv.
AMPLE_PROJECT = "cc5f34ec07cd455ca5ad1a69af19022b"
AMPLE_NODE = "97cc644b-bba8-40a2-add3-257525c7781f"
WORKSPACE = "draft"


def configured_data():
    """Datová složka, na které běží aplikace podle opora.toml + opora.local.toml ([app] data)."""
    use_repo()
    from tools.opora import load_config, resolve

    try:
        return (REPO_ROOT / resolve(load_config())["data"]).resolve()
    except (OSError, ValueError, KeyError):
        return None


def copy_dir(value):
    """Adresář kopie dat; živá data odmítne, ať měření nikdy nesáhne na produkci."""
    path = Path(value).resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Adresář dat {value} neexistuje.")
    for live in (LIVE_DATA.resolve(), configured_data()):
        if live is not None and (path == live or live in path.parents):
            raise argparse.ArgumentTypeError(
                f"Měř na kopii dat (tools/perf/data_copy.py), ne na živých datech {live}.")
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


def percentiles(values):
    """p50, p95 a p99 v ms; z méně než dvou vzorků vrátí jedinou hodnotu třikrát."""
    if len(values) < 2:
        value = values[0] if values else 0.0
        return value, value, value
    cuts = statistics.quantiles(values, n=100, method="inclusive")
    return statistics.median(values), cuts[94], cuts[98]
