"""A fresh manager recovers durable work; shutdown never returns to the closed DB."""
import sqlite3

import pytest

from backend.canvas.opora_reconciliation_manager import ReconciliationManager
from backend.canvas.reconciliation_test_support import Service, data, reader, setup
from backend.integrations.github_merge_transport import GitHubMergeError
from database.repositories.opora_reconciliation import ReconciliationRepository
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs


def manager(service, source, now):
    return ReconciliationManager(service, source, clock=lambda: now[0], jitter=lambda: 0,
                                 validator=lambda *args: {'acceptedHead': 'f' * 40})


def test_crash_after_remote_merge_before_canvas_commit_restart(tmp_path):
    path = tmp_path / 'state.sqlite'
    db, repo, jobs, binding = setup(path)
    now = [1000]
    class Crash(BaseException):
        pass
    def merged_then_crash(pin):
        assert pin['acceptedRevision'] == 'a' * 40
        raise Crash('process died after GitHub merged, before Canvas transaction')
    first = manager(Service(db), reader(merged_then_crash), now)
    with pytest.raises(Crash):
        first.run_one()
    first.close()
    assert jobs.public(binding['id'])['state'] == 'checking'
    db.close()
    now[0] = 1046
    reopened = sqlite3.connect(path, check_same_thread=False)
    second = manager(Service(reopened), reader(lambda pin: data(pin)), now)
    assert second.run_one()
    repo = ReconciliationRepository(reopened, 'project', 'workspace')
    assert len(repo.records('event', binding['id'])) == 1
    assert repo.latest_record('observation', binding['id'])['data']['pr']['state'] == 'merged'
    assert repo.read('binding', binding['id'])['acceptedRevision'] == 'a' * 40
    second.close()
    reopened.close()
    third_db = sqlite3.connect(path)
    third = manager(Service(third_db), reader(lambda _: pytest.fail('terminal job fetched again')), now)
    assert third.run_one() is None
    assert len(ReconciliationRepository(third_db, 'project', 'workspace').records('event', binding['id'])) == 1


def test_global_rate_cooldown_survives_restart_and_manual_retry(tmp_path):
    path = tmp_path / 'state.sqlite'
    db, _repo, jobs, first = setup(path)
    db2, _, _, second = setup(path, number=8)
    db2.close()
    now, calls = [1000], []
    def rate(pin):
        calls.append(pin['id'])
        raise GitHubMergeError('github-rate-limit', retry_after=600)
    one = manager(Service(db), reader(rate), now)
    one.run_one()
    assert len(calls) == 1
    assert jobs.public(first['id'])['providerRetryUntil'] or jobs.public(second['id'])['providerRetryUntil']
    one.close()
    db.close()
    db = sqlite3.connect(path)
    two = manager(Service(db), reader(lambda pin: calls.append(pin['id']) or data(pin)), now)
    now[0] = 1002
    with db:
        db.execute('BEGIN IMMEDIATE')
        ReconciliationJobs(db, 'project', 'workspace').configure(first['id'], 2, True, now[0])
    assert two.run_one() is None
    assert len(calls) == 1
    now[0] = 1601
    assert two.run_one()
    assert len(calls) == 2


def test_failure_retains_last_success_and_backoff_is_per_job(tmp_path):
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    now = [1000]
    worker = manager(Service(db), reader(lambda pin: data(pin, 'open')), now)
    worker.run_one()
    previous = jobs.public(binding['id'])['lastObservationId']
    worker.reader = reader(lambda pin: (_ for _ in ()).throw(GitHubMergeError()))
    now[0] = 1301
    worker.run_one()
    assert jobs.public(binding['id'])['state'] == 'retrying'
    assert jobs.public(binding['id'])['lastObservationId'] == previous
    assert jobs.public(binding['id'])['consecutiveFailures'] == 1
    assert worker.cooldown_until == 0
    assert repo.latest_record('observation', binding['id'])['data']['pr']['state'] == 'open'


def test_config_change_pauses_inflight_without_publication(tmp_path):
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    count = [0]
    def validator(*args):
        count[0] += 1
        if count[0] == 2:
            raise ValueError('configuration moved')
    worker = manager(Service(db), reader(lambda pin: data(pin)), [1000])
    worker.validator = validator
    worker.run_one()
    assert jobs.public(binding['id'])['state'] == 'paused'
    assert not repo.latest_control(binding['id'])['enabled']
    assert repo.latest_record('observation', binding['id']) is None

def test_bounded_startup_scans_restore_cooldown_before_any_network(tmp_path):
    db, _repo, _jobs, _binding = setup(tmp_path / 'state.sqlite')
    with db:
        db.execute('UPDATE opora_reconciliation_jobs SET provider_retry_until=2000')
    service = Service(db)
    service.project_ids = lambda: [f'p{i}' for i in range(40)] + ['project']
    scans = []
    service.db_for = lambda pid: scans.append(pid) or db
    worker = manager(service, reader(lambda _: pytest.fail('cooldown was bypassed')), [1000])
    assert worker.run_one() is None
    assert len(scans) == 32 and not worker.initialized
    assert worker.run_one() is None
    assert len(scans) == 41 and worker.initialized and worker.cooldown_until == 2000


