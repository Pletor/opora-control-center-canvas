"""Bounded lifecycle reads, pinned IDs, deleted forks and transport isolation."""
import io
import urllib.error
from types import SimpleNamespace

import pytest

from backend.integrations.github_merge_reader import GitHubMergeReader, normalize
from backend.integrations.github_merge_transport import (
    MAX_BYTES,
    GitHubMergeError,
    GitHubMergeTransport,
    cooldown,
)

PIN = {'repository': {'id': 1, 'fullName': 'owner/repo', 'baseBranch': 'main'},
       'pr': {'id': 107, 'number': 7, 'headRepoId': 2}}


def pull(merged=True):
    return {'id': 107, 'number': 7, 'base': {'repo': {'id': 1, 'full_name': 'owner/repo'}, 'ref': 'main'},
            'head': {'repo': None, 'sha': 'a' * 40}, 'state': 'closed' if merged else 'open',
            'draft': False, 'merged': merged, 'merged_at': '2026-01-01T00:00:00Z' if merged else None,
            'merge_commit_sha': 'b' * 40}


def test_deleted_fork_can_publish_but_replacement_is_action_required():
    assert normalize(pull(), PIN)['headRepoId'] is None
    value = pull()
    value['head']['repo'] = {'id': 8}
    with pytest.raises(GitHubMergeError) as failure:
        normalize(value, PIN)
    assert failure.value.action_required
    value = pull(False)
    assert normalize(value, PIN)['mergeCommitSha'] is None


@pytest.mark.parametrize('mutate', [lambda x: x.update(merged=None), lambda x: x.update(merged_at=None),
    lambda x: x.update(state='open'), lambda x: x.update(id=108),
    lambda x: x['base'].update(ref='other'), lambda x: x['base']['repo'].update(id=8),
    lambda x: x.update(id=True), lambda x: x.update(id=2**54)])
def test_incomplete_or_retargeted_data_rejected(mutate):
    value = pull()
    mutate(value)
    with pytest.raises(GitHubMergeError):
        normalize(value, PIN)


def test_three_calls_serial_cadence_and_mid_collection_cooldown():
    now, starts = [0], []
    def sleep(duration):
        now[0] += duration
    def transport(path, timeout):
        starts.append(now[0])
        return ({'id': 1, 'full_name': 'owner/repo'} if len(starts) == 1 else pull()), {}
    source = GitHubMergeReader(transport, monotonic=lambda: now[0], sleep=sleep)
    assert source.read(PIN)['pr']['state'] == 'merged'
    assert starts == [0, 1, 2]
    starts.clear()
    source = GitHubMergeReader(lambda *a, **k: (starts.append(1) or {'id': 1, 'full_name': 'owner/repo'},
        {'Retry-After': '120'}), sleep=lambda _: None)
    with pytest.raises(GitHubMergeError) as failure:
        source.read(PIN)
    assert len(starts) == 1
    assert failure.value.retry_after == 120


class Response:
    status, headers = 200, {}
    def __init__(self, payload):
        self.stream = io.BytesIO(payload)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read1(self, size):
        return self.stream.read(size)


def test_transport_fixed_origin_env_only_get_and_size(monkeypatch):
    requests = []
    monkeypatch.setenv('OPORA_GITHUB_TOKEN', 'private-token')
    def open_request(request, **kwargs):
        requests.append(request)
        return Response(b'{}')
    transport = GitHubMergeTransport(opener=SimpleNamespace(open=open_request))
    assert transport('/repos/owner/repo', timeout=3)[0] == {}
    assert requests[0].full_url == 'https://api.github.com/repos/owner/repo'
    assert requests[0].method == 'GET'
    assert requests[0].headers['Authorization'] == 'Bearer private-token'
    for path in ('https://evil.invalid', '/repos/owner/repo/../../token', '/repos/owner/repo?token=secret'):
        with pytest.raises(GitHubMergeError):
            transport(path, timeout=3)
    transport = GitHubMergeTransport(opener=SimpleNamespace(open=lambda *a, **k: Response(b'x' * (MAX_BYTES + 1))))
    with pytest.raises(GitHubMergeError, match='too-large'):
        transport('/repos/owner/repo', timeout=3)


def test_slow_drip_hits_absolute_deadline_and_sanitizes_http(monkeypatch):
    now = [0]
    monkeypatch.setattr('backend.integrations.github_merge_transport.time.monotonic', lambda: now[0])
    class Slow(Response):
        def read1(self, size):
            now[0] += 0.4
            return b' '
    source = GitHubMergeTransport(opener=SimpleNamespace(open=lambda *a, **k: Slow(b'')))
    with pytest.raises(GitHubMergeError, match='timeout'):
        source('/repos/owner/repo', timeout=1)
    assert now[0] < 1.5
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://secret.invalid', 429, 'private body', {'Retry-After': '50'}, None)
    source = GitHubMergeTransport(opener=SimpleNamespace(open=fail))
    with pytest.raises(GitHubMergeError) as failure:
        source('/repos/owner/repo', timeout=3)
    assert str(failure.value) == 'github-rate-limit'
    assert failure.value.retry_after == 60
    assert cooldown({'Retry-After': 'Infinity'}) == 86400

@pytest.mark.parametrize('status', [401, 403, 404])
def test_private_repository_without_token_is_auth_missing_not_unavailable(monkeypatch, status):
    for name in ('OPORA_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN'):
        monkeypatch.delenv(name, raising=False)
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://secret.invalid', status, 'Not Found', {}, None)
    source = GitHubMergeTransport(opener=SimpleNamespace(open=fail))
    with pytest.raises(GitHubMergeError) as failure:
        source('/repos/owner/private/pulls/7', timeout=3)
    assert failure.value.code == 'github-auth-missing' and failure.value.action_required
    monkeypatch.setenv('GH_TOKEN', 'present')  # With a token the same answer stays a GitHub-side failure.
    with pytest.raises(GitHubMergeError) as failure:
        source('/repos/owner/private/pulls/7', timeout=3)
    assert failure.value.code == ('github-auth-invalid' if status == 401 else 'github-unavailable')
    assert failure.value.action_required


def test_default_transport_disables_proxy_and_redirects(monkeypatch):
    handlers = []
    def build(*supplied):
        handlers.extend(supplied)
        return object()
    monkeypatch.setattr('urllib.request.build_opener', build)
    GitHubMergeTransport()
    assert handlers[0].proxies == {}
    assert handlers[1].redirect_request(None, None, 302, '', {}, 'https://evil.invalid') is None
