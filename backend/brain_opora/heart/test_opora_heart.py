"""Nástroj srdce proti falešnému serveru: hlavičky, tvar úkolu, odpověď, zrušení, eskalace, paměť (`decide`, `rule`),
`done`, chyby a dílna (`ctx`, `run`)."""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.brain_opora.heart import opora_heart


class Handler(BaseHTTPRequestHandler):
    calls = []
    stale = 0  # kolikrát ještě `/api/canvas-plan` odmítne zastaralý digest

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
        if url.path == "/api/brain/heart/context":
            return self._reply(200, {"name": "tasks", "items": [{"taskId": "ht_1"}, {"taskId": "ht_2", "t": "č"}]})
        if url.path == "/api/view":
            return self._reply(200, {"digest": f"d{len(Handler.calls)}", "graph": {"nodes": []}})
        if url.path == "/api/canvas-plan":
            if Handler.stale:
                Handler.stale -= 1
                return self._reply(409, {"error": "Plátno se změnilo v jiném okně. Obnovte ho."})
            if not body["plan"].get("nodes"):
                return self._reply(409, {"error": "Dávka je prázdná."})
            return self._reply(200, {"ok": True, "dryRun": body.get("dryRun", False), "refs": {"hero": "n_1"},
                                     "summary": "1 karta", "warnings": [], "digest": "x", "revision": 3})
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
    Handler.calls, Handler.stale = [], 0
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


