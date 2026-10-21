"""Small bounded PR lifecycle reader; independent of review-policy evidence."""
import re
import time
from datetime import UTC, datetime

from backend.integrations.github_merge_transport import (
    GitHubMergeError,
    GitHubMergeTransport,
    cooldown,
)


def require(condition, *, identity=False):
    if not condition:
        raise GitHubMergeError('github-identity-mismatch' if identity else 'github-malformed', action_required=identity)


def positive(value):
    require(type(value) is int and 1 <= value <= 9007199254740991)
    return value


def sha(value):
    require(isinstance(value, str) and re.fullmatch('[a-f0-9]{40}', value) is not None)
    return value


def stamp():
    return datetime.now(UTC).isoformat()


def normalize(value, binding):
    require(isinstance(value, dict))
    base, head = value.get('base'), value.get('head')
    require(isinstance(base, dict) and isinstance(head, dict) and isinstance(base.get('repo'), dict))
    repo, pin = binding['repository'], binding['pr']
    require(positive(base['repo'].get('id')) == repo['id']
            and str(base['repo'].get('full_name', '')).casefold() == repo['fullName'].casefold()
            and positive(value.get('id')) == pin['id'] and positive(value.get('number')) == pin['number']
            and base.get('ref') == repo['baseBranch'], identity=True)
    require('repo' in head and 'merged_at' in value and 'merge_commit_sha' in value)
    fork = head.get('repo')
    require(fork is None or isinstance(fork, dict))
    head_id = positive(fork.get('id')) if fork is not None else None
    require(head_id is None or head_id == pin['headRepoId'], identity=True)
    state, merged = value.get('state'), value.get('merged')
    require(state in ('open', 'closed') and type(merged) is bool and type(value.get('draft')) is bool)
    merged_at, commit = value.get('merged_at'), value.get('merge_commit_sha')
    if merged:
        require(state == 'closed' and isinstance(merged_at, str) and len(merged_at) <= 50)
        try:
            parsed = datetime.fromisoformat(merged_at)
            require(parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0)
        except (ValueError, OverflowError):
            raise GitHubMergeError('github-malformed') from None
        merged_at = parsed.astimezone(UTC).isoformat()
        commit = sha(commit)
    else:
        require(merged_at is None)
        commit = None  # GitHub's pre-merge test commit is not publication evidence.
    return {'id': pin['id'], 'number': pin['number'], 'baseRef': repo['baseBranch'],
            'headSha': sha(head.get('sha')), 'headRepoId': head_id,
            'state': 'merged' if merged else 'open' if state == 'open' else 'closed-unmerged',
            'draft': value['draft'], 'merged': merged, 'mergedAt': merged_at, 'mergeCommitSha': commit}


class GitHubMergeReader:
    deadline_seconds = 25

    def __init__(self, transport=None, *, monotonic=time.monotonic, sleep=time.sleep):
        self.transport, self.monotonic = transport or GitHubMergeTransport(), monotonic
        self.retry_after, self.sleep, self.last_call = 0, sleep, None

    def read(self, binding):
        start, observed_from = self.monotonic(), stamp()
        self.retry_after = 0

        def get(path):
            if self.retry_after:
                raise GitHubMergeError('github-rate-limit', retry_after=self.retry_after)
            if self.last_call is not None:
                self.sleep(max(0, self.last_call + 1 - self.monotonic()))
            remaining = self.deadline_seconds - (self.monotonic() - start)
            if remaining <= 0:
                raise GitHubMergeError('github-timeout')
            self.last_call = self.monotonic()
            data, headers = self.transport(path, timeout=min(8, remaining))
            self.retry_after = max(self.retry_after, cooldown(headers))
            if self.monotonic() - start >= self.deadline_seconds:
                raise GitHubMergeError('github-timeout')
            return data

        repo = binding['repository']
        require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo['fullName']) is not None)
        path = '/repos/' + repo['fullName']
        actual = get(path)
        require(isinstance(actual, dict))
        require(positive(actual.get('id')) == repo['id']
                and str(actual.get('full_name', '')).casefold() == repo['fullName'].casefold(), identity=True)
        pull_path = path + '/pulls/' + str(binding['pr']['number'])
        first = normalize(get(pull_path), binding)
        second = normalize(get(pull_path), binding)
        require(first == second)
        return {'complete': True, 'observedFrom': observed_from, 'observedUntil': stamp(),
                'repository': {'id': repo['id'], 'fullName': repo['fullName'].casefold()}, 'pr': second}