def test_plan_may_advance_during_get_and_serial_fairness(tmp_path):
    path = tmp_path / 'state.sqlite'
    db, repo, jobs, first = setup(path)
    other, _, _, second = setup(path, number=8)
    other.close()
    calls, heads = [], ['a' * 40]
    def read(pin):
        calls.append(pin['id'])
        heads[0] = 'f' * 40
        return data(pin, 'open')
    now = [1000]
    worker = manager(Service(db), reader(read), now)
    worker.validator = lambda *args: {'acceptedHead': heads[0]}
    worker.run_one()
    now[0] += 2
    worker.run_one()
    assert set(calls) == {first['id'], second['id']}
    assert jobs.public(first['id'])['state'] == 'scheduled'
    assert repo.read('binding', first['id'])['acceptedRevision'] == 'a' * 40

def test_expiry_during_context_recheck_fences_publication(tmp_path):
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    now, contexts = [1000], [0]
    worker = manager(Service(db), reader(lambda pin: data(pin)), now)
    def validator(*args):
        contexts[0] += 1
        if contexts[0] == 2:
            now[0] = 1046
    worker.validator = validator
    worker.run_one()
    assert repo.latest_record('observation', binding['id']) is None
    assert jobs.public(binding['id'])['state'] == 'checking'
    worker.close()

@pytest.mark.parametrize('phase', [1, 2])
def test_expired_context_failure_cannot_pause_or_start_network(tmp_path, phase):
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    now, contexts, calls = [1000], [0], []
    worker = manager(Service(db), reader(lambda pin: calls.append(pin['id']) or data(pin)), now)
    def validator(*args):
        contexts[0] += 1
        if contexts[0] == phase:
            now[0] = 1046
            raise ValueError('configuration changed during slow context')
    worker.validator = validator
    worker.run_one()
    assert len(calls) == phase - 1
    assert repo.latest_control(binding['id'])['generation'] == 1
    assert repo.latest_control(binding['id'])['enabled']
    assert jobs.public(binding['id'])['state'] == 'checking'
    assert repo.latest_record('observation', binding['id']) is None


def test_paused_inflight_response_retains_only_provider_cooldown(tmp_path):
    from backend.canvas.opora_reconciliation_finish import system_pause
    db, repo, jobs, binding = setup(tmp_path / 'state.sqlite')
    now = [1000]
    def read(pin):
        with db:
            db.execute('BEGIN IMMEDIATE')
            system_pause(repo, jobs, binding, now[0], 'subscription-context-changed')
        raise GitHubMergeError('github-rate-limit', retry_after=600)
    worker = manager(Service(db), reader(read), now)
    worker.run_one()
    row = jobs.read(binding['id'])
    assert row['state'] == 'paused' and row['generation'] == 2
    assert row['provider_retry_until'] == 1600
    assert row['last_observation_id'] is None and row['last_event_id'] is None
    assert len(repo.records('control', binding['id'])) == 2
    assert repo.latest_record('observation', binding['id']) is None
    restart = manager(Service(db), reader(lambda _: pytest.fail('provider cooldown bypass')), now)
    assert restart.run_one() is None
    assert restart.cooldown_until == 1600


def test_retry_pause_and_recovery_go_to_the_error_journal(tmp_path, monkeypatch):
    from backend.app import error_log

    records, resolved = [], []
    monkeypatch.setattr(error_log, 'submit', lambda source, kind, message, **kw: records.append((source, kind, kw)))
    monkeypatch.setattr(error_log, 'resolve', lambda **kw: resolved.append(kw))
    db, _, _, binding = setup(tmp_path / 'state.sqlite')
    now = [1000]
    worker = manager(Service(db), reader(lambda pin: (_ for _ in ()).throw(GitHubMergeError())), now)
    worker.run_one()
    [(source, kind, kw)] = records
    assert (source, kind, kw['subject'], kw['project'], kw['severity']) == (
        'card', 'exception', binding['id'], binding['project'], 'warn')
    worker.reader = reader(lambda pin: data(pin, 'open'))
    now[0] = 5000
    worker.run_one()
    assert resolved == [{'source': 'card', 'project': binding['project'], 'subject': binding['id']}]
    worker.reader = reader(lambda pin: (_ for _ in ()).throw(GitHubMergeError('github-auth-missing',
                                                                               action_required=True)))
    now[0] = 9000
    worker.run_one()
    assert records[-1][1] == 'blocked' and records[-1][2]['data']['code'] == 'github-auth-missing'
