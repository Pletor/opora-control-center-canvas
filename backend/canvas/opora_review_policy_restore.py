"""Old architecture backups must never discard policy or observation-attempt authority."""
TABLES = ("opora_review_policies", "opora_review_policy_refs", "opora_review_attempts")


def refuse_policy_restore(db):
    if any(db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in TABLES):
        raise ValueError("Architecture backup restore is unavailable after review policy or observation attempt history.")
