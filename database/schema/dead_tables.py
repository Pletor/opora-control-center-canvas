"""Úklid mrtvých tabulek v `project.sqlite` (audit sirotků, dávka B8).

Tabulky zůstaly ve starých DB po odstraněném vázání agentů na uzly; žádný kód je nečte ani nepíše
a při auditu 23. 10. měly všude 0 řádků. Krok je idempotentní a běží při každém otevření projektu
(`initialize_project_schema`), stejně jako ostatní doplnění schématu.

Pojistky: tabulka s daty zůstane (nic se neztratí potichu) a projekt zapsaný do SQL kontextu
(`opora_context_coverage`) se nechá být, protože každé DDL posune `PRAGMA schema_version`,
na které je jeho pokrytí připnuté (`database/repositories/opora_context_events.py`).

`drop_retired_tables` maže tabulky smazaných funkcí (`RETIRED_TABLES`) i s daty: kód je už nečte ani nepíše
a zpětná kompatibilita se nedrží. Pojistka SQL kontextu platí stejně.
"""

DEAD_TABLES = ("node_sessions", "agent_bindings", "agent_binding_scopes", "agent_activity_entries")
RETIRED_TABLES = ("heart_tasks",)  # stará fronta úkolů mozku; nahradil ji ticket práce (novy-zaklad §4)


def _tables(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def drop_dead_tables(db):
    """Smaže prázdné mrtvé tabulky (s jejich indexy) a vrátí jména těch, které smazal."""
    tables = _tables(db)
    present = [name for name in DEAD_TABLES if name in tables]
    if not present:
        return []
    if "opora_context_coverage" in tables and db.execute(
            "SELECT 1 FROM opora_context_coverage LIMIT 1").fetchone():
        return []
    dropped = []
    for name in present:
        if db.execute(f'SELECT 1 FROM "{name}" LIMIT 1').fetchone():
            continue
        db.execute(f'DROP TABLE IF EXISTS "{name}"')
        dropped.append(name)
    return dropped


def drop_retired_tables(db):
    """Smaže tabulky smazaných funkcí i s daty a indexy (`DROP TABLE IF EXISTS`); vrátí jména smazaných."""
    tables = _tables(db)
    present = [name for name in RETIRED_TABLES if name in tables]
    if not present or ("opora_context_coverage" in tables and db.execute(
            "SELECT 1 FROM opora_context_coverage LIMIT 1").fetchone()):
        return []
    for name in present:
        db.execute(f'DROP TABLE IF EXISTS "{name}"')
    return present
