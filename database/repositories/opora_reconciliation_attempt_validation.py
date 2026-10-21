"""Validate every durable attempt before projecting safe audit summaries or replaying."""
import json
import math
import re

from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_review_policy_validation import timestamp
from database.repositories.opora_reconciliation_job_validation import ERROR_CODES
from database.repositories.opora_reconciliation_receipts import JOB_KEYS


def validate_attempt(row, scope, binding_id):
    if (row['project_id'], row['workspace_id'], row['binding_id']) != (*scope, binding_id):
        raise ValueError('Stored attempt scope mismatch.')
    identifier(binding_id)
    if not isinstance(row['id'], str) or re.fullmatch('[a-f0-9]{32}', row['id']) is None:
        raise ValueError('Malformed stored attempt identity.')
    if row['status'] not in {'pending', 'complete', 'failed', 'interrupted'}:
        raise ValueError('Malformed stored attempt state.')
    for key in ('epoch', 'generation'):
        if type(row[key]) is not int or row[key] < 1:
            raise ValueError('Malformed stored attempt counter.')
    for key in ('started_at', 'finished_at'):
        value = row[key]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 253402300799):
            raise ValueError('Malformed stored attempt timestamp.')
    if row['started_at'] is None or (row['finished_at'] is not None and row['finished_at'] < row['started_at']):
        raise ValueError('Malformed stored attempt interval.')
    error = row['error_code']
    if error is not None and error not in ERROR_CODES:
        raise ValueError('Malformed stored attempt error code.')
    identifier(row['observation_id'], nullable=True)
    pending = row['status'] == 'pending'
    if pending != (row['finished_at'] is None) or (pending and (error is not None or row['observation_id'] is not None)):
        raise ValueError('Malformed stored attempt outcome.')
    if row['status'] in {'pending', 'interrupted'}:
        if row['finish_digest'] is not None or row['receipt'] is not None:
            raise ValueError('Unexpected stored attempt receipt.')
    else:
        identifier(row['finish_digest'])
        if (row['status'] == 'failed') != (error is not None):
            raise ValueError('Stored attempt status disagrees with error.')
        try:
            job = json.loads(row['receipt'])
            if (not isinstance(job, dict) or set(job) != JOB_KEYS or job['bindingId'] != binding_id
                    or job['generation'] != row['generation'] or job['lastAttemptId'] != row['id']
                    or job['lastErrorCode'] != error or job['state'] not in {'scheduled', 'retrying', 'paused', 'reconciled'}
                    or type(job['generation']) is not int or type(job['consecutiveFailures']) is not int
                    or job['consecutiveFailures'] < 0 or job['leaseUntil'] is not None):
                raise ValueError('Malformed stored attempt receipt.')
            for key in ('nextAttemptAt', 'providerRetryUntil'):
                if job[key] is not None:
                    timestamp(job[key])
            for key in ('lastObservationId', 'lastEventId'):
                identifier(job[key], nullable=True)
            if row['observation_id'] is not None and job['lastObservationId'] != row['observation_id']:
                raise ValueError('Stored receipt observation mismatch.')
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError('Malformed stored attempt receipt.') from error
    return row
