"""No historical restore can erase any populated formal evidence table."""
from database.schema.opora_verification_schema import TABLES


def refuse_verification_restore(db):
    existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if any(db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in TABLES if table in existing):
        raise ValueError("Architecture backup restore is unavailable after formal verification history.")
