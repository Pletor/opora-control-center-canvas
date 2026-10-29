"""Testy MCP serveru OPORY (docs/brain-control-api.md §3): server běží jako podproces proti falešné bráně."""
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SERVER = Path(__file__).with_name("opora_mcp.py")
SCHEMA = {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"],
          "additionalProperties": False}
WORKER_KINDS = [{"kind": "next", "description": "Další úkol.", "input": {"type": "object", "properties": {}}},
                {"kind": "ask", "description": "Otázka.", "input": SCHEMA},
                {"kind": "report", "description": "Hlášení.", "input": {"type": "object"}},
                {"kind": "inbox", "description": "Schránka.", "input": {"type": "object"}}]
HEART_KINDS = WORKER_KINDS + [{"kind": "task.create", "description": "Nový úkol.", "input": {"type": "object"}}]


class FakeGate(BaseHTTPRequestHandler):
    """Napodobí /api/gate/kinds, /sessions a /requests; každé volání zapíše do `server.calls`."""

    def log_message(self, *args):
        pass

    def reply(self, status, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        token = self.headers.get("X-Opora-Gate-Token")
        self.server.calls.append(("GET", self.path, token, None))
        kinds = HEART_KINDS if token == "heart-token" else WORKER_KINDS
        self.reply(200, {"role": "heart" if token == "heart-token" else "worker", "kinds": kinds})

    def do_POST(self):
        token = self.headers.get("X-Opora-Gate-Token")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"null")
        self.server.calls.append(("POST", self.path, token, body))
        if self.path == "/api/gate/sessions":
            return self.reply(201, {"sessionId": "gs_1", "token": "worker-token", "expiresAt": "2026-10-29T20:00:00Z"})
        if token not in ("worker-token", "heart-token"):
            return self.reply(401, {"error": "Token chybí.", "code": "gate_token_invalid", "hint": "Založte relaci."})
        kind = body["kind"]
        if kind == "report":
            return self.reply(403, {"error": "Cizí úkol.", "code": "task_not_assigned", "hint": "Hlaste jen svůj."})
        if kind == "ask":
            return self.reply(201, {"ticketId": "gt_ask", "seq": 3, "kind": "ask", "status": "queued"})
        if kind == "inbox":
            after = body["body"]["after"]
            box = ({"tickets": [{"ticketId": "gt_old", "answeredSeq": 1, "answer": {"text": "staré"}}], "last": 1}
                   if after == 0 else
                   {"tickets": [{"ticketId": "gt_ask", "answeredSeq": 2, "answer": {"text": "ano"}}], "last": 2})
            return self.reply(201, {"ticketId": "gt_box", "seq": 4, "kind": "inbox", "status": "answered",
                                    "answer": box})
        self.reply(201, {"ticketId": "gt_1", "seq": 1, "kind": kind, "status": "answered",
                         "answer": {"task": None, "plan": []}})


