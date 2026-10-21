"""Reusable real-SQLite runtime setup; no network or Canvas mutations."""
import sqlite3
import threading
from types import SimpleNamespace

from database.repositories.opora_reconciliation import ReconciliationRepository
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs, stamp
from database.schema.opora_reconciliation_jobs import JOB_SCHEMA
from database.schema.opora_reconciliation_schema import RECONCILIATION_SCHEMA


def setup(path, *, number=7, now=1000):
    db = sqlite3.connect(path, check_same_thread=False)
    db.executescript(RECONCILIATION_SCHEMA + JOB_SCHEMA)
    repo, jobs = ReconciliationRepository(db, 'project', 'workspace'), ReconciliationJobs(db, 'project', 'workspace')
    with db:
        db.execute('BEGIN IMMEDIATE')
        binding = repo.insert('binding', {'schemaVersion': 1, 'project': 'project', 'workspace': 'workspace',
            'createdAt': stamp(now), 'acceptedRevision': 'a' * 40, 'identityEvidenceId': 'b' * 40,
            'repository': {'id': 1, 'fullName': 'owner/repo', 'baseBranch': 'main'},
            'pr': {'id': number + 100, 'number': number, 'headRepoId': 2}, 'enrolledHeadSha': 'c' * 40,
            'configuration': {'repository': 'owner/repo', 'branch': 'main', 'repoPath': 'path', 'sourcePath': 'path'},
            'intervalSeconds': 300, 'by': {'kind': 'human', 'name': 'Test'}})
        repo.activate_control({'schemaVersion': 1, 'project': 'project', 'workspace': 'workspace',
            'bindingId': binding['id'], 'parentControlId': None, 'generation': 1, 'action': 'enroll',
            'enabled': True, 'requestId': 'request-' + str(number), 'requestDigest': 'd' * 40,
            'createdAt': stamp(now), 'by': {'kind': 'human', 'name': 'Test'}}, 0)
        jobs.configure(binding['id'], 1, True, now)
    return db, repo, jobs, binding


def data(binding, state='merged'):
    return {'complete': True, 'observedFrom': stamp(1000), 'observedUntil': stamp(1001),
            'repository': {'id': 1, 'fullName': 'owner/repo'},
            'pr': {'id': binding['pr']['id'], 'number': binding['pr']['number'], 'baseRef': 'main',
                   'headSha': 'c' * 40, 'headRepoId': None, 'state': state, 'draft': False,
                   'merged': state == 'merged', 'mergedAt': stamp(900) if state == 'merged' else None,
                   'mergeCommitSha': 'e' * 40 if state == 'merged' else None}}


class Service:
    def __init__(self, db):
        self.db, self.lock = db, threading.RLock()

    def project_ids(self):
        return ['project']

    def db_for(self, pid):
        assert pid == 'project'
        return self.db

    def lock_for(self, pid):
        return self.lock

    def graph_lock_for(self, pid):
        return self.lock


def reader(fn):
    return SimpleNamespace(read=fn, retry_after=0)
