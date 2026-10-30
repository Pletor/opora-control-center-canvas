"""Nástroj srdce proti falešnému serveru: hlavičky, tvar úkolu, odpověď, zrušení, eskalace, paměť (`decide`, `rule`),
`done`, chyby, dílna (`ctx`, `run`) a dávka plánu s přijetím (`plan`)."""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.brain_opora.heart import opora_heart


class Handler(BaseHTTPRequestHandler):
    calls: ClassVar = []
    stale = 0  # kolikrát ještě `/api/canvas-plan` odmítne zastaralý digest
    rejected = None  # (status, tělo), kterým `/api/canvas-plan` dávku odmítne
    states: ClassVar = []  # odpovědi `GET /api/oporahub/agent-state` po řadě (poslední se opakuje)
    refuse = ""  # cesta, kterou server odmítne 403 (přijetí bez oprávnění)
    manifest = None  # graphManifestId kontextu návrhů grafu (None = graf ještě není přijatý)

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
        if url.path == "/api/oporahub/agent-state":
            index = sum(call["path"] == url.path for call in Handler.calls) - 1
            return self._reply(200, Handler.states[min(index, len(Handler.states) - 1)] if Handler.states else {})
        if url.path == Handler.refuse:
            return self._reply(403, {"error": "Graph additions require human acceptance in the UI.",
                                     "humanRequired": True})
        if url.path == "/api/oporahub/graph-proposals/context":
            return self._reply(200, {"acceptedHead": "r1" if Handler.manifest else None, "graphDigest": "gd",
                                     "graphManifestId": Handler.manifest})
        if url.path == "/api/oporahub/graph-proposals" and method == "POST":
            return self._reply(200, {"id": "gp2", "refs": {ref["ref"]: "n_" + ref["ref"] for ref in body["plan"]["nodes"]},
                                     "accepted": False})
        if url.path.startswith("/api/oporahub/"):
            return self._reply(200, {"id": "g1"})
        if url.path == "/api/canvas-plan":
            if Handler.rejected:
                return self._reply(*Handler.rejected)
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
    Handler.calls, Handler.stale, Handler.rejected, Handler.states, Handler.refuse = [], 0, None, [], ""
    Handler.manifest = None
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
    context, view, post = Handler.calls
    assert context["path"] == "/api/oporahub/graph-proposals/context"
    assert view["path"] == "/api/view" and view["query"] == {"project": ["p1"], "workspace": ["main"]}
    assert post["body"] == {"project": "p1", "workspace": "main", "digest": "d2", "plan": plan, "dryRun": True}
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
    assert run(capsys, "intake", "--entry", "ie_1", "--verdict", "later_extension", "--reason", "po milníku")[0] == 0
    assert (Handler.calls[-1]["path"], Handler.calls[-1]["body"]) == ("/api/brain/heart/intake", {
        "project": "p1", "workspace": "main", "entry": "ie_1", "verdict": "later_extension", "reason": "po milníku"})
    with pytest.raises(SystemExit):
        opora_heart.main(["intake", "--entry", "ie_1", "--verdict", "duplicate"])  # duplicitu dává determinismus
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
    assert raw.decode("utf-8").splitlines()[1] == '{"taskId": "ht_1"},'  # položka na řádek: Grep a Read po řádcích
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
        listed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                                check=False)
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


PROPOSE = {"verb": "propose_graph", "method": "POST", "path": "/api/oporahub/graph-proposals", "status": "ready",
           "preconditions": {"parentRevision": None, "expectedGraphDigest": "g", "subject": "Graf",
                             "plan": {"nodes": [], "edges": []}}}
ACCEPT = {"verb": "accept", "method": "POST", "path": "/api/oporahub/graph-proposals/gp1/accept", "status": "blocked",
          "blockReason": "human_only", "preconditions": {"expectedAcceptedHead": None, "expectedGraphDigest": "g",
                                                         "adoptBaseGraphDigest": "g"}}
