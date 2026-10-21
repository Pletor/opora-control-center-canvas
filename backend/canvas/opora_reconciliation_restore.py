"""Old architecture backups cannot erase durable subscription authority or facts."""
from database.schema.opora_reconciliation_jobs import JOB_TABLES
from database.schema.opora_reconciliation_schema import RECONCILIATION_TABLES


def refuse_reconciliation_restore(db):
    for table in (*RECONCILIATION_TABLES, *JOB_TABLES):
        if db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            raise ValueError("Architecture backup restore is unavailable after durable reconciliation history.")
