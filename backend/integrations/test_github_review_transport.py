"""The transport cannot follow redirects, leak error bodies, or accept oversized JSON."""
import io
import json
import urllib.error
import urllib.request

import pytest

from backend.integrations import github_review_transport as module
from backend.integrations.github_review_transport import GitHubReadError, GitHubReviewTransport


class Response:
    status = 200
    def __init__(self, raw):
        self.raw = raw
        self.headers = {"Link": "next"}

    def read(self, limit):
        return self.raw[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Opener:
    def __init__(self, raw=b'{}', error=None):
        self.raw, self.error, self.calls = raw, error, []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return Response(self.raw)


def test_get_has_fixed_origin_server_token_and_bounded_timeout(monkeypatch):
    monkeypatch.setenv("OPORA_GITHUB_TOKEN", "server-secret")
    opener = Opener(json.dumps({"id": 7}).encode())
    data, headers = GitHubReviewTransport(opener=opener)("/repos/a/b", timeout=30)
    request, timeout = opener.calls[0]
    assert request.full_url == "https://api.github.com/repos/a/b"
    assert request.get_method() == "GET" and request.data is None
    assert request.get_header("Authorization") == "Bearer server-secret"
    assert timeout == 10 and data == {"id": 7} and headers == {"link": "next"}


@pytest.mark.parametrize("path", ["https://evil.test", "//evil.test", "/repos/a/b/../secret", "/repos/a/b#x", "/repos/a/b\r\nX: secret"])
def test_untrusted_paths_never_open(path):
    opener = Opener()
    with pytest.raises(GitHubReadError):
        GitHubReviewTransport(opener=opener)(path, timeout=10)
    assert not opener.calls


def test_default_opener_blocks_redirects():
    transport = GitHubReviewTransport(token="")
    redirects = [h for h in transport._opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
    assert len(redirects) == 1
    assert redirects[0].redirect_request(None, None, 302, "", {}, "https://evil.test") is None


@pytest.mark.parametrize("error", [OSError("server-secret"), urllib.error.HTTPError("https://example", 403, "server-secret", {}, io.BytesIO(b"server-secret"))])
def test_errors_are_sanitized(error):
    with pytest.raises(GitHubReadError) as raised:
        GitHubReviewTransport(opener=Opener(error=error))("/repos/a/b", timeout=10)
    assert "server-secret" not in str(raised.value)
    assert raised.value.__suppress_context__


@pytest.mark.parametrize("raw", [b"not JSON", b"\xff", b"{}" * 10])
def test_oversized_or_malformed_response_fails(monkeypatch, raw):
    monkeypatch.setattr(module, "MAX_BYTES", 10)
    with pytest.raises(GitHubReadError):
        GitHubReviewTransport(opener=Opener(raw))("/repos/a/b", timeout=10)
