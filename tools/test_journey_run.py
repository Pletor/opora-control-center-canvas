"""Integrační test runneru nad lokálním http.serverem; přeskočí se, když chybí Python Playwright."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("playwright.sync_api")

from tools import journey_run, journey_run_browser

PAGES = {
    "/": '<form data-opora-section="form" action="/novinky"><label>E-mail <input name="email"></label>'
         '<button>Chci video zdarma</button></form>',
    "/novinky": '<section data-opora-section="cta"><a href="/pribeh/">Pokračovat</a></section>'
                '<nav><a href="/kontakt">Kontakt</a></nav>',
    "/pribeh": "<h1>Příběh</h1>",
}


def _plan(base):
    return {
        "schema": "opora.journey-plan/1", "applicationId": "web", "journeyId": "kampan", "name": "Kampaň",
        "baseUrl": base, "digest": "sha256:" + "b" * 64,
        "segments": [
            {"from": "s1", "to": "s2", "open": "/", "scope": '[data-opora-section="form"]', "do": "submit",
             "text": "Chci video zdarma", "expectPath": "/novinky"},
            {"from": "s2", "to": "s3", "open": "/novinky", "scope": '[data-opora-section="cta"]', "do": "click",
             "expectPath": "/pribeh"},
        ],
    }


posted: list[dict] = []


@pytest.fixture
def site():
    posted.clear()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0].rstrip("/") or "/"
            if path == "/api/project-architecture/journey-plan":
                body, kind = json.dumps(_plan(base)).encode(), "application/json"
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
            posted.append({"path": self.path, "origin": self.headers["Origin"],
                           "type": self.headers["Content-Type"], "run": json.loads(body)})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"recordedAt": "2026-10-27T21:40:01Z"}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield base
    server.shutdown()


def test_replay_passes_with_fixtures(site):
    results = journey_run_browser.replay(_plan(site), site, {"kampan/s2": {"E-mail": "a@b.cz"}}, False, lambda _: None)
    assert [(r["to"], r["ok"]) for r in results] == [("s2", True), ("s3", True)]


def test_replay_reports_reasons(site):
    plan = _plan(site)
    plan["segments"][1]["scope"] = '[data-opora-section="chybi"]'
    results = journey_run_browser.replay(plan, site, {}, False, lambda _: None)
    assert results[0]["ok"] is False and results[0]["reason"] == "chybí data formuláře"
    assert results[1]["ok"] is False and "chybí" in results[1]["reason"]


def test_main_dry_run(site, tmp_path, capsys):
    fixtures = tmp_path / "f.json"
    fixtures.write_text(json.dumps({"kampan/s2": {"input[name=email]": "a@b.cz"}}), encoding="utf-8")
    log = tmp_path / "beh.log"
    code = journey_run.main(["--server", site, "--project", "p", "--journey", "kampan",
                             "--fixtures", str(fixtures), "--dry-run", "--log", str(log)])
    run = json.loads(capsys.readouterr().out)
    assert code == 0
    assert run["schema"] == "opora.journey-run/1" and all(s["ok"] for s in run["segments"])
    assert run["logUrl"].startswith("file:") and "s2 -> s3: ok" in log.read_text(encoding="utf-8")


def test_main_posts_run_with_origin(site):
    code = journey_run.main(["--server", site, "--project", "p", "--journey", "kampan"])
    assert code == 1  # bez fixtures formulář neprojde
    [call] = posted
    assert call["path"] == "/api/project-architecture/journey-runs?project=p"
    assert call["origin"] == site and call["type"] == "application/json"
    assert call["run"]["segments"][0] == {"from": "s1", "to": "s2", "ok": False, "reason": "chybí data formuláře"}
