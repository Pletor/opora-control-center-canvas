"""Sequence authority survives restarts, failed refreshes and out-of-order completion."""
import sqlite3

import pytest

from database.repositories.opora_review_attempts import Attempts
from database.schema.opora_review_policy_schema import SCHEMA

CONFIG = {"repository": "owner/repo", "branch": "main"}
START, FINISH = "2026-10-21T10:00:00Z", "2026-10-21T10:00:10Z"


@pytest.fixture
def attempts(tmp_path):
    db = sqlite3.connect(tmp_path / "attempts.sqlite")
    db.executescript(SCHEMA)
    yield Attempts(db, "project", "workspace")
    db.close()


def begin(repo, pr=1, config=None):
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        return repo.begin(pr, config or CONFIG, "a" * 40, None, START)


def finish(repo, attempt, state="complete"):
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        return repo.finish(attempt["sequence"], state, "b" * 40, FINISH, "github-unavailable" if state == "failed" else None)


def test_newest_pending_failed_and_late_completion_never_fall_back(attempts):
    first, second = begin(attempts), begin(attempts)
    finish(attempts, first)
    assert attempts.latest(1, CONFIG) == second
    failed = finish(attempts, second, "failed")
    assert attempts.latest(1, CONFIG) == failed
    with pytest.raises(ValueError, match="rewritten"):
        finish(attempts, second)
    assert finish(attempts, second, "failed") == failed


def test_scope_and_pr_configuration_separate_authority(attempts):
    first = begin(attempts)
    begin(attempts, 2)
    begin(attempts, 1, {**CONFIG, "branch": "other"})
    assert attempts.latest(1, CONFIG) == first
    assert Attempts(attempts.db, "project", "other").latest(1, CONFIG) is None


def test_rollback_and_crashed_pending_survive_restart(attempts, tmp_path):
    with pytest.raises(RuntimeError):
        attempts.begin(1, CONFIG, "a" * 40, None, START)
    first = begin(attempts)
    attempts.db.execute("BEGIN IMMEDIATE")
    attempts.finish(first["sequence"], "complete", "b" * 40, FINISH)
    attempts.db.rollback()
    fresh_db = sqlite3.connect(tmp_path / "attempts.sqlite")
    try:
        assert Attempts(fresh_db, "project", "workspace").latest(1, CONFIG) == first
    finally:
        fresh_db.close()


def test_invalid_terminal_evidence_and_corrupt_row_rejected(attempts):
    first = begin(attempts)
    with pytest.raises(ValueError), attempts.db:
        attempts.db.execute("BEGIN IMMEDIATE")
        attempts.finish(first["sequence"], "complete", None, FINISH)
    with pytest.raises(ValueError), attempts.db:
        attempts.db.execute("BEGIN IMMEDIATE")
        attempts.finish(first["sequence"], "failed", None, "2026-10-21T09:59:00Z", "bad-time")
    attempts.db.execute("UPDATE opora_review_attempts SET state='complete'")
    with pytest.raises(ValueError):
        attempts.latest(1, CONFIG)


@pytest.mark.parametrize("pr", [True, 0, -1, 2147483648, "1"])
def test_strict_pr_number(attempts, pr):
    with pytest.raises(ValueError):
        begin(attempts, pr)
