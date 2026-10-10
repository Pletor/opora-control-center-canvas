"""Kopie dat pro měření: SQLite přes backup API (zdroj jen pro čtení), ostatní soubory kopií.

`uv run python tools/perf/data_copy.py [.data/production] [.data/perf-copy]`.
Cíl musí být prázdný nebo neexistující a ležet mimo zdroj; výchozí `.data/perf-copy` je v .gitignore.
Soubory -wal, -shm a -journal se nekopírují: backup přenese konzistentní stav databáze.
"""
import argparse
import os
import shutil
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / ".data" / "production"
DEFAULT_TARGET = REPO_ROOT / ".data" / "perf-copy"
SKIPPED = ("-wal", "-shm", "-journal")


def backup_sqlite(source, target):
    """Konzistentní kopie SQLite přes backup API: zahrne i potvrzená data, která jsou zatím jen
    v souboru -wal (běžící server), a zdroj otevře jen pro čtení. Prostá kopie souboru je minula."""
    reader = sqlite3.connect(f"{Path(source).resolve().as_uri()}?mode=ro", uri=True)
    try:
        writer = sqlite3.connect(target)
        try:
            reader.backup(writer)
        finally:
            writer.close()
    finally:
        reader.close()


def copy_data(source, target):
    """Zkopíruje adresář dat `source` do `target`; vrátí počet zkopírovaných souborů."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_dir():
        raise ValueError(f"Zdroj {source} neexistuje.")
    if target == source or source in target.parents or target in source.parents:
        raise ValueError("Cíl kopie nesmí být zdroj, ležet v něm ani ho obsahovat.")
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"Cíl {target} není prázdný; smaž ho ručně nebo zvol jiný.")
    copied = 0
    for root, _dirs, files in os.walk(source):
        for name in files:
            if name.endswith(SKIPPED):
                continue
            origin = Path(root) / name
            destination = target / origin.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith(".sqlite"):
                backup_sqlite(origin, destination)
            else:
                shutil.copy2(origin, destination)
            copied += 1
    return copied


def main(argv=None):
    cli = argparse.ArgumentParser(description="Kopie dat pro měření výkonu.")
    cli.add_argument("source", nargs="?", default=str(DEFAULT_SOURCE))
    cli.add_argument("target", nargs="?", default=str(DEFAULT_TARGET))
    args = cli.parse_args(argv)
    print(f"ok: {copy_data(args.source, args.target)} souborů v {Path(args.target).resolve()}")


if __name__ == "__main__":
    main()
