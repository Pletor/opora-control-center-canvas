"""Additive facts for the merge gate rules (docs/oporahub-review-jobs.md, "Pravidla brány").

`opora_review_self_checks` holds per-head self-check evidence an agent adds after its execution
result (rebase or review fixes move the head). `opora_review_base_observations` holds the latest
read-only GitHub observation of a PR head against the current base branch head and of the PR body.
`opora_review_lens` holds optional PR Lens evidence per execution and slot: a PR head SHA, or `area` for the
pre-code map of the accepted plan revision (`head_sha` NULL) (backend/canvas/opora_review_lens.py).
`ensure_review_job_kind` upgrades review job tables created before the `kind` column existed."""
TABLES = ("opora_review_self_checks", "opora_review_base_observations", "opora_review_lens")
SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_review_self_checks(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL, head_sha TEXT NOT NULL,
 record TEXT NOT NULL, by TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,execution_id,head_sha));
CREATE TABLE IF NOT EXISTS opora_review_base_observations(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, repository TEXT NOT NULL, number INTEGER NOT NULL,
 head_sha TEXT NOT NULL, observation TEXT NOT NULL, observed_at REAL NOT NULL,
 PRIMARY KEY(project_id,workspace_id,repository,number));
CREATE TABLE IF NOT EXISTS opora_review_lens(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL, slot TEXT NOT NULL,
 node_id TEXT NOT NULL, kind TEXT NOT NULL, head_sha TEXT, accepted_revision TEXT NOT NULL,
 record TEXT NOT NULL, by TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,execution_id,slot));
CREATE INDEX IF NOT EXISTS opora_review_lens_node ON opora_review_lens(project_id,workspace_id,node_id);
"""

_JOBS = "opora_review_jobs"
_COLUMNS = ("project_id,workspace_id,job_id,execution_id,node_id,repository,number,base_sha,head_sha,round,"
            "since_sha,risk_tier,risk,required_approvals,finders,voters,required_votes,phase,candidates,"
            "created_at,updated_at,completed_at")


def ensure_review_job_kind(db):
    """Rebuild a pre-`kind` review job table once so one head can hold a code and a security job.

    SQLite cannot change a UNIQUE constraint in place; the copy keeps every row as `kind='code'`."""
    columns = {row[1] for row in db.execute(f"PRAGMA table_info({_JOBS})")}
    if not columns or "kind" in columns:
        return
    from database.schema.opora_review_job_schema import SCHEMA as JOB_SCHEMA
    create = JOB_SCHEMA.split("CREATE TABLE IF NOT EXISTS opora_review_tasks", 1)[0]
    own = not db.in_transaction  # executescript would commit, so each statement runs alone
    if own:
        db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(f"ALTER TABLE {_JOBS} RENAME TO {_JOBS}_pre_kind")
        for statement in (part.strip() for part in create.split(";")):
            if statement:
                db.execute(statement)
        db.execute(f"INSERT INTO {_JOBS}({_COLUMNS},kind) SELECT {_COLUMNS},'code' FROM {_JOBS}_pre_kind")
        db.execute(f"DROP TABLE {_JOBS}_pre_kind")
        if own:
            db.execute("COMMIT")
    except Exception:
        if own:
            db.execute("ROLLBACK")
        raise
