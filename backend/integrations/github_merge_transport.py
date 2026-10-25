"""Fixed-origin GET-only lifecycle transport with sanitized provider cooldown metadata."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime

from backend.integrations.github_review_transport import ORIGIN, _NoRedirect

MAX_BYTES = 256 * 1024


class GitHubMergeError(ValueError):
    def __init__(self, code='github-unavailable', *, retry_after=0, action_required=False):
        super().__init__(code)
        self.code, self.retry_after, self.action_required = code, retry_after, action_required


def cooldown(headers, now=None):
    now = time.time() if now is None else now
    headers = {str(k).lower(): str(v) for k, v in headers.items()}
    wait = 0
    retry = headers.get('retry-after', '')
    try:
        wait = float(retry)
    except ValueError:
        try:
            wait = parsedate_to_datetime(retry).timestamp() - now
        except (ValueError, TypeError, OverflowError):
            pass
    if headers.get('x-ratelimit-remaining') == '0':
        try:
            wait = max(wait, float(headers.get('x-ratelimit-reset', '0')) - now)
        except ValueError:
            pass
    return min(86400, max(0, wait))


TOKEN_VARIABLES = ('OPORA_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN')


def github_token():
    return next((os.environ[k] for k in TOKEN_VARIABLES if os.environ.get(k)), '')


class GitHubMergeTransport:
    def __init__(self, *, opener=None):
        self._opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def __call__(self, path, *, timeout):
        if (not isinstance(path, str) or not re.fullmatch(r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/pulls/[1-9][0-9]*'
                                                         r'|/pulls\?state=all&sort=updated&direction=desc&per_page=[1-9][0-9]?)?', path)
                or '..' in path or timeout <= 0):
            raise GitHubMergeError('invalid-read-request', action_required=True)
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'OporaHub',
                   'X-GitHub-Api-Version': '2022-11-28'}
        token = github_token()
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(ORIGIN + path, headers=headers, method='GET')
        deadline = time.monotonic() + min(timeout, 8)
        try:
            with self._opener.open(request, timeout=min(timeout, 8)) as response:
                metadata = dict(response.headers.items())
                if response.status != 200:
                    raise GitHubMergeError('github-unavailable', retry_after=cooldown(metadata))
                chunks, size = [], 0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise GitHubMergeError('github-timeout')
                    # read1 performs one buffered/raw read, unlike read(n), which can
                    # wait indefinitely for n trickled bytes. Rebound the live socket
                    # to the absolute remaining budget before every raw read.
                    sock = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
                    if sock is not None:
                        sock.settimeout(remaining)
                    chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                    if time.monotonic() >= deadline:
                        raise GitHubMergeError('github-timeout')
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise GitHubMergeError('github-response-too-large')
                raw = b''.join(chunks)
                return json.loads(raw), metadata
        except urllib.error.HTTPError as error:
            wait = cooldown(error.headers or {})
            rate = error.code == 429 or (error.code == 403 and wait > 0)
            if error.code in (401, 403, 404) and not rate and not token:
                # A private repository answers 404/401 to an anonymous read: the token is missing, GitHub is fine.
                raise GitHubMergeError('github-auth-missing', action_required=True) from None
            raise GitHubMergeError('github-rate-limit' if rate else 'github-unavailable',
                                   retry_after=max(60, wait) if rate else wait,
                                   action_required=error.code in (401, 403, 404) and not rate) from None
        except (OSError, ValueError) as error:
            if isinstance(error, GitHubMergeError):
                raise
            raise GitHubMergeError() from None