FOREIGN = {"verb": "accept", "method": "POST", "path": "/api/oporahub/content-changes/c1/accept", "status": "blocked",
           "blockReason": "human_only", "preconditions": {}}
CLAIM = {"verb": "claim", "method": "POST", "path": "/api/oporahub/executions/claim", "status": "ready"}


def plan_file(tmp_path):
    (tmp_path / "plan.json").write_text(json.dumps(opora_heart.PLAN_EXAMPLE, ensure_ascii=False), encoding="utf-8")
    return "plan.json"


def test_plan_accepts_the_graph_with_the_heart_token_and_leaves_foreign_proposals(server, capsys, tmp_path):
    Handler.states = [{"actions": [PROPOSE, FOREIGN]}, {"actions": [ACCEPT, FOREIGN]},
                      {"actions": [CLAIM, FOREIGN], "heads": {"workingDiffers": False}}]
    code, out = run(capsys, "plan", "--file", plan_file(tmp_path))
    result = json.loads(out)
    assert code == 0 and result["accepted"] is True and result["acceptSteps"] == ["propose_graph", "accept"]
    posts = [call for call in Handler.calls if call["method"] == "POST"]
    assert [call["path"] for call in posts] == ["/api/canvas-plan", PROPOSE["path"], ACCEPT["path"]]
    assert posts[1]["body"] == {"project": "p1", "workspace": "main", **PROPOSE["preconditions"]}
    assert posts[2]["body"] == {"project": "p1", "workspace": "main", **ACCEPT["preconditions"]}
    assert all(call["headers"]["X-Opora-Gate-Token"] == "tok-heart" for call in posts)


def test_plan_reports_an_unaccepted_plan_with_a_code_and_hint(server, capsys, tmp_path):
    name = plan_file(tmp_path)
    Handler.states, Handler.refuse = [{"actions": [ACCEPT]}], ACCEPT["path"]
    result = json.loads(run(capsys, "plan", "--file", name)[1])
    assert (result["accepted"], result["code"], result["acceptSteps"]) == (False, "http_403", [])
    assert "human acceptance" in result["error"] and result["hint"]
    Handler.calls, Handler.refuse = [], ""
    Handler.states = [{"actions": [CLAIM], "heads": {"workingDiffers": True}}]
    result = json.loads(run(capsys, "plan", "--file", name)[1])
    assert (result["accepted"], result["code"]) == (False, "plan_not_accepted") and result["hint"]
    Handler.calls = []
    code, out = run(capsys, "plan", "--file", name, "--no-accept")
    assert code == 0 and json.loads(out)["accepted"] is False
    assert [call["path"] for call in Handler.calls] == ["/api/oporahub/graph-proposals/context", "/api/view",
                                                        "/api/canvas-plan"]
    Handler.calls = []
    assert "accepted" not in json.loads(run(capsys, "plan", "--file", name, "--dry-run")[1])
    assert [call["path"] for call in Handler.calls] == ["/api/oporahub/graph-proposals/context", "/api/view",
                                                        "/api/canvas-plan"]


def test_rejected_plan_hint_carries_the_server_text_and_field(server, capsys, tmp_path):
    name = plan_file(tmp_path)
    Handler.rejected = (409, {"error": "nodes[0]: neznámé pole files, id, title, why"})
    code, out = run(capsys, "plan", "--file", name, "--dry-run")
    result = json.loads(out)
    assert code == 1 and result["code"] == "http_409"
    assert "nodes[0]: neznámé pole files, id, title, why" in result["hint"] and "plan --example" in result["hint"]
    Handler.rejected = (422, {"error": "Krok plánu: …", "code": "invalid_payload", "field": "spec.steps",
                              "expected": "pole kroků", "example": [{"id": "s1"}]})
    result = json.loads(run(capsys, "plan", "--file", name)[1])
    assert result["field"] == "spec.steps" and result["example"] == [{"id": "s1"}]
    assert "Krok plánu: …" in result["hint"] and "Pole spec.steps: pole kroků." in result["hint"]
    Handler.rejected = (409, {"error": "Cyklus.", "code": "card_cycle", "hint": "Vlastní rada serveru."})
    assert json.loads(run(capsys, "plan", "--file", name)[1])["hint"] == "Vlastní rada serveru."


