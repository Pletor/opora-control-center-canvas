"""Old backups cannot restore consumed attempts or revoke the permanent budget fences."""

from database.schema.opora_execution_budget_schema import BUDGET_TABLES


def refuse_budget_restore(db):
    if any(db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in BUDGET_TABLES):
        raise ValueError(
            "Architecture backup restore is unavailable after execution budget authority."
        )
