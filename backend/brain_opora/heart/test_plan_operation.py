import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.brain_opora.heart import opora_heart as cli


@pytest.mark.parametrize("accepted_graph", [False, True])
def test_lost_write_response_replays_original_request_without_duplicate(tmp_path, monkeypatch, accepted_graph):
    posts, receipts = [], {}
    committed = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, body):
            raw = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path.startswith("/api/desktop-v3/state"):
                return self.reply({"revision": 1})
            if "/context" in self.path:
                return self.reply({"graphManifestId": "m" if accepted_graph else None,
                                   "acceptedHead": "r2" if committed else "r1", "graphDigest": "d2" if committed else "d1"})
            if self.path.startswith("/api/view"):
                return self.reply({"digest": "d2" if committed else "d1", "graph": {"nodes": [{"id": "n1"}] if committed else []}})
            return self.reply({"id": "gp1", "project": "p", "workspace": "w", "parentRevision": "r1",
                               "refs": {"a": "n1"}, "additions": {"nodes": [{"id": "n1"}]}, "accepted": False})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            posts.append(body)
            key = body["operationId"]
            if key not in receipts:
                committed.append("n1")
                receipts[key] = ({"id": "gp1", "project": "p", "workspace": "w", "parentRevision": "r1",
                                  "refs": {"a": "n1"}, "additions": {"nodes": [{"id": "n1"}]}, "accepted": False}
                                 if accepted_graph else
                                 {"ok": True, "dryRun": False, "refs": {"a": "n1"}, "warnings": [], "digest": "d2", "revision": 1})
                # The server committed, but the caller never receives the receipt.
                self.close_connection = True
                return
            return self.reply(receipts[key])

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.chdir(tmp_path)
    for name, value in {"OPORA_PROJECT": "p", "OPORA_WORKSPACE": "w", "OPORA_HEART_TOKEN": "test-secret",
                        "OPORA_BASE_URL": f"http://127.0.0.1:{server.server_port}"}.items():
        monkeypatch.setenv(name, value)
    filename = tmp_path / "plan.json"
    filename.write_text(json.dumps({"nodes": [{"ref": "a", "kind": "node", "name": "A"}], "edges": []}))
    args = cli.parser().parse_args(["plan", "--file", str(filename)])
    try:
        with pytest.raises(cli.Failure) as error:
            cli.run(args)
        assert error.value.payload["code"] == "server_unreachable"
        result = cli.run(args)
        assert result["verified"] is True and result["accepted"] is False
        assert len(committed) == 1 and len(posts) == 2 and posts[0] == posts[1]
        assert posts[1].get("expectedGraphDigest", posts[1].get("digest")) == "d1"
        record = json.loads((tmp_path / result["operationFile"]).read_text(encoding="utf-8"))
        assert record["request"]["body"] == posts[0]
        assert record["outcome"]["readback"]["nodeIds"] == ["n1"]
        assert "test-secret" not in json.dumps(record)
    finally:
        server.shutdown()
        server.server_close()


def test_stale_operation_does_not_refresh_cas_or_allow_changed_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPORA_PROJECT", "p")
    monkeypatch.setenv("OPORA_WORKSPACE", "w")
    filename = tmp_path / "plan.json"
    filename.write_text('{"nodes":[{"ref":"a","kind":"node","name":"A"}],"edges":[]}')
    posts = []

    def call(method, path, body=None, query=None):
        if method == "GET":
            return {"graphManifestId": "m", "acceptedHead": "r", "graphDigest": "d"}
        posts.append(body)
        raise cli.Failure({"status": 409, "error": "Accepted revision changed"})

    monkeypatch.setattr(cli, "call", call)
    args = cli.parser().parse_args(["plan", "--file", str(filename), "--operation-id", "intent1"])
    with pytest.raises(cli.Failure):
        cli.run(args)
    assert len(posts) == 1
    filename.write_text('{"nodes":[{"ref":"a","kind":"node","name":"Changed"}],"edges":[]}')
    with pytest.raises(cli.Failure) as error:
        cli.run(args)
    assert error.value.payload["code"] == "operation_conflict" and len(posts) == 1
