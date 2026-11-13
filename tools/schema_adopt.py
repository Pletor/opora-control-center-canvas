"""Stav generací schématu jedné SQLite databáze a vědomé uznání mezery v jejich řetězci.

    uv run python tools/schema_adopt.py --db <project.sqlite|registry.sqlite>
    uv run python tools/schema_adopt.py --db <cesta> --from K --to M --author "<kdo>" --reason "<proč>" [--write]

Proč: piny SQL kontextu (pokrytí projektu, vazby registru) drží verzi schématu z chvíle zápisu.
Aplikace každé své DDL dosvědčí jako generaci `od → do`; pin projde, když od něj vede souvislý
řetězec k aktuální `PRAGMA schema_version`. DDL mimo aplikaci nechá mezeru a pin odmítne.
Tady se člověk i agent podívá, co se stalo: verze teď, piny, celý řetězec (kdo, kdy, proč),
kde je mezera a jaký příkaz by ji uznal. Uznání (`--from/--to`) je výslovný záznam s pravdivým
autorem a důvodem; bez `--write` je to suchý běh (transakce se vrátí). Nic se nepřepisuje ani
nemaže. Kontrakt: docs/oporahub-content-changes.md („Upgrade projektu s dřívějším kontextem v2“)
a docs/oporahub-sparse-context.md; mechanika v database/repositories/schema_generations.py.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.repositories import opora_context_bindings, opora_context_events
from database.repositories.schema_generations import adopt, gap, rows


def _select(db, sql):
    try:
        return [tuple(row) for row in db.execute(sql)]
    except sqlite3.OperationalError:  # tabulka v této databázi není
        return []


def _pins(db):
    coverage = [("pokrytí projektu", project, version, lambda project=project: opora_context_events.checkpoint(db, project))
                for project, version in _select(db, "SELECT project_id,schema_version FROM opora_context_coverage")]
    binding = [("vazba registru", f"{project}/{workspace}", version,
                lambda project=project, workspace=workspace: opora_context_bindings.checkpoint(db, project, workspace))
               for project, workspace, version in _select(db, "SELECT project_id,workspace_id,schema_version FROM opora_context_bindings")]
    return coverage + binding


def _verdict(check):
    try:
        check()
        return "projde"
    except ValueError as error:
        return "neprojde: " + str(error)


def describe(db, path):
    current = db.execute("PRAGMA schema_version").fetchone()[0]
    lines = [f"Databáze: {path}", f"PRAGMA schema_version teď: {current}", "", "Řetězec generací (od → do, kdo, kdy, proč):"]
    lines += [f"  {start} → {end}  {author}  {at}  {reason}" for start, end, author, reason, at in rows(db)] or ["  (žádné zapsané generace)"]
    lines += ["", "Piny SQL kontextu:"]
    pins = _pins(db)
    if not pins:
        lines.append("  (žádné piny v této databázi)")
    for kind, key, version, check in pins:
        missing = gap(db, version)
        lines.append(f"  {kind} {key}: pin na verzi {version}, checkpoint {_verdict(check)}")
        if missing:
            start, until = missing
            lines.append(f"    mezera: řetězec od pinu končí na {start}, nedosvědčený článek {start}→{until}. Uznat jen vědomě:")
            lines.append(f'    python tools/schema_adopt.py --db "{path}" --from {start} --to {until} --author "<kdo>" --reason "<proč>" --write')
    return lines


def run(path, start=None, end=None, author=None, reason=None, write=False):
    if not Path(path).is_file():
        raise ValueError("Databáze neexistuje.")
    if (start is None) != (end is None) or (write and start is None):
        raise ValueError("Uznání mezery potřebuje --from i --to.")
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.execute("PRAGMA recursive_triggers=ON")
        lines = describe(db, path)
        if start is None:
            return lines, all(_verdict(check) == "projde" for *_, check in _pins(db))
        # A row beyond the live version would pre-authorise future foreign DDL.
        if end > db.execute("PRAGMA schema_version").fetchone()[0]:
            raise ValueError("Generace nesmí mířit za aktuální PRAGMA schema_version.")
        db.execute("BEGIN IMMEDIATE")
        try:
            adopt(db, start, end, author or "", reason or "")
            verdicts = [(kind, key, _verdict(check)) for kind, key, _, check in _pins(db)]
            db.execute("COMMIT" if write else "ROLLBACK")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        lines += ["", ("Zapsáno" if write else "Suchý běh (nic nezapsáno), po uznání") + f" {start} → {end} ({author}: {reason}):"]
        lines += [f"  {kind} {key}: checkpoint {verdict}" for kind, key, verdict in verdicts]
        return lines, all(verdict == "projde" for *_, verdict in verdicts)
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True)
    parser.add_argument("--from", dest="start", type=int)
    parser.add_argument("--to", dest="end", type=int)
    parser.add_argument("--author")
    parser.add_argument("--reason")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # Windows konzole v cp1250 neumí šipku →
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        lines, ok = run(args.db, args.start, args.end, args.author, args.reason, args.write)
    except ValueError as error:
        print("Chyba: " + str(error))
        return 2
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
