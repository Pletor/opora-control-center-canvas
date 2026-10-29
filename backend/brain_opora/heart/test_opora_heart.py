"""Nástroj srdce proti falešnému serveru: hlavičky, tvar úkolu, odpověď, zrušení, eskalace, paměť (`decide`, `rule`),
`done` a chyby."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.brain_opora.heart import opora_heart


class Handler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        return

    def _reply(self, status, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _handle(self, method):
        url = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        Handler.calls.append({"method": method, "path": url.path, "query": parse_qs(url.query), "body": body,
                              "headers": dict(self.headers)})
        if url.path == "/api/brain/heart/snapshot":
            return self._reply(200, {"snapshot": "PROJEKT p1\nPLÁN:"})
        if url.path == "/api/brain/tasks":
            return self._reply(201, {"taskId": "ht_1", "title": body["title"], "status": "ready", "order": 1})
        if url.path.endswith("/answer"):
            return self._reply(200, {"ticketId": "gt_1", "status": "answered", "answeredBy": "heart"})
        if url.path.startswith("/api/desktop-v3/"):
            return self._reply(200, {"revision": 2, "item": {**body["item"], "by": "agent"}})
        if url.path.endswith("/cancel"):
            return self._reply(409, {"error": "uzavřený", "code": "task_closed", "hint": "Jen ready nebo assigned."})
        return self._reply(201, {"ticketId": "gt_2", "kind": "ask", "status": "queued"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


@pytest.fixture
def server(monkeypatch, tmp_path):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    for key, value in {"OPORA_BASE_URL": base, "OPORA_HEART_TOKEN": "tok-heart", "OPORA_PROJECT": "p1",
                       "OPORA_WORKSPACE": "main"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    Handler.calls = []
    yield base
    httpd.shutdown()


def run(capsys, *argv):
    code = opora_heart.main(list(argv))
    return code, capsys.readouterr().out.strip()


def test_task_sends_the_fixed_shape_with_the_heart_token(server, capsys):
    code, out = run(capsys, "task", "--title", "Hero", "--do", "Udělej hero.", "--why", "Proč", "--file", "a.tsx",
                    "--done-when", "npm test projde", "--dont-touch", "nav.tsx@úkol navigace", "--rule", "Česky",
                    "--intent", "klid", "--order", "1", "--node", "home", "--model", "opus")
    assert code == 0 and json.loads(out) == {"taskId": "ht_1", "title": "Hero", "status": "ready", "order": 1}
    call = Handler.calls[0]
    assert call["headers"]["X-Opora-Gate-Token"] == "tok-heart" and call["headers"]["Origin"] == server
    assert call["headers"]["X-Opora-Actor"] == "agent; name=heart"
    assert call["body"] == {"project": "p1", "workspace": "main", "title": "Hero", "nodeId": "home", "order": 1,
                            "body": {"do": "Udělej hero.", "why": "Proč", "files": ["a.tsx"],
                                     "doneWhen": ["npm test projde"], "commit": "", "model": "opus",
                                     "dontTouch": [{"path": "nav.tsx", "heldBy": "úkol navigace"}],
                                     "context": {"rules": ["Česky"], "intent": "klid"}}}


def test_snapshot_answer_escalate_and_done(server, capsys, tmp_path):
    assert run(capsys, "snapshot") == (0, "PROJEKT p1\nPLÁN:")
    code, out = run(capsys, "answer", "--ticket", "gt_1", "--text", "Ano.")
    assert code == 0 and json.loads(out)["answeredBy"] == "heart"
    answer = Handler.calls[-1]
    assert answer["query"] == {"project": ["p1"]} and answer["body"] == {"answer": {"text": "Ano."}}
    assert json.loads(run(capsys, "escalate", "--text", "Rozhodni barvu.")[1])["kind"] == "ask"
    assert Handler.calls[-1]["body"] == {"project": "p1", "workspace": "main", "text": "Rozhodni barvu."}
    assert run(capsys, "done", "--summary", "Dva úkoly.") == (0, '{"done": true}')
    assert json.loads((tmp_path / "last_done.json").read_text(encoding="utf-8"))["summary"] == "Dva úkoly."


def test_errors_print_code_and_hint(server, capsys, monkeypatch):
    code, out = run(capsys, "cancel", "--task", "ht_1")
    assert code == 1 and json.loads(out)["code"] == "task_closed" and json.loads(out)["hint"]
    monkeypatch.delenv("OPORA_HEART_TOKEN")
    code, out = run(capsys, "snapshot")
    assert code == 1 and json.loads(out)["code"] == "heart_env_missing"
    monkeypatch.setenv("OPORA_HEART_TOKEN", "t")
    monkeypatch.setenv("OPORA_BASE_URL", "http://127.0.0.1:9")
    assert json.loads(run(capsys, "snapshot")[1])["code"] == "server_unreachable"


def test_decide_and_rule_add_memory_items_in_the_fixed_shape(server, capsys):
    code, out = run(capsys, "decide", "--text", "Test h1 smí upravit úkol hero.", "--node", "home", "--pin")
    decision = Handler.calls[-1]["body"]
    assert code == 0 and Handler.calls[-1]["path"] == "/api/desktop-v3/decision"
    item = decision["item"]
    assert {key: decision[key] for key in ("project", "workspace", "op", "expected")} == {
        "project": "p1", "workspace": "main", "op": "add", "expected": None}
    assert decision["id"] == item["id"] and item["id"].startswith("hd_") and item["createdAt"].endswith("Z")
    assert {key: item[key] for key in ("text", "pinned", "path", "nodeId", "by")} == {
        "text": "Test h1 smí upravit úkol hero.", "pinned": True, "path": "", "nodeId": "home", "by": "agent"}
    assert json.loads(out) == {"id": item["id"], "text": item["text"], "by": "agent"}
    assert run(capsys, "decide", "--text", "Bez karty.")[0] == 0
    assert (Handler.calls[-1]["body"]["item"]["nodeId"], Handler.calls[-1]["body"]["item"]["pinned"]) == ("", False)
    code, out = run(capsys, "rule", "--text", "Texty česky, tykání.")
    rule = Handler.calls[-1]["body"]
    assert code == 0 and Handler.calls[-1]["path"] == "/api/desktop-v3/rule" and rule["id"].startswith("hr_")
    assert rule["item"] == {"id": rule["id"], "text": "Texty česky, tykání.", "kind": "must", "scope": "project",
                            "target": ""}
    assert json.loads(out)["by"] == "agent"
