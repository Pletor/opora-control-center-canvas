"""Klient brány proti falešnému serveru: relace a token v .opora/, .gitignore, next/ask/report/release, kurzor schránky a 4xx."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import opora_gate

TOKEN = "t" * 43


class FakeGate(BaseHTTPRequestHandler):
    seen: ClassVar[list] = []

    def log_message(self, *args):
        pass

    def _send(self, status, body):
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.seen.append(("POST", self.path, body, self.headers.get(opora_gate.HEADER), self.headers.get("Origin")))
        if self.path == "/api/gate/sessions":
            return self._send(201, {"sessionId": "gs_1", "token": TOKEN, "expiresAt": "2026-10-29T18:00:00Z"})
        if body["kind"] == "report" and body["body"]["taskId"] == "ht_cizi":
            return self._send(409, {"error": "Úkol není přidělený.", "code": "task_not_assigned", "hint": "Použijte next."})
        return self._send(201, {"ticketId": "gt_1", "seq": 1, "kind": body["kind"], "status": "answered",
                                "answer": {"echo": body["body"]}})

    def do_GET(self):
        url = urlsplit(self.path)
        query = {key: value[0] for key, value in parse_qs(url.query).items()}
        self.seen.append(("GET", url.path, query, self.headers.get(opora_gate.HEADER), self.headers.get("Origin")))
        after = int(query["after"])
        self._send(200, {"tickets": [{"answeredSeq": after + 1}], "last": after + 1})


@pytest.fixture
def server(monkeypatch):
    FakeGate.seen = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeGate)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("OPORA_BASE_URL", f"http://127.0.0.1:{httpd.server_address[1]}")
    yield FakeGate.seen
    httpd.shutdown()


def run(cwd, capsys, *argv):
    code = opora_gate.main(list(argv), cwd=cwd)
    return code, json.loads(capsys.readouterr().out)


def test_session_stores_token_and_ignores_opora_dir(server, tmp_path, capsys):
    (tmp_path / ".gitignore").write_text("node_modules/", "utf-8")
    code, out = run(tmp_path, capsys, "session", "--project", "draft", "--workspace", "draft", "--name", "dev")
    assert code == 0 and out["sessionId"] == "gs_1" and TOKEN not in json.dumps(out)
    assert json.loads((tmp_path / ".opora" / "gate.json").read_text("utf-8"))["token"] == TOKEN
    assert (tmp_path / ".gitignore").read_text("utf-8") == "node_modules/\n.opora/\n"
    run(tmp_path, capsys, "session", "--project", "draft", "--workspace", "draft", "--name", "dev")
    assert (tmp_path / ".gitignore").read_text("utf-8").count(".opora/") == 1
    assert server[0][2] == {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}}


def test_requests_carry_token_and_bodies(server, tmp_path, capsys):
    run(tmp_path, capsys, "session", "--project", "draft", "--workspace", "draft", "--name", "dev")
    assert run(tmp_path, capsys, "next")[1]["answer"] == {"echo": {}}
    assert run(tmp_path, capsys, "ask", "Smím?")[1]["answer"] == {"echo": {"question": "Smím?"}}
    answer = run(tmp_path, capsys, "change", "Přidej kartu Kontakt.", "--reason", "Záměr člověka.")[1]["answer"]
    assert answer == {"echo": {"proposal": "Přidej kartu Kontakt.", "reason": "Záměr člověka."}}
    code, out = run(tmp_path, capsys, "report", "--task", "ht_1", "--sha", "abc1234", "--summary", "ok",
                    "--check", "npm test=green", "--check", "a=b=red")
    assert code == 0 and out["answer"]["echo"]["checks"] == [{"name": "npm test", "status": "green"},
                                                             {"name": "a=b", "status": "red"}]
    code, out = run(tmp_path, capsys, "release", "--task", "ht_1", "--reason", "Nestihnu.")
    assert code == 0 and server[-1][2] == {"kind": "release", "body": {"taskId": "ht_1", "reason": "Nestihnu."}}
    assert all(item[3] == TOKEN and item[4].startswith("http://127.0.0.1:") for item in server[1:])


def test_inbox_moves_the_cursor(server, tmp_path, capsys):
    run(tmp_path, capsys, "session", "--project", "draft", "--workspace", "draft", "--name", "dev")
    assert run(tmp_path, capsys, "inbox")[1]["last"] == 1
    assert run(tmp_path, capsys, "inbox", "--wait", "2")[1]["last"] == 2
    assert server[-1][2] == {"after": "1", "wait": "2"}


def test_refusals_exit_non_zero_with_code_and_hint(server, tmp_path, capsys):
    code, out = run(tmp_path, capsys, "next")
    assert code == opora_gate.EXIT_CLIENT and "session" in out["hint"]
    run(tmp_path, capsys, "session", "--project", "draft", "--workspace", "draft", "--name", "dev")
    code, out = run(tmp_path, capsys, "report", "--task", "ht_cizi", "--sha", "abc1234", "--summary", "x",
                    "--check", "t=green")
    assert code == opora_gate.EXIT_REFUSED and out["status"] == 409
    assert (out["code"], out["hint"]) == ("task_not_assigned", "Použijte next.")
    code, out = run(tmp_path, capsys, "report", "--task", "ht_1", "--sha", "abc1234", "--summary", "x",
                    "--check", "t=yellow")
    assert code == opora_gate.EXIT_CLIENT


def test_server_down_is_a_client_error(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("OPORA_BASE_URL", "http://127.0.0.1:9")
    code, out = run(tmp_path, capsys, "session", "--project", "draft", "--workspace", "draft", "--name", "dev")
    assert code == opora_gate.EXIT_CLIENT and out["hint"]