def test_plan_sends_the_file_with_a_fresh_digest_and_retries_stale_once(server, capsys, tmp_path):
    plan = {"nodes": [{"ref": "hero", "kind": "node", "name": "Hero", "card": {"status": "draft"}}]}
    (tmp_path / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    code, out = run(capsys, "plan", "--file", "plan.json", "--dry-run")
    assert code == 0 and json.loads(out) == {"ok": True, "dryRun": True, "refs": {"hero": "n_1"}, "summary": "1 karta",
                                             "warnings": []}
    view, post = Handler.calls
    assert view["path"] == "/api/view" and view["query"] == {"project": ["p1"], "workspace": ["main"]}
    assert post["body"] == {"project": "p1", "workspace": "main", "digest": "d1", "plan": plan, "dryRun": True}
    assert post["headers"]["X-Opora-Gate-Token"] == "tok-heart"
    Handler.calls, Handler.stale = [], 1
    code, out = run(capsys, "plan", "--file", "plan.json")
    posts = [call for call in Handler.calls if call["path"] == "/api/canvas-plan"]
    assert code == 0 and len(posts) == 2 and posts[0]["body"]["digest"] != posts[1]["body"]["digest"]
    assert "dryRun" not in posts[1]["body"]
    Handler.stale = 2
    code, out = run(capsys, "plan", "--file", "plan.json")
    assert code == 1 and json.loads(out)["code"] == "stale" and json.loads(out)["hint"]
    (tmp_path / "empty.json").write_text('{"nodes": []}', encoding="utf-8")
    code, out = run(capsys, "plan", "--file", "empty.json")
    assert code == 1 and json.loads(out)["code"] == "http_409" and json.loads(out)["error"] == "Dávka je prázdná."
    (tmp_path / "bad.json").write_text("[1]", encoding="utf-8")
    assert json.loads(run(capsys, "plan", "--file", "bad.json")[1])["code"] == "plan_file"
    assert json.loads(run(capsys, "plan", "--file", "chybi.json")[1])["code"] == "plan_file"


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


def test_ctx_writes_the_data_file_and_prints_only_its_size(server, capsys, tmp_path):
    code, out = run(capsys, "ctx", "tasks")
    raw = (tmp_path / "dilna" / "data" / "tasks.json").read_bytes()
    assert code == 0 and json.loads(out) == {"path": "dilna/data/tasks.json", "items": 2, "bytes": len(raw)}
    assert "ht_1" not in out and json.loads(raw)[1] == {"taskId": "ht_2", "t": "č"}
    call = Handler.calls[0]
    assert call["path"] == "/api/brain/heart/context" and call["headers"]["X-Opora-Gate-Token"] == "tok-heart"
    assert call["query"] == {"project": ["p1"], "workspace": ["main"], "name": ["tasks"]}
    with pytest.raises(SystemExit):
        opora_heart.main(["ctx", "secrets"])


SCRIPT = """\"\"\"Vypíše prostředí a argumenty.\"\"\"
import json, os, sys
import rlm
with open(os.environ["OPORA_RLM_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"ok": True, "costUsd": 0.002}) + "\\n" + json.dumps({"ok": True, "costUsd": 0.003}) + "\\n")
print(json.dumps({"args": sys.argv[1:], "token": os.environ.get("OPORA_HEART_TOKEN"),
                  "key": os.environ.get("ANTHROPIC_API_KEY"), "base": os.environ.get("OPORA_BASE_URL"),
                  "chunks": rlm.chunks([1, 2, 3], 2), "cwd": os.path.basename(os.getcwd())}))
"""


@pytest.fixture
def dilna(server, tmp_path, monkeypatch):
    (tmp_path / "dilna" / "scripts").mkdir(parents=True)
    (tmp_path / "dilna" / "rlm.py").write_bytes((opora_heart.Path(opora_heart.__file__).parent / "rlm.py").read_bytes())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-tajne")
    return tmp_path / "dilna"


def test_run_executes_the_script_without_token_and_logs_sub_cost(dilna, capsys):
    (dilna / "scripts" / "probe.py").write_text(SCRIPT, encoding="utf-8")
    code, out = run(capsys, "run", "probe", "a b", "--flag")
    result = json.loads(out)
    assert code == 0 and result["exit"] == 0, result.get("stderr")
    assert json.loads(result["stdout"]) == {"args": ["a b", "--flag"], "token": None, "key": None, "base": None,
                                            "chunks": [[1, 2], [3]], "cwd": "dilna"}
    assert (result["subCalls"], result["subCostUsd"]) == (2, 0.005)
    entry = json.loads((dilna / "runs.jsonl").read_text(encoding="utf-8"))
    assert set(entry) == {"at", "script", "args", "exit", "ms", "subCalls", "subCostUsd"}
    assert (entry["script"], entry["args"], entry["subCostUsd"]) == ("probe", ["a b", "--flag"], 0.005)
    assert not list(dilna.glob(".sub-*"))  # záznam sub-volání po běhu zmizí


def test_run_refuses_bad_names_and_missing_scripts(dilna, capsys):
    for name in ("../probe", "a/b", "a\\b", "x.py", ""):
        code, out = run(capsys, "run", name)
        assert code == 1 and json.loads(out)["code"] == "script_name", name
    code, out = run(capsys, "run", "nikde")
    assert code == 1 and json.loads(out)["code"] == "script_missing"


def test_run_cuts_stdout_reports_errors_and_times_out(dilna, capsys, monkeypatch):
    (dilna / "scripts" / "loud.py").write_text("import sys\nprint('x' * 9000)\nsys.exit('chyba')\n", encoding="utf-8")
    result = json.loads(run(capsys, "run", "loud")[1])
    assert result["exit"] == 1 and "chyba" in result["stderr"] and len(result["stdout"]) < 8100
    assert result["stdout"].startswith("x" * opora_heart.STDOUT_LIMIT) and "zkráceno" in result["stdout"]
    (dilna / "scripts" / "slow.py").write_text("import time\nprint('start', flush=True)\ntime.sleep(30)\n",
                                               encoding="utf-8")
    monkeypatch.setattr(opora_heart, "RUN_TIMEOUT", 1)
    result = json.loads(run(capsys, "run", "slow")[1])
    assert result["timedOut"] is True and result["exit"] is None
    assert json.loads((dilna / "runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])["script"] == "slow"


TREE = """import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
open("child.pid", "w").write(str(child.pid))
print("start", flush=True)
time.sleep(60)
"""


def alive(pid):
    if os.name == "nt":  # os.kill(pid, 0) by na Windows proces ukončil
        listed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in listed.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_timeout_kills_the_whole_tree_with_sub_processes(dilna, capsys, monkeypatch):
    (dilna / "scripts" / "tree.py").write_text(TREE, encoding="utf-8")
    monkeypatch.setattr(opora_heart, "RUN_TIMEOUT", 2)
    started = time.time()
    result = json.loads(run(capsys, "run", "tree")[1])
    assert result["timedOut"] is True and result["exit"] is None and "start" in result["stdout"]
    assert time.time() - started < 8  # potomek nedrží rouru výstupu
    child = int((dilna / "child.pid").read_text(encoding="utf-8"))
    deadline = time.time() + 3
    while alive(child) and time.time() < deadline:
        time.sleep(0.1)
    assert not alive(child)
