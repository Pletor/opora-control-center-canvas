"""Atomic lifecycle observations and semantic publication transitions, separate from reviews."""
from backend.canvas.opora_hub_store import content_id
from database.repositories.opora_reconciliation_jobs import stamp


def semantic(data):
    pr = data['pr']
    return {key: pr[key] for key in ('state', 'headSha', 'headRepoId', 'draft', 'mergedAt', 'mergeCommitSha')}


def record_success(repo, jobs, claim, binding, data, now):
    """Caller checked context and claim under locks and BEGIN IMMEDIATE."""
    completed = jobs.completed_attempt(claim)
    if completed:
        if not completed['observationId'] or repo.read('observation', completed['observationId'])['data'] != data:
            raise ValueError('Completed attempt replay differs from its original observation.')
        return completed['job']
    if not jobs.valid(claim, now):
        return False
    previous = repo.latest_record('observation', binding['id'])
    common = {'schemaVersion': 1, 'project': binding['project'], 'workspace': binding['workspace'],
              'bindingId': binding['id'], 'createdAt': stamp(now)}
    observation = repo.insert('observation', {**common, 'data': data})
    event = None
    old, new = semantic(previous['data']) if previous else None, semantic(data)
    if old != new:
        if new['state'] == 'merged':
            key = content_id({'repositoryId': binding['repository']['id'], 'prId': binding['pr']['id'],
                              'mergedAt': new['mergedAt'], 'mergeCommitSha': new['mergeCommitSha']})
        else:
            key = content_id({'previousObservationId': previous['id'] if previous else None,
                              'observationId': observation['id'], 'state': new})
        event = repo.event_for_key(binding['id'], key)
        if not event:
            event = repo.insert('event', {**common, 'eventKey': key, 'observationId': observation['id'],
                                         'fromState': old, 'toState': new})
    merged = new['state'] == 'merged'
    interval = 900 if new['state'] == 'closed-unmerged' else binding['intervalSeconds']
    finished = jobs.finish(claim, now, state='reconciled' if merged else 'scheduled',
                       next_attempt_at=None if merged else now + interval,
                           observation_id=observation['id'], event_id=event['id'] if event else None)
    return jobs.completed_attempt(claim)['job'] if finished else False


def retry_delay(failures, jitter):
    return min(3600, 30 * 2 ** min(failures, 7)) * (0.8 + 0.2 * jitter)


def system_pause(repo, jobs, binding, now, reason):
    previous = repo.latest_control(binding['id'])
    content = {'schemaVersion': 1, 'project': binding['project'], 'workspace': binding['workspace'],
               'bindingId': binding['id'], 'createdAt': stamp(now), 'parentControlId': previous['id'],
               'generation': previous['generation'] + 1, 'action': 'system-pause', 'enabled': False,
               'requestId': None, 'requestDigest': None, 'by': {'kind': 'system', 'name': 'Reconciliation'}}
    repo.activate_control(content, previous['generation'])
    jobs.configure(binding['id'], content['generation'], False, now)
    jobs.db.execute('UPDATE opora_reconciliation_jobs SET error_code=? WHERE project_id=? AND workspace_id=? '
                    'AND binding_id=?', (reason, *jobs.scope, binding['id']))
