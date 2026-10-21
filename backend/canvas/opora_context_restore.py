"""Historical backup restore cannot erase even orphaned context journal evidence."""
from database.schema.opora_context_event_schema import TABLES
from database.schema.opora_execution_context_schema import TABLES as PRIVATE_TABLES


def refuse_context_restore(db):
    existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if any(db.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone()
           for table in (*TABLES, *PRIVATE_TABLES) if table in existing):
        raise ValueError("Architecture backup restore is unavailable after SQL context history.")
