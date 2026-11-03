"""Integrační test `journey_run.py --intent` nad lokálním http.serverem; přeskočí se, když chybí Python Playwright."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("playwright.sync_api")

from tools import journey_run

PAGES = {
    "/video": '<section data-opora-section="form"><form action="/dekujeme"><input name="email">'
              '<button>Chci video</button></form></section>',
    "/dekujeme": "<h1>Děkujeme</h1>",
}
FORM = '[data-opora-section="form"]'
PLAN = {"schema": "opora.intent-plan/1", "pageId": "landing", "workflowVersionId": "v1",
        "digest": "sha256:" + "a" * 64, "path": "/video",
        "nodes": [{"nodeId": "type", "kind": "step", "do": "type", "scope": FORM, "text": "a@b.cz"},
                  {"nodeId": "send", "kind": "step", "do": "submit", "scope": FORM},
                  {"nodeId": "mail", "kind": "expect", "check": "email", "value": "e-mail"},
                  {"nodeId": "seen", "kind": "expect", "check": "visible", "value": "Děkujeme"},
                  {"nodeId": "ok", "kind": "expect", "check": "path", "value": "/dekujeme"}]}
posted: list[dict] = []


@pytest.fixture
def site():
    posted.clear()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/project-architecture/intent-plan":
                body, kind = json.dumps({**PLAN, "baseUrl": base}).encode(), "application/json"
            elif path in PAGES:
                body, kind = f"<!doctype html><meta charset=utf-8>{PAGES[path]}".encode(), "text/html"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            posted.append({"path": self.path, "run": json.loads(body)})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"stale": false}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield base
    server.shutdown()


def test_intent_run_replays_the_page_and_posts_the_run(site):
    assert journey_run.main(["--server", site, "--project", "p", "--intent", "landing"]) == 0
    [call] = posted
    assert call["path"] == "/api/project-architecture/intent-runs?project=p"
    assert [(n["nodeId"], n["ok"]) for n in call["run"]["nodes"]] == [
        ("type", True), ("send", True), ("mail", None), ("seen", True), ("ok", True)]