def test_plan_example_prints_the_batch_and_plan_needs_a_file(server, capsys):
    code, out = run(capsys, "plan", "--example")
    assert code == 0 and json.loads(out) == opora_heart.PLAN_EXAMPLE and Handler.calls == []
    code, out = run(capsys, "plan")
    assert code == 1 and json.loads(out)["code"] == "plan_file" and "--example" in json.loads(out)["hint"]


def test_plan_over_an_accepted_graph_goes_as_a_graph_proposal_and_accepts_it(server, capsys, tmp_path):
    Handler.manifest = "m1"
    code, out = run(capsys, "plan", "--file", plan_file(tmp_path))
    result = json.loads(out)
    assert code == 0 and result["accepted"] is True and result["acceptSteps"] == ["graph_addition", "accept"]
    assert result["refs"] == {"mvp": "n_mvp", "model": "n_model", "cli": "n_cli"} and result["proposalId"] == "gp2"
    assert result["warnings"] == []
    posts = [call for call in Handler.calls if call["method"] == "POST"]
    assert [call["path"] for call in posts] == ["/api/oporahub/graph-proposals",
                                                "/api/oporahub/graph-proposals/gp2/accept"]
    proposal = posts[0]["body"]
    assert (proposal["parentRevision"], proposal["expectedGraphDigest"]) == ("r1", "gd")
    assert proposal["plan"]["nodes"] == opora_heart.PLAN_EXAMPLE["nodes"]  # card (i effort) a checks beze ztráty
    assert proposal["plan"]["nodes"][1]["spec"] == opora_heart.PLAN_EXAMPLE["nodes"][1]["spec"]
    assert posts[1]["body"] == {"project": "p1", "workspace": "main", "expectedAcceptedHead": "r1",
                                "expectedGraphDigest": "gd", "adoptBaseGraphDigest": None}
    Handler.calls = []
    result = json.loads(run(capsys, "plan", "--file", "plan.json", "--no-accept")[1])
    assert result["accepted"] is False and [call["path"] for call in Handler.calls if call["method"] == "POST"] == [
        "/api/oporahub/graph-proposals"]
    Handler.calls = []
    result = json.loads(run(capsys, "plan", "--file", "plan.json", "--dry-run")[1])
    dry = [call for call in Handler.calls if call["method"] == "POST"]
    assert result["dryRun"] is True and [call["path"] for call in dry] == ["/api/canvas-plan"]
    assert dry[0]["body"]["dryRun"] is True and dry[0]["body"]["plan"]["nodes"][1]["card"]["effort"] == "medium"


def test_addition_refuses_fields_a_graph_proposal_cannot_carry(server, capsys, tmp_path):
    Handler.manifest = "m1"
    bad = {"nodes": [{"ref": "a", "kind": "node", "name": "A", "blocks": [{"ref": "b", "title": "B"}]}]}
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "bad.json")[1])
    assert result["code"] == "plan_shape" and "blocks" in result["error"] and "návrh grafu" in result["hint"]
    edge = {"nodes": [], "edges": [{"from": "a", "to": "b", "port": "block"}]}
    (tmp_path / "edge.json").write_text(json.dumps(edge), encoding="utf-8")
    assert json.loads(run(capsys, "plan", "--file", "edge.json")[1])["code"] == "plan_shape"
    assert not [call for call in Handler.calls if call["method"] == "POST"]


