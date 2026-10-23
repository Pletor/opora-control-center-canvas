"""Úklid mrtvých tabulek v `project.sqlite` (audit sirotků, dávka B8).

Tabulky zůstaly ve starých DB po odstraněném vázání agentů na uzly; žádný kód je nečte ani nepíše
a při auditu 23. 10. měly všude 0 řádků. Krok je idempotentní a běží při každém otevření projektu
(`initialize_project_schema`), stejně jako ostatní doplnění schématu.

Pojistky: tabulka s daty zůstane (nic se neztratí potichu) a projekt zapsaný do SQL kontextu
(`opora_context_coverage`) se nechá být, protože každé DDL posune `PRAGMA schema_version`,
na které je jeho pokrytí připnuté (`database/repositories/opora_context_events.py`).
"""

DEAD_TABLES = ("node_sessions", "agent_bindings", "agent_binding_scopes", "agent_activity_entries")


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
