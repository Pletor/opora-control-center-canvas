"""Sdílené fixtury testů srdce: místní web pro stažení a ověření výzkumu (test_research_fetch, test_research_verify)."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

DOC = ("<html><head><title>Doc</title><style>.x{color:red}</style><script>var secret = 'skryto';</script></head>"
       "<body><h1>Rate limiting</h1><p>Redis &amp; Lua: the INCR command is atomic, so a counter per user and "
       "window works across many instances.</p>" + "<p>Výplň dokumentace o limitech a oknech. </p>" * 12
       + "</body></html>").encode("utf-8")


class _Site(BaseHTTPRequestHandler):
    PAGES: ClassVar = {"/index.html": b'<html><head><link rel="stylesheet" href="s.css"><link rel="icon" href="i.png">'
                            b'<script src="/js/app.js"></script><script src="https://cdn.example/x.js"></script>'
                            b'<script src="big.js"></script><script>inline()</script></head></html>',
             "/s.css": b"body{}", "/js/app.js": b"go()", "/big.js": b"x" * 2000, "/i.png": b"png",
             "/doc": DOC, "/short": b"<html><body><div id=root></div></body></html>",
             "/plain": ("Plain text release notes: version 5.0 drops Node 16. " * 12).encode()}
    hits: ClassVar = []

    def do_GET(self):
        self.hits.append(self.path)
        body = self.PAGES.get(self.path.split("?")[0])
        self.send_response(200 if body is not None else 404)
        self.end_headers()
        self.wfile.write(body or b"")

    def log_message(self, *args):
        pass


@pytest.fixture
def site():
    _Site.hits.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