@pytest.fixture
def gate():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGate)
    server.calls = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def run_mcp(base, messages, **extra):
    """Pošle zprávy na stdin serveru (`-I`, bez repa na sys.path) a vrátí odpovědi ze stdout."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("OPORA_")}
    env.update({"OPORA_BASE_URL": base, "OPORA_PROJECT": "p1", "OPORA_WORKSPACE": "main", **extra})
    stdin = "".join(json.dumps(message) + "\n" for message in messages)
    done = subprocess.run([sys.executable, "-I", str(SERVER)], input=stdin.encode("utf-8"), capture_output=True,
                          env=env, timeout=60, check=True)
    return [json.loads(line) for line in done.stdout.decode("utf-8").splitlines()]


def url(server):
    return f"http://127.0.0.1:{server.server_address[1]}"


def rpc(mid, method, params=None):
    return {"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}


def call(mid, name, arguments=None):
    return rpc(mid, "tools/call", {"name": name, "arguments": arguments or {}})


def text(reply):
    return json.loads(reply["result"]["content"][0]["text"])


def test_initialize_list_and_call_for_worker(gate):
    replies = run_mcp(url(gate), [rpc(1, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}}),
                                  {"jsonrpc": "2.0", "method": "notifications/initialized"},
                                  rpc(2, "tools/list"), call(3, "opora_next")], OPORA_WORKER_NAME="dev-1")
    assert [reply["id"] for reply in replies] == [1, 2, 3]
    assert replies[0]["result"] == {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                                    "serverInfo": {"name": "opora", "version": replies[0]["result"]["serverInfo"]
                                                   ["version"]}}
    tools = {tool["name"]: tool for tool in replies[1]["result"]["tools"]}
    assert list(tools) == ["opora_next", "opora_ask", "opora_report", "opora_inbox"]
    assert tools["opora_ask"]["inputSchema"]["properties"]["wait"]["type"] == "boolean"
    assert tools["opora_ask"]["inputSchema"]["required"] == ["question"]
    assert tools["opora_inbox"]["inputSchema"] == {"type": "object"}
    assert text(replies[2]) == {"ticketId": "gt_1", "seq": 1, "kind": "next", "status": "answered",
                                "answer": {"task": None, "plan": []}}
    assert "isError" not in replies[2]["result"]
    assert gate.calls[0][:3] == ("GET", "/api/gate/kinds", None)  # druhy bez relace
    assert gate.calls[-1] == ("POST", "/api/gate/requests", "worker-token", {"kind": "next", "body": {}})


def test_worker_opens_one_session_for_many_calls(gate):
    run_mcp(url(gate), [call(1, "opora_next"), call(2, "opora_next")], OPORA_WORKER_NAME="dev-1")
    sessions = [entry for entry in gate.calls if entry[1] == "/api/gate/sessions"]
    assert sessions == [("POST", "/api/gate/sessions", None,
                         {"project": "p1", "workspace": "main", "worker": {"name": "dev-1"}})]
    assert sum(entry[1] == "/api/gate/requests" for entry in gate.calls) == 2


def test_heart_token_header_and_heart_kinds(gate):
    replies = run_mcp(url(gate), [rpc(1, "tools/list"), call(2, "opora_task_create", {"title": "T"})],
                      OPORA_HEART_TOKEN="heart-token")
    assert "opora_task_create" in [tool["name"] for tool in replies[0]["result"]["tools"]]
    assert all(entry[2] == "heart-token" for entry in gate.calls)
    assert not any(entry[1] == "/api/gate/sessions" for entry in gate.calls)
    assert gate.calls[-1][3] == {"kind": "task.create", "body": {"title": "T"}}


def test_gate_token_wins_and_is_sent(gate):
    run_mcp(url(gate), [call(1, "opora_next")], OPORA_GATE_TOKEN="heart-token", OPORA_WORKER_NAME="dev-1")
    assert {entry[2] for entry in gate.calls} == {"heart-token"}


def test_refusal_maps_to_is_error_with_code_and_hint(gate):
    replies = run_mcp(url(gate), [call(1, "opora_report", {"taskId": "ht_x"}), call(2, "opora_nope")],
                      OPORA_WORKER_NAME="dev-1")
    assert replies[0]["result"]["isError"] is True
    assert text(replies[0]) == {"status": 403, "code": "task_not_assigned", "error": "Cizí úkol.",
                                "hint": "Hlaste jen svůj."}
    assert replies[1]["result"]["isError"] is True and text(replies[1])["code"] == "unknown_tool"


def test_unreachable_server_says_opora_is_not_running():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    replies = run_mcp(f"http://127.0.0.1:{port}", [call(1, "opora_next")], OPORA_HEART_TOKEN="heart-token")
    assert replies[0]["result"]["isError"] is True
    assert text(replies[0])["code"] == "server_unreachable" and "neběží" in text(replies[0])["hint"]


def test_notifications_get_no_reply_and_unknown_method_is_32601(gate):
    replies = run_mcp(url(gate), [{"jsonrpc": "2.0", "method": "notifications/initialized"},
                                  {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}},
                                  rpc(1, "ping"), rpc(2, "resources/list")], OPORA_WORKER_NAME="dev-1")
    assert replies == [{"jsonrpc": "2.0", "id": 1, "result": {}},
                       {"jsonrpc": "2.0", "id": 2, "error": {"code": -32601,
                                                             "message": "Method not found: resources/list"}}]


def test_ask_with_wait_long_polls_inbox_for_its_ticket(gate):
    replies = run_mcp(url(gate), [call(1, "opora_ask", {"question": "Smím?", "wait": True})],
                      OPORA_WORKER_NAME="dev-1")
    assert text(replies[0]) == {"ticketId": "gt_ask", "seq": 3, "kind": "ask", "status": "queued",
                                "answer": {"text": "ano"}, "answered": True}
    requests = [entry[3] for entry in gate.calls if entry[1] == "/api/gate/requests"]
    assert requests[0] == {"kind": "ask", "body": {"question": "Smím?"}}  # wait se bráně neposílá
    assert [body["body"]["after"] for body in requests[1:]] == [0, 1]
    assert all(0 < body["body"]["wait"] <= 30 for body in requests[1:])