def test_architecture_in_a_workspace_points_the_heart_to_main(server, capsys, tmp_path):
    Handler.manifest = "m1"
    page = {"nodes": [{"ref": "p", "kind": "node", "name": "Zdroje", "site": {"kind": "page", "path": "/sources"}}]}
    (tmp_path / "arch.json").write_text(json.dumps(page), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "arch.json")[1])
    assert result["code"] == "plan_architecture" and "--workspace main" in result["hint"]
    assert not [call for call in Handler.calls if call["method"] == "POST"]


def test_workspace_override_is_per_call_and_ctx_plan_of_reads_another_project(server, capsys, tmp_path):
    code, _ = run(capsys, "task", "--title", "T", "--do", "D", "--workspace", "w1")
    assert code == 0 and Handler.calls[-1]["body"]["workspace"] == "w1"
    run(capsys, "snapshot")  # další volání bez --workspace jde zase do prostoru z prostředí
    assert Handler.calls[-1]["query"]["workspace"] == ["main"]
    code, out = run(capsys, "ctx", "plan-of", "--project", "p2", "--workspace", "w9")
    assert code == 0 and json.loads(out)["path"] == "dilna/data/plan-of-p2.json"
    assert Handler.calls[-1]["query"] == {"project": ["p1"], "workspace": ["main"], "name": ["plan-of"],
                                          "of": ["p2"], "ofWorkspace": ["w9"]}
    code, out = run(capsys, "ctx", "plan-of", "--project", "p2", "--node", "n7")
    assert code == 0 and json.loads(out)["path"] == "dilna/data/plan-of-p2-n7.json"
    assert Handler.calls[-1]["query"]["ofNode"] == ["n7"]
    code, out = run(capsys, "ctx", "plan-of")
    assert code == 1 and json.loads(out)["code"] == "plan_of_project"


def test_ctx_plan_of_reports_which_nodes_were_cut(server, capsys, tmp_path, monkeypatch):
    marker = {"truncated": True, "total": 3, "shown": 1, "cut": [{"id": "b", "name": "B"}, {"id": "c", "name": "C"}],
              "hint": "…"}
    monkeypatch.setattr(opora_heart, "call", lambda *args, **kwargs: {"items": [{"id": "a"}, marker]})
    code, out = run(capsys, "ctx", "plan-of", "--project", "p2")
    assert code == 0 and json.loads(out) == {"path": "dilna/data/plan-of-p2.json", "items": 1, "truncated": True,
                                             "total": 3, "cut": ["b", "c"], "bytes": json.loads(out)["bytes"]}


def test_accepted_plan_remembers_its_workspace(server, capsys, tmp_path):
    Handler.states = [{"actions": [], "heads": {"workingDiffers": False}}]
    (tmp_path / "plan.json").write_text(json.dumps({"nodes": [{"ref": "hero"}]}), encoding="utf-8")
    code, out = run(capsys, "plan", "--file", "plan.json", "--workspace", "w1")
    assert code == 0 and json.loads(out)["accepted"] is True
    assert json.loads((tmp_path / opora_heart.ACTIVE).read_text(encoding="utf-8"))["workspace"] == "w1"


def test_research_in_main_goes_to_the_active_workspace_or_the_explicit_one(server, capsys, tmp_path, monkeypatch):
    seen = []
    module = type("M", (), {"research": staticmethod(lambda args, tool: seen.append(tool.scope()["workspace"]) or {})})
    monkeypatch.setattr(opora_heart, "research_module", lambda name="x": module)
    args = ["research", "--question", "Q", "--title", "T"]
    run(capsys, *args)
    (tmp_path / opora_heart.ACTIVE).write_text(json.dumps({"workspace": "w7"}), encoding="utf-8")
    run(capsys, *args)
    run(capsys, *args, "--workspace", "w2")
    run(capsys, "snapshot")
    assert seen == ["main", "w7", "w2"] and Handler.calls[-1]["query"]["workspace"] == ["main"]
