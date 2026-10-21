"""Claim fencing and durable attempt audit. Helpers never commit caller transactions."""
import json
import uuid
from datetime import UTC, datetime

from backend.canvas.opora_hub_store import canonical, content_id
from database.repositories.opora_reconciliation_attempt_validation import validate_attempt
from database.repositories.opora_reconciliation_job_validation import validate_job


def stamp(value):
    return datetime.fromtimestamp(value, UTC).isoformat() if value is not None else None


class ReconciliationJobs:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def _transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError('Reconciliation writes require an explicit transaction.')

    def configure(self, binding_id, generation, enabled, now):
        self._transaction()
        old = self.read(binding_id)
        if old:
            if generation <= old['generation']:
                raise ValueError('Control generation must advance.')
            if old['last_attempt_id']:
                self.db.execute("UPDATE opora_reconciliation_attempts SET status='interrupted',"
                                "finished_at=?,error_code='control-changed' WHERE id=? AND status='pending'",
                                (now, old['last_attempt_id']))
            self.db.execute("UPDATE opora_reconciliation_jobs SET generation=?,enabled=?,state=?,"
                            "next_attempt_at=?,owner=NULL,lease_until=NULL,error_code=NULL WHERE "
                            "project_id=? AND workspace_id=? AND binding_id=?",
                            (generation, int(enabled), 'scheduled' if enabled else 'paused',
                             now if enabled else None, *self.scope, binding_id))
        else:
            self.db.execute('INSERT INTO opora_reconciliation_jobs '
                            '(project_id,workspace_id,binding_id,generation,enabled,state,next_attempt_at) '
                            'VALUES(?,?,?,?,?,?,?)', (*self.scope, binding_id, generation, int(enabled),
                            'scheduled' if enabled else 'paused', now if enabled else None))
        return self.public(binding_id)

    def create(self, binding, control, now):
        return self.configure(binding['id'], control['generation'], control['enabled'], now)

    def control(self, binding_id, control, now):
        return self.configure(binding_id, control['generation'], control['enabled'], now)

    def read(self, binding_id):
        cursor = self.db.execute('SELECT * FROM opora_reconciliation_jobs WHERE project_id=? '
                                 'AND workspace_id=? AND binding_id=?', (*self.scope, binding_id))
        row = cursor.fetchone()
        job = dict(zip([item[0] for item in cursor.description], row)) if row else None
        return validate_job(job, self.scope, binding_id) if job else None

    def public(self, binding_id):
        row = self.read(binding_id)
        if not row:
            return None
        return {'bindingId': binding_id, 'generation': row['generation'], 'state': row['state'],
                'nextAttemptAt': stamp(row['next_attempt_at']), 'leaseUntil': stamp(row['lease_until']),
                'consecutiveFailures': row['failures'], 'lastErrorCode': row['error_code'],
                'lastAttemptId': row['last_attempt_id'], 'lastObservationId': row['last_observation_id'],
                'lastEventId': row['last_event_id'], 'providerRetryUntil': stamp(row['provider_retry_until'])}

    def claim(self, now, owner, lease_seconds=45):
        self._transaction()
        if lease_seconds <= 30:
            raise ValueError('Lease must exceed the bounded network deadline.')
        row = self.db.execute('SELECT binding_id FROM opora_reconciliation_jobs WHERE project_id=? '
                              'AND workspace_id=? AND enabled=1 AND next_attempt_at<=? '
                              "AND state IN ('scheduled','retrying','checking') "
                              'AND (lease_until IS NULL OR lease_until<=?) '
                              'ORDER BY next_attempt_at,binding_id LIMIT 1', (*self.scope, now, now)).fetchone()
        if not row:
            return None
        job = self.read(row[0])
        if job['last_attempt_id']:
            self.db.execute("UPDATE opora_reconciliation_attempts SET status='interrupted',finished_at=?,"
                            "error_code='lease-expired' WHERE id=? AND status='pending'",
                            (now, job['last_attempt_id']))
        attempt_id, epoch = uuid.uuid4().hex, job['claim_epoch'] + 1
        self.db.execute("UPDATE opora_reconciliation_jobs SET state='checking',owner=?,lease_until=?,"
                        'claim_epoch=?,last_attempt_id=? WHERE project_id=? AND workspace_id=? AND binding_id=?',
                        (owner, now + lease_seconds, epoch, attempt_id, *self.scope, job['binding_id']))
        self.db.execute('INSERT INTO opora_reconciliation_attempts '
                        '(id,project_id,workspace_id,binding_id,epoch,generation,status,started_at) '
                        "VALUES(?,?,?,?,?,?,'pending',?)",
                        (attempt_id, *self.scope, job['binding_id'], epoch, job['generation'], now))
        return self.read(job['binding_id'])

    def valid(self, claim, now):
        current = self.read(claim['binding_id'])
        return bool(current and current['enabled'] and current['state'] == 'checking'
                    and current['owner'] == claim['owner'] and current['claim_epoch'] == claim['claim_epoch']
                    and current['generation'] == claim['generation'] and current['lease_until'] > now)

    def finish(self, claim, now, *, state, next_attempt_at, observation_id=None, event_id=None, error_code=None, provider_retry_until=None):
        self._transaction()
        digest = content_id({'state': state, 'nextAttemptAt': next_attempt_at, 'observationId': observation_id,
                             'eventId': event_id, 'errorCode': error_code, 'providerRetryUntil': provider_retry_until})
        completed = self.completed_attempt(claim)
        if completed:
            if completed['digest'] != digest:
                raise ValueError('Completed attempt replay differs from its original result.')
            return True
        if not self.valid(claim, now):
            return False
        if state not in ('scheduled', 'retrying', 'paused', 'reconciled'):
            raise ValueError('Invalid reconciliation job state.')
        self.db.execute('UPDATE opora_reconciliation_jobs SET state=?,next_attempt_at=?,owner=NULL,'
                        'lease_until=NULL,failures=?,last_observation_id=COALESCE(?,last_observation_id),'
                        'last_event_id=COALESCE(?,last_event_id),error_code=?,provider_retry_until=COALESCE(?,provider_retry_until) '
                        'WHERE project_id=? AND workspace_id=? AND binding_id=?',
                        (state, next_attempt_at, claim['failures'] + 1 if error_code else 0,
                         observation_id, event_id, error_code, provider_retry_until, *self.scope, claim['binding_id']))
        self.db.execute('UPDATE opora_reconciliation_attempts SET status=?,finished_at=?,error_code=?,'
                        'observation_id=?,finish_digest=?,receipt=? WHERE id=? AND status=\'pending\'',
                        ('failed' if error_code else 'complete', now, error_code, observation_id, digest,
                         canonical(self.public(claim['binding_id'])), claim['last_attempt_id']))
        return True

    def _attempt_rows(self, binding_id, clause, parameters):
        cursor = self.db.execute('SELECT rowid AS cursor,* FROM opora_reconciliation_attempts '
                                 'WHERE project_id=? AND workspace_id=? AND binding_id=? ' + clause,
                                 (*self.scope, binding_id, *parameters))
        keys = [column[0] for column in cursor.description]
        return [validate_attempt(dict(zip(keys, row)), self.scope, binding_id) for row in cursor.fetchall()]

    @staticmethod
    def _attempt_public(row):
        return {'id': row['id'], 'state': row['status'], 'startedAt': stamp(row['started_at']),
                'finishedAt': stamp(row['finished_at']), 'errorCode': row['error_code'],
                'observationId': row['observation_id']}

    def latest_attempt(self, binding_id):
        job = self.read(binding_id)
        if not job or not job['last_attempt_id']:
            return None
        rows = self._attempt_rows(binding_id, 'AND id=?', (job['last_attempt_id'],))
        if not rows:
            raise ValueError('Stored latest attempt is missing.')
        return self._attempt_public(rows[0])

    def completed_attempt(self, claim):
        rows = self._attempt_rows(claim['binding_id'], 'AND id=? AND epoch=? AND generation=?',
                                  (claim['last_attempt_id'], claim['claim_epoch'], claim['generation']))
        if rows and rows[0]['status'] in ('complete', 'failed'):
            row = rows[0]
            return {'digest': row['finish_digest'], 'job': json.loads(row['receipt']), 'observationId': row['observation_id']}
        return None

    def attempt_history(self, binding_id, limit=50, cursor=0):
        if type(cursor) is not int or not 0 <= cursor <= 9223372036854775807:
            raise ValueError('Invalid attempt history cursor.')
        limit = min(100, max(1, limit))
        rows = self._attempt_rows(binding_id, 'AND rowid>? ORDER BY rowid LIMIT ?', (cursor, limit + 1))
        return {'items': [self._attempt_public(row) for row in rows[:limit]],
                'nextCursor': str(rows[limit - 1]['cursor']) if len(rows) > limit else None}
