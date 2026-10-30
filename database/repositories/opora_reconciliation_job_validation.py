"""Reject malformed mutable worker rows before exposing them or claiming work."""
import math
import re

from backend.canvas.opora_change_validation import identifier

ERROR_CODES = {'github-unavailable', 'github-timeout', 'github-malformed', 'github-identity-mismatch',
               'github-rate-limit', 'github-auth-missing', 'github-auth-invalid', 'github-response-too-large', 'invalid-read-request',
               'subscription-context-changed', 'control-changed', 'lease-expired'}


def validate_job(job, scope, binding_id):
    if (job['project_id'], job['workspace_id'], job['binding_id']) != (*scope, binding_id):
        raise ValueError('Stored job scope mismatch.')
    identifier(binding_id)
    for key in ('generation', 'claim_epoch', 'failures'):
        if type(job[key]) is not int or job[key] < (1 if key == 'generation' else 0):
            raise ValueError('Malformed persisted job counter.')
    if job['enabled'] not in (0, 1) or job['state'] not in {'scheduled', 'checking', 'retrying', 'paused', 'reconciled'}:
        raise ValueError('Malformed persisted job state.')
    for key in ('next_attempt_at', 'lease_until', 'provider_retry_until'):
        if job[key] is not None and (type(job[key]) not in (int, float) or not math.isfinite(job[key]) or job[key] < 0):
            raise ValueError('Malformed persisted job timestamp.')
    for key in ('last_observation_id', 'last_event_id'):
        identifier(job[key], nullable=True)
    if job['last_attempt_id'] is not None and not re.fullmatch('[a-f0-9]{32}', job['last_attempt_id']):
        raise ValueError('Malformed persisted attempt reference.')
    if job['error_code'] is not None and job['error_code'] not in ERROR_CODES:
        raise ValueError('Malformed persisted error code.')
    if job['state'] == 'checking':
        if not isinstance(job['owner'], str) or not 1 <= len(job['owner']) <= 100 or job['lease_until'] is None:
            raise ValueError('Malformed persisted claim lease.')
    elif job['owner'] is not None or job['lease_until'] is not None:
        raise ValueError('Unexpected persisted claim lease.')
    return job
