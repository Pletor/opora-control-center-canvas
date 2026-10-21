"""Pre-`kind` review job tables upgrade once; a head can then hold a code and a security job."""
import sqlite3

import pytest

from database.schema.opora_review_gate_schema import ensure_review_job_kind
from database.schema.project_initialization import initialize_project_schema

OLD = """CREATE TABLE opora_review_jobs(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, job_id TEXT NOT NULL,
 execution_id TEXT NOT NULL, node_id TEXT NOT NULL, repository TEXT NOT NULL, number INTEGER NOT NULL,
 base_sha TEXT, head_sha TEXT NOT NULL, round INTEGER NOT NULL, since_sha TEXT,
 risk_tier TEXT NOT NULL, risk TEXT NOT NULL, required_approvals INTEGER NOT NULL,
 finders INTEGER NOT NULL, voters INTEGER NOT NULL, required_votes INTEGER NOT NULL,
 phase TEXT NOT NULL, candidates TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 completed_at TEXT,
 PRIMARY KEY(project_id,workspace_id,job_id),
 UNIQUE(project_id,workspace_id,repository,number,head_sha))"""
ROW = ("p", "w", "rj_1", "e", "card", "owner/repo", 7, None, "c" * 40, 1, None, "low", "{}", 0, 3, 3, 2, "find",
       "[]", "t", "t", None)


def test_old_review_job_table_is_rebuilt_with_kind_and_keeps_rows():
    db = sqlite3.connect(":memory:")
    db.execute(OLD)
    db.execute("INSERT INTO opora_review_jobs VALUES(" + ",".join("?" * len(ROW)) + ")", ROW)
    db.commit()
    initialize_project_schema(db)
    assert db.execute("SELECT job_id,kind FROM opora_review_jobs").fetchall() == [("rj_1", "code")]
    db.execute("INSERT INTO opora_review_jobs VALUES(" + ",".join("?" * (len(ROW) + 1)) + ")",
               (*ROW[:2], "rj_2", *ROW[3:], "security"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO opora_review_jobs VALUES(" + ",".join("?" * (len(ROW) + 1)) + ")",
                   (*ROW[:2], "rj_3", *ROW[3:], "security"))
    ensure_review_job_kind(db)  # idempotent
    assert db.execute("SELECT COUNT(*) FROM opora_review_jobs").fetchone()[0] == 2
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"opora_review_self_checks", "opora_review_base_observations"} <= tables
    assert "opora_review_jobs_pre_kind" not in tables
