"""Durability proofs against SQLite files and independent connections."""
import sqlite3
import threading

import pytest

from backend.canvas.opora_reconciliation_finish import record_success
from backend.canvas.reconciliation_test_support import data, setup
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs


def claim(db, jobs, now=1000, owner='first'):
    with db:
        db.execute('BEGIN IMMEDIATE')
        return jobs.claim(now, owner)


def test_independent_connection_claim_race_expiry_and_generation(tmp_path):
    path = tmp_path / 'state.sqlite'
    db, _repo, jobs, binding = setup(path)
    other = sqlite3.connect(path, check_same_thread=False)
    barrier, results = threading.Barrier(2), []
    def race(conn):
        barrier.wait()
        results.append(claim(conn, ReconciliationJobs(conn, 'project', 'workspace')))
    threads = [threading.Thread(target=race, args=(conn,)) for conn in (db, other)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(item is not None for item in results) == 1
    first = next(item for item in results if item)
    second = claim(other, ReconciliationJobs(other, 'project', 'workspace'), 1046, 'second')
    with db:
        db.execute('BEGIN IMMEDIATE')
        assert not jobs.finish(first, 1046, state='reconciled', next_attempt_at=None)
        assert jobs.valid(second, 1046)
        jobs.configure(binding['id'], 2, False, 1046)
        assert not jobs.finish(second, 1047, state='reconciled', next_attempt_at=None)
    assert db.execute("SELECT count(*) FROM opora_reconciliation_attempts WHERE status='interrupted'").fetchone()[0] == 2


@pytest.mark.parametrize('fail_at', ['observation', 'event', 'finish'])
def test_atomic_rollback_and_merge_dedup(tmp_path, monkeypatch, fail_at):
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    work = claim(db, jobs)
    original_insert, original_finish = repo.insert, jobs.finish
    def insert(kind, content):
        result = original_insert(kind, content)
        if kind == fail_at:
            raise RuntimeError('crash within transaction')
        return result
    def finish(*args, **kwargs):
        result = original_finish(*args, **kwargs)
        if fail_at == 'finish':
            raise RuntimeError('crash after job write')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(repo, 'insert', insert)
        patch.setattr(jobs, 'finish', finish)
        with pytest.raises(RuntimeError), db:
            db.execute('BEGIN IMMEDIATE')
            record_success(repo, jobs, work, binding, data(binding), 1001)
    assert repo.latest_record('event', binding['id']) is None
    assert repo.latest_record('observation', binding['id']) is None
    assert jobs.read(binding['id'])['state'] == 'checking'
    work = claim(db, jobs, 1046, 'restart')
    with db:
        db.execute('BEGIN IMMEDIATE')
        assert record_success(repo, jobs, work, binding, data(binding), 1047)
    assert len(repo.records('event', binding['id'])) == 1
    with db:
        db.execute('BEGIN IMMEDIATE')
        jobs.configure(binding['id'], 2, True, 1048)
    work = claim(db, jobs, 1048, 'explicit-retry')
    with db:
        db.execute('BEGIN IMMEDIATE')
        assert record_success(repo, jobs, work, binding, data(binding), 1049)
    assert len(repo.records('event', binding['id'])) == 1
    assert jobs.public(binding['id'])['state'] == 'reconciled'
    assert 'owner' not in jobs.public(binding['id'])


def test_closed_reopened_is_new_semantic_transition(tmp_path):
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    for index, state in enumerate(('open', 'open', 'closed-unmerged', 'open', 'merged')):
        now = 1000 + index * 901
        work = claim(db, jobs, now)
        with db:
            db.execute('BEGIN IMMEDIATE')
            record_success(repo, jobs, work, binding, data(binding, state), now + 1)
    assert len(repo.records('observation', binding['id'])) == 5
    assert len(repo.records('event', binding['id'])) == 4
    assert jobs.public(binding['id'])['state'] == 'reconciled'

def test_completed_receipt_replay_conflicts_and_history_pages(tmp_path):
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    work = claim(db, jobs)
    observed = data(binding)
    with db:
        db.execute('BEGIN IMMEDIATE')
        assert record_success(repo, jobs, work, binding, observed, 1001)
    saved = jobs.public(binding['id'])
    with db:
        db.execute('BEGIN IMMEDIATE')
        assert record_success(repo, jobs, work, binding, observed, 1050) == saved
        changed = {**observed, 'observedUntil': '2026-01-01T00:00:00+00:00'}
        with pytest.raises(ValueError, match='replay differs'):
            record_success(repo, jobs, work, binding, changed, 1050)
        jobs.configure(binding['id'], 2, True, 1051)
    second = claim(db, jobs, 1051)
    with db:
        db.execute('BEGIN IMMEDIATE')
        record_success(repo, jobs, second, binding, observed, 1052)
    first_page = jobs.attempt_history(binding['id'], limit=1)
    assert first_page['items'][0]['id'] == work['last_attempt_id']
    assert first_page['nextCursor'] is not None
    second_page = jobs.attempt_history(binding['id'], limit=1, cursor=int(first_page['nextCursor']))
    assert second_page['items'][0]['id'] == second['last_attempt_id']
    assert second_page['nextCursor'] is None
    assert 'owner' not in repr(first_page)


def test_corrupt_job_state_is_rejected_before_claim(tmp_path):
    db, _repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    with db:
        db.execute('UPDATE opora_reconciliation_jobs SET failures=-1')
    with pytest.raises(ValueError, match='counter'):
        jobs.public(binding['id'])

@pytest.mark.parametrize('column,value', [('error_code', 'private-token-should-never-render'),
    ('status', 'private-state'), ('id', 'private-identifier'), ('epoch', -1), ('finished_at', -3)])
def test_attempt_projections_reject_tampered_rows(tmp_path, column, value):
    db, _repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    work = claim(db, jobs)
    with db:
        db.execute(f'UPDATE opora_reconciliation_attempts SET {column}=? WHERE id=?',
                   (value, work['last_attempt_id']))
    for project in (lambda: jobs.latest_attempt(binding['id']), lambda: jobs.attempt_history(binding['id'])):
        with pytest.raises(ValueError):
            project()


def test_completed_attempt_rejects_private_receipt_fields(tmp_path):
    import json
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    work = claim(db, jobs)
    with db:
        db.execute('BEGIN IMMEDIATE')
        record_success(repo, jobs, work, binding, data(binding), 1001)
    receipt = {**jobs.public(binding['id']), 'owner': 'private-token'}
    with db:
        db.execute('UPDATE opora_reconciliation_attempts SET receipt=?', (json.dumps(receipt),))
    with pytest.raises(ValueError, match='receipt'):
        jobs.completed_attempt(work)
    with pytest.raises(ValueError, match='receipt'):
        jobs.attempt_history(binding['id'])
