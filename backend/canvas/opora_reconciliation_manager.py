"""Lifespan-owned serial scheduler; network never holds Canvas or SQLite locks."""
import logging
import os
import random
import threading
import time
import uuid

from backend.canvas.opora_reconciliation_finish import (
    journal,
    record_success,
    retry_delay,
    system_pause,
)
from backend.canvas.opora_reconciliation_observation import observation
from backend.canvas.opora_reconciliation_scope import historical_context
from backend.integrations.github_merge_reader import GitHubMergeReader
from backend.integrations.github_merge_transport import GitHubMergeError
from database.repositories.opora_reconciliation import ReconciliationRepository
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs

LOGGER = logging.getLogger(__name__)


class ReconciliationManager:
    def __init__(self, service, reader=None, *, clock=time.time, jitter=random.random, validator=historical_context):
        self.service, self.reader = service, reader or GitHubMergeReader()
        self.clock, self.jitter, self.validator = clock, jitter, validator
        self.stop = threading.Event()
        self.gate, self.serial = threading.RLock(), threading.Lock()
        self.thread = None
        self.cooldown_until, self.next_start = 0, 0
        self.projects, self.cursor, self.initialized = None, 0, False
        self.project_cursor = 0

    def start(self):
        if os.environ.get('OPORA_RECONCILIATION_WORKER', '1') == '0' or self.thread or self.stop.is_set():
            return
        self.thread = threading.Thread(target=self._loop, name='github-reconciliation', daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stop.is_set():
            try:
                self.run_one()
            except Exception:
                LOGGER.exception('Reconciliation scheduler unavailable; retrying safely.')
            self.stop.wait(1)

    def close(self):
        self.stop.set()
        # Every DB access, including after network, takes this gate and checks stop.
        with self.gate:
            pass
        if self.thread:
            self.thread.join(timeout=1)

    def _projects(self):
        with self.gate:
            return [] if self.stop.is_set() else self.service.project_ids()

    def _initialize(self):
        if self.projects is None:
            self.projects = self._projects()
        current = set(self._projects())
        for pid in self.projects[self.cursor:self.cursor + 32]:
            if pid not in current:
                continue
            with self.service.graph_lock_for(pid), self.service.lock_for(pid), self.gate:
                if self.stop.is_set():
                    return
                row = self.service.db_for(pid).execute('SELECT MAX(provider_retry_until) FROM opora_reconciliation_jobs').fetchone()
                self.cooldown_until = max(self.cooldown_until, row[0] or 0)
        self.cursor += 32
        self.initialized = self.cursor >= len(self.projects)

    def _claim(self, now):
        projects = self._projects()
        for offset in range(min(32, len(projects))):
            pid = projects[(self.project_cursor + offset) % len(projects)]
            with self.service.graph_lock_for(pid), self.service.lock_for(pid), self.gate:
                if self.stop.is_set():
                    return None
                db = self.service.db_for(pid)
                scopes = db.execute('SELECT DISTINCT workspace_id FROM opora_reconciliation_jobs WHERE enabled=1 '
                                    "AND next_attempt_at<=? AND state IN ('scheduled','retrying','checking') "
                                    'AND (lease_until IS NULL OR lease_until<=?) ORDER BY workspace_id LIMIT 100', (now, now)).fetchall()
                for (wid,) in scopes:
                    with db:
                        db.execute('BEGIN IMMEDIATE')
                        jobs = ReconciliationJobs(db, pid, wid)
                        claim = jobs.claim(self.clock(), uuid.uuid4().hex)
                        if claim:
                            repo = ReconciliationRepository(db, pid, wid)
                            binding = repo.read('binding', claim['binding_id'])
                            control = repo.latest_control(binding['id'])
                            try:
                                if not control['enabled'] or control['generation'] != claim['generation']:
                                    raise ValueError('Control changed.')
                                self.validator(self.service, pid, wid, binding)
                            except ValueError:
                                checked = self.clock()
                                if jobs.valid(claim, checked):
                                    system_pause(repo, jobs, binding, checked, 'subscription-context-changed')
                                continue
                            if not jobs.valid(claim, self.clock()) or self.stop.is_set():
                                return None
                            self.project_cursor = (self.project_cursor + offset + 1) % len(projects)
                            return pid, wid, claim, binding
        self.project_cursor = (self.project_cursor + 32) % max(1, len(projects))
        return None

    def run_one(self):
        with self.serial:
            if self.stop.is_set():
                return None
            if self.projects is not None and set(self.projects) != set(self._projects()):
                self.projects, self.cursor, self.initialized = None, 0, False
            if not self.initialized:
                self._initialize()
                if not self.initialized:
                    return None
            now = self.clock()
            if self.stop.is_set() or now < max(self.cooldown_until, self.next_start):
                return None
            work = self._claim(now)
            if not work:
                return None
            pid, wid, claim, binding = work
            data, error = None, None
            try:
                data = observation(self.reader.read(binding))
            except (ValueError, KeyError, TypeError) as failure:
                error = failure if isinstance(failure, GitHubMergeError) else GitHubMergeError('github-malformed')
            except Exception:  # noqa: BLE001 - reader failures expose only a fixed error code.
                error = GitHubMergeError()
            now = self.clock()
            wait = error.retry_after if error else getattr(self.reader, 'retry_after', 0)
            self.cooldown_until = max(self.cooldown_until, now + wait if wait else 0)
            self.next_start = now + 1
            with self.service.graph_lock_for(pid), self.service.lock_for(pid), self.gate:
                if self.stop.is_set():
                    return claim
                db = self.service.db_for(pid)
                with db:
                    db.execute('BEGIN IMMEDIATE')
                    jobs, repo = ReconciliationJobs(db, pid, wid), ReconciliationRepository(db, pid, wid)
                    now = self.clock()
                    if wait:
                        db.execute('UPDATE opora_reconciliation_jobs SET provider_retry_until=MAX(COALESCE(provider_retry_until,0),?) '
                                   'WHERE project_id=? AND workspace_id=? AND binding_id=?',
                                   (self.cooldown_until, pid, wid, binding['id']))
                    if not jobs.valid(claim, now):
                        return claim
                    control = repo.latest_control(binding['id'])
                    if not control['enabled'] or control['generation'] != claim['generation']:
                        return claim
                    try:
                        self.validator(self.service, pid, wid, binding)
                    except ValueError:
                        now = self.clock()
                        if jobs.valid(claim, now):
                            system_pause(repo, jobs, binding, now, 'subscription-context-changed')
                        return claim
                    now = self.clock()
                    if not jobs.valid(claim, now):
                        return claim
                    if error and error.action_required:
                        system_pause(repo, jobs, binding, now, error.code)
                    elif error:
                        due = max(now + retry_delay(claim['failures'], self.jitter()), self.cooldown_until)
                        jobs.finish(claim, now, state='retrying', next_attempt_at=due, error_code=error.code,
                                    provider_retry_until=self.cooldown_until if wait else None)
                        journal(binding, 'exception', 'čtení GitHubu selhalo, zkusí se znovu', error.code, 'warn',
                                'Zkontrolovat dostupnost GitHubu a token; sledování se opakuje samo.')
                    else:
                        record_success(repo, jobs, claim, binding, data, now)
                        if claim['failures']:
                            from backend.app import error_log

                            error_log.resolve(source='card', project=pid, subject=binding['id'])
            return claim
