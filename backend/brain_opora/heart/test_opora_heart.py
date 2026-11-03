"""Nástroj srdce proti falešnému serveru: hlavičky, tvar úkolu, odpověď, zrušení, eskalace, paměť (`decide`, `rule`),
`done`, chyby, dílna (`ctx`, `run`), dávka plánu s přijetím (`plan`) a návrh členství v oblasti (`member`)
a pořadí podle záměru (`order`)."""
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
    refuse = ""  # cesta, na kterou server odmítne POST 403 (přijetí bez oprávnění)
    manifest = None  # graphManifestId kontextu návrhů grafu (None = graf ještě není přijatý)
    graph: ClassVar = {"nodes": []}  # pracovní graf z `GET /api/view`
    architecture: ClassVar = {"graph": {"nodes": [], "edges": []}, "revision": 0, "digest": "a0"}  # architektura projektu
    differs = False  # architectureContext.differs kontextu návrhů (prostor má starší architekturu, než je uložená)

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
            return self._reply(200, {"name": "work", "items": [{"ticketId": "tk_1"}, {"ticketId": "tk_2", "t": "č"}]})
        if url.path == "/api/view":
            return self._reply(200, {"digest": f"d{len(Handler.calls)}", "graph": Handler.graph})
        if url.path == "/api/oporahub/agent-state":
            index = sum(call["path"] == url.path for call in Handler.calls) - 1
            return self._reply(200, Handler.states[min(index, len(Handler.states) - 1)] if Handler.states else {})
        if url.path == Handler.refuse and method == "POST":
            return self._reply(403, {"error": "Graph additions require human acceptance in the UI.",
                                     "humanRequired": True})
        if url.path == "/api/oporahub/graph-proposals/context":
            return self._reply(200, {"acceptedHead": "r1" if Handler.manifest else None, "graphDigest": "gd",
                                     "graphManifestId": Handler.manifest,
                                     "architectureContext": {"differs": Handler.differs and any(
                                         call["path"] == "/api/project-architecture" and call["method"] == "POST"
                                         for call in Handler.calls)}})
        if url.path == "/api/project-architecture":
            if method == "GET":
                return self._reply(200, Handler.architecture)
            return self._reply(200, {"graph": body["graph"], "revision": body["expectedRevision"] + 1, "digest": "a1"})
        if url.path == "/api/oporahub/graph-proposals" and method == "POST":
            return self._reply(200, {"id": "gp2", "refs": {ref["ref"]: "n_" + ref["ref"] for ref in body["plan"].get("nodes", [])},
                                     "accepted": False})
        if url.path.startswith("/api/oporahub/"):
            return self._reply(200, {"id": "g1"})
        if url.path == "/api/canvas-plan":
            if Handler.rejected:
                return self._reply(*Handler.rejected)
            if Handler.stale:
                Handler.stale -= 1
                return self._reply(409, {"error": "Plátno se změnilo v jiném okně. Obnovte ho."})
            if body["plan"].get("extend"):
                return self._reply(200, {"ok": True, "dryRun": False, "refs": {}, "warnings": [], "revision": 6,
                                         "blocks": {f"{item['node']}/{block['ref']}": f"blk_{block['ref']}"
                                                    for item in body["plan"]["extend"] for block in item.get("blocks", [])}})
            if not body["plan"].get("nodes"):
                return self._reply(409, {"error": "Dávka je prázdná."})
            return self._reply(200, {"ok": True, "dryRun": body.get("dryRun", False), "refs": {"hero": "n_1"},
                                     "summary": "1 karta", "warnings": [], "digest": "x", "revision": 3})
        if url.path == "/api/brain/heart/snapshot":
            return self._reply(200, {"snapshot": "PROJEKT p1\nPLÁN:"})
        if url.path == "/api/gate/requests":
            ticket = ({"ticketId": "tk_1", "status": "cancelled"} if body["kind"] == "ticket.cancel" else
                      {"ticketId": "tk_1", "status": "issued", "machine": {"cardId": body["body"].get("cardId")}}
                      if body["kind"] == "ticket.issue" else {"ticketId": "tk_1", "status": "issued"})
            return self._reply(201, {"ticketId": "gt_3", "kind": body["kind"], "status": "answered",
                                     "answer": {"ticket": ticket}})
        if url.path.endswith("/answer"):
            return self._reply(200, {"ticketId": "gt_1", "status": "answered", "answeredBy": "heart"})
        if url.path == "/api/desktop-v3/state" and method == "GET":
            return self._reply(200, {"revision": 5, "state": {}, "readOnly": False})
        if url.path.startswith("/api/desktop-v3/"):
            return self._reply(200, {"revision": 2, "item": {**body["item"], "by": "agent"}})
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
    Handler.manifest, Handler.graph = None, {"nodes": []}
    Handler.architecture, Handler.differs = {"graph": {"nodes": [], "edges": []}, "revision": 0, "digest": "a0"}, False
    yield base
    httpd.shutdown()


def run(capsys, *argv):
    code = opora_heart.main(list(argv))
    return code, capsys.readouterr().out.strip()


def test_task_issues_only_a_work_ticket_with_a_full_body_and_the_card(server, capsys):
    code, out = run(capsys, "task", "--title", "Hero", "--do", "Udělej hero.", "--why", "Proč", "--file", "a.tsx",
                    "--done-when", "npm test projde", "--dont-touch", "nav.tsx@úkol navigace", "--rule", "Česky",
                    "--intent", "klid", "--open-path", "Pod hero místo pro CTA", "--node", "home",
                    "--department", "design", "--profile", "frontend")
    assert code == 0 and json.loads(out) == {"ticketId": "tk_1", "status": "issued", "title": "Hero", "cardId": "home"}
    [call] = Handler.calls  # žádná fronta úkolů, jen ticket
    assert call["path"] == "/api/gate/requests" and call["headers"]["X-Opora-Gate-Token"] == "tok-heart"
    assert call["headers"]["Origin"] == server and call["headers"]["X-Opora-Actor"] == "agent; name=heart"
    assert call["body"] == {"kind": "ticket.issue", "body": {"cardId": "home", "department": "design",
                                                             "profile": "frontend", "body": {
        "essence": "Proč\nPocit: klid", "build": "Hero\nUdělej hero.\nSoubory: a.tsx",
        "openPaths": ["Pod hero místo pro CTA"], "cautions": ["Nesahej na nav.tsx (drží úkol navigace)", "Česky"],
        "doneCriteria": ["npm test projde"]}}}


def test_task_body_carries_no_gate_ids_and_goes_to_the_named_workspace(server, capsys):
    code, out = run(capsys, "task", "--title", "Hero", "--do", "Navaž na ht_0123456789ab.", "--done-when", "build",
                    "--workspace", "w1")
    assert code == 0 and json.loads(out)["cardId"] is None
    sent = Handler.calls[0]["body"]["body"]
    assert sent == {"workspace": "w1", "body": {"essence": "Hero", "build": "Hero\nNavaž na (ID).", "openPaths": [],
                                                "cautions": [], "doneCriteria": ["build"]}}
    code, out = run(capsys, "task", "--title", "Hero", "--do", "Bez kritéria.")
    assert code == 1 and json.loads(out)["code"] == "ticket_done_criteria" and len(Handler.calls) == 1


def test_cancel_cancels_the_work_ticket(server, capsys):
    code, out = run(capsys, "cancel", "--task", "tk_1")
    assert code == 0 and json.loads(out) == {"ticketId": "tk_1", "status": "cancelled"}
    assert Handler.calls[0]["body"] == {"kind": "ticket.cancel", "body": {"ticketId": "tk_1"}}


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
    assert run(capsys, "escalate", "--withdraw", "gt_9", "--reason", "Oprava je sloučená.")[0] == 0
    assert (Handler.calls[-1]["path"], Handler.calls[-1]["body"]) == ("/api/brain/heart/escalations/gt_9/withdraw", {
        "project": "p1", "workspace": "main", "reason": "Oprava je sloučená."})
    for argv in (["escalate", "--withdraw", "gt_9"], ["escalate", "--text", "x", "--withdraw", "gt_9"]):
        with pytest.raises(SystemExit):
            opora_heart.main(argv)
    assert run(capsys, "intake", "--entry", "ie_1", "--verdict", "later_extension", "--reason", "po milníku")[0] == 0
    assert (Handler.calls[-1]["path"], Handler.calls[-1]["body"]) == ("/api/brain/heart/intake", {
        "project": "p1", "workspace": "main", "entry": "ie_1", "verdict": "later_extension", "reason": "po milníku"})
    with pytest.raises(SystemExit):
        opora_heart.main(["intake", "--entry", "ie_1", "--verdict", "duplicate"])  # duplicitu dává determinismus
    assert run(capsys, "intake", "--entry", "ie_2", "--verdict", "later_extension", "--requirement", "new",
               "--title", "Hybridní hledání", "--open-condition", "ms_1")[0] == 0
    assert Handler.calls[-1]["body"] == {"project": "p1", "workspace": "main", "entry": "ie_2",
                                         "verdict": "later_extension", "requirement": "new",
                                         "title": "Hybridní hledání", "openCondition": "ms_1"}
    assert run(capsys, "milestone", "--area", "a1", "--title", "Spolehlivé hledání",
               "--criterion", "Jen dokumenty organizace::n1, n2", "--criterion", "Rychlé::n3")[0] == 0
    assert (Handler.calls[-1]["path"], Handler.calls[-1]["body"]) == ("/api/brain/heart/milestone", {
        "project": "p1", "workspace": "main", "area": "a1", "title": "Spolehlivé hledání",
        "criteria": [{"text": "Jen dokumenty organizace", "cards": ["n1", "n2"]}, {"text": "Rychlé", "cards": ["n3"]}]})
    assert run(capsys, "milestone-decide", "--activate", "ms_1")[0] == 0
    assert (Handler.calls[-1]["path"], Handler.calls[-1]["body"]) == ("/api/intake/milestone", {
        "project": "p1", "workspace": "main", "milestoneId": "ms_1", "action": "activate"})
    assert run(capsys, "milestone-decide", "--reject", "ms_2")[0] == 0
    assert Handler.calls[-1]["body"]["action"] == "reject" and Handler.calls[-1]["body"]["milestoneId"] == "ms_2"
    Handler.refuse = "/api/intake/milestone"
    code, out = run(capsys, "milestone-decide", "--activate", "ms_1")
    assert code == 1 and json.loads(out)["status"] == 403 and json.loads(out)["hint"] == "Rozhodne člověk ve Velínu."
    Handler.refuse = ""
    with pytest.raises(SystemExit):
        opora_heart.main(["milestone-decide"])
    (tmp_path / "brief.json").write_text(json.dumps({"goal": "Metriky"}, ensure_ascii=False), encoding="utf-8")
    assert run(capsys, "brief", "--requirement", "rq_1", "--synthesis", "@brief.json")[0] == 0
    assert (Handler.calls[-1]["path"], Handler.calls[-1]["body"]) == ("/api/brain/heart/brief", {
        "project": "p1", "workspace": "main", "requirement": "rq_1", "synthesis": {"goal": "Metriky"}})
    assert run(capsys, "brief", "--requirement", "rq_1", "--synthesis", '{"users": "člověk"}')[0] == 0
    assert Handler.calls[-1]["body"]["synthesis"] == {"users": "člověk"}
    code, out = run(capsys, "brief", "--requirement", "rq_1", "--synthesis", "@chybi.json")
    assert code == 1 and json.loads(out)["code"] == "brief_file"
    assert run(capsys, "ask", "--requirement", "rq_1", "--question", "Kdo?", "--recommended", "Člověk.",
               "--why", "Určí rozsah.")[0] == 0
    assert (Handler.calls[-1]["path"], Handler.calls[-1]["body"]) == ("/api/brain/heart/ask", {
        "project": "p1", "workspace": "main", "requirement": "rq_1", "question": "Kdo?", "recommended": "Člověk.",
        "why": "Určí rozsah."})
    assert run(capsys, "done", "--summary", "Dva úkoly.") == (0, '{"done": true}')
    assert json.loads((tmp_path / "last_done.json").read_text(encoding="utf-8"))["summary"] == "Dva úkoly."


def test_errors_print_code_and_hint(server, capsys, monkeypatch):
    code, out = run(capsys, "proposal", "--accept", "gp1")
    assert code == 1 and json.loads(out)["code"] == "human_only" and json.loads(out)["hint"]
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
    code, out = run(capsys, "ctx", "work")
    raw = (tmp_path / "dilna" / "data" / "work.json").read_bytes()
    assert code == 0 and json.loads(out) == {"path": "dilna/data/work.json", "items": 2, "bytes": len(raw)}
    assert "tk_1" not in out and json.loads(raw)[1] == {"ticketId": "tk_2", "t": "č"}
    assert raw.decode("utf-8").splitlines()[1] == '{"ticketId": "tk_1"},'  # položka na řádek: Grep a Read po řádcích
    call = Handler.calls[0]
    assert call["path"] == "/api/brain/heart/context" and call["headers"]["X-Opora-Gate-Token"] == "tok-heart"
    assert call["query"] == {"project": ["p1"], "workspace": ["main"], "name": ["work"]}
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


BLOCKED = {"nodes": [{"ref": "a", "kind": "node", "name": "A", "blocks": [
    {"ref": "pick", "title": "Varianta", "ports": [{"ref": "yes", "label": "Ano → B"}]}]},
    {"ref": "b", "kind": "node", "name": "B"}],
    "edges": [{"from": "a", "to": "b", "port": "next"},
              {"from": "a", "to": "b", "port": "block", "block": "pick", "blockPort": "yes"},
              {"from": "@old", "to": "b", "port": "block", "block": "blk_old", "blockPort": "ok"}]}


def test_later_plan_places_blocks_on_accepted_cards_and_wires_their_ports(server, capsys, tmp_path):
    Handler.manifest = "m1"
    (tmp_path / "blocks.json").write_text(json.dumps(BLOCKED, ensure_ascii=False), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "blocks.json")[1])
    assert result["accepted"] is True and result["blocks"] == {"@n_a/pick": "blk_pick"}
    assert result["acceptSteps"] == ["graph_addition", "accept", "card_state", "graph_addition", "accept"]
    check, *posts = [call for call in Handler.calls if call["method"] == "POST"]
    # Celá dávka se nejdřív ověří bez zápisu, ať chybný port nenechá přijaté karty bez stavu.
    assert check["path"] == "/api/canvas-plan" and check["body"]["dryRun"] is True and check["body"]["plan"] == BLOCKED
    assert [call["path"] for call in posts] == ["/api/oporahub/graph-proposals", "/api/oporahub/graph-proposals/gp2/accept",
                                                "/api/canvas-plan", "/api/oporahub/graph-proposals",
                                                "/api/oporahub/graph-proposals/gp2/accept"]
    cards = posts[0]["body"]["plan"]
    assert cards["nodes"] == [{"ref": "a", "kind": "node", "name": "A"}, {"ref": "b", "kind": "node", "name": "B"}]
    assert cards["edges"] == [{"from": "a", "to": "b", "port": "next"}]
    assert posts[2]["body"]["plan"] == {"extend": [{"node": "@n_a", "expectedRevision": 5,
                                                    "blocks": BLOCKED["nodes"][0]["blocks"]}]}
    assert posts[3]["body"]["plan"] == {"nodes": [], "edges": [
        {"from": "@n_a", "to": "@n_b", "port": "block", "block": "blk_pick", "blockPort": "yes"},
        {"from": "@old", "to": "@n_b", "port": "block", "block": "blk_old", "blockPort": "ok"}]}
    Handler.calls = []
    dry = json.loads(run(capsys, "plan", "--file", "blocks.json", "--dry-run")[1])
    sent = [call for call in Handler.calls if call["method"] == "POST"]
    assert dry["dryRun"] is True and [call["path"] for call in sent] == ["/api/canvas-plan"]
    assert sent[0]["body"]["plan"] == BLOCKED  # celá dávka s bloky i vazbami block projde validací bez zápisu


def vault_batch():
    """Dávka generátoru Schránky (oblast se značkou, sektor disciplíny, karta s textem, fragmentRef a bloky) a k ní
    blok s portem na existující kartě `@old` a vazba block z jeho portu na novou kartu."""
    from backend.editor.brief_vault.test_brief_vault_plan import chunks
    batch = chunks().plan(["r"])["plan"]
    batch["extend"] = [{"node": "@old", "blocks": [{"ref": "pick", "title": "Varianta",
                                                     "ports": [{"ref": "yes", "label": "Ano → chunks"}]}]}]
    batch["edges"].append({"from": "@old", "to": "f1", "port": "block", "block": "pick", "blockPort": "yes"})
    return batch


def test_vault_batch_over_an_accepted_graph_keeps_card_state_and_extends_an_existing_card(server, capsys, tmp_path):
    Handler.manifest = "m1"
    batch = vault_batch()
    (tmp_path / "vault.json").write_text(json.dumps(batch, ensure_ascii=False), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "vault.json")[1])
    assert result["accepted"] is True, result
    assert result["acceptSteps"] == ["graph_addition", "accept", "card_state", "graph_addition", "accept"]
    check, proposal, _, state, wired, _ = [call for call in Handler.calls if call["method"] == "POST"]
    assert check["body"]["plan"]["extend"] == [{"expectedRevision": 5, **batch["extend"][0]}]
    # Návrh grafu nese jen graf: stav karty (text, fragmentRef, bloky, značky) z něj vypadne.
    by_ref = {node["ref"]: node for node in batch["nodes"]}
    assert all(not set(node) & set(opora_heart.CARD_STATE) for node in proposal["body"]["plan"]["nodes"])
    assert [edge["port"] for edge in proposal["body"]["plan"]["edges"]] == ["next"]
    extend = {item["node"]: item for item in state["body"]["plan"]["extend"]}
    card = extend["@n_f1"]
    assert card["fragmentRef"] == by_ref["f1"]["fragmentRef"] and card["blocks"] == by_ref["f1"]["blocks"]
    assert card["text"] == {"expectedRevision": 0, "text": by_ref["f1"]["text"]} and card["expectedRevision"] == 5
    assert extend["@n_a1"] == {"node": "@n_a1", "expectedRevision": 5, "briefGroup": "logika"}
    assert extend["@n_s1"] == {"node": "@n_s1", "expectedRevision": 5, "briefDiscipline": "be"}
    assert extend["@old"] == {"expectedRevision": 5, **batch["extend"][0]}
    assert wired["body"]["plan"]["edges"] == [
        {"from": "@old", "to": "@n_f1", "port": "block", "block": "blk_pick", "blockPort": "yes"}]


def test_existing_cards_only_need_no_card_proposal(server, capsys, tmp_path):
    Handler.manifest = "m1"
    only = {"nodes": [], "extend": [{"node": "@old", "blocks": [{"ref": "pick", "title": "Varianta",
                                                                 "ports": [{"ref": "yes"}]}]}],
            "edges": [{"from": "@old", "to": "@other", "port": "block", "block": "pick", "blockPort": "yes"}]}
    (tmp_path / "only.json").write_text(json.dumps(only), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "only.json")[1])
    assert result["acceptSteps"] == ["card_state", "graph_addition", "accept"], result
    posts = [call["path"] for call in Handler.calls if call["method"] == "POST"]
    assert posts == ["/api/canvas-plan", "/api/canvas-plan", "/api/oporahub/graph-proposals",
                     "/api/oporahub/graph-proposals/gp2/accept"]


def test_addition_refuses_fields_a_graph_proposal_cannot_carry(server, capsys, tmp_path):
    Handler.manifest = "m1"
    bad = {"nodes": [{"ref": "a", "kind": "node", "name": "A", "rules": [{"kind": "must", "text": "R"}]}]}
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "bad.json")[1])
    assert result["code"] == "plan_shape" and "rules" in result["error"] and "návrh grafu" in result["hint"]
    edge = {"nodes": [], "edges": [{"from": "a", "to": "b", "port": "rule"}]}
    (tmp_path / "edge.json").write_text(json.dumps(edge), encoding="utf-8")
    assert json.loads(run(capsys, "plan", "--file", "edge.json")[1])["code"] == "plan_shape"
    (tmp_path / "blocks.json").write_text(json.dumps(BLOCKED), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "blocks.json", "--no-accept")[1])
    assert result["code"] == "plan_shape" and "přijaté karty" in result["error"]
    spec = {"nodes": [], "extend": [{"node": "@old", "spec": {"expectedRevision": 1, "fields": {}}, "layer": "backend"}]}
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "spec.json")[1])
    assert result["code"] == "plan_shape" and "layer, spec" in result["error"] and "steps --node" in result["hint"]
    assert not [call for call in Handler.calls if call["method"] == "POST"]


def test_architecture_in_a_workspace_points_the_heart_to_main(server, capsys, tmp_path):
    Handler.manifest = "m1"
    page = {"nodes": [{"ref": "p", "kind": "node", "name": "Zdroje", "site": {"kind": "page", "path": "/sources"}}]}
    (tmp_path / "arch.json").write_text(json.dumps(page), encoding="utf-8")
    result = json.loads(run(capsys, "plan", "--file", "arch.json")[1])
    assert result["code"] == "plan_architecture" and "--workspace main" in result["hint"]
    assert not [call for call in Handler.calls if call["method"] == "POST"]


def test_workspace_override_is_per_call_and_ctx_plan_of_reads_another_project(server, capsys, tmp_path):
    code, _ = run(capsys, "decide", "--text", "T", "--workspace", "w1")
    assert code == 0 and Handler.calls[-1]["body"]["workspace"] == "w1"
    run(capsys, "snapshot")  # další volání bez --workspace jde zase do prostoru z prostředí
    assert Handler.calls[-1]["query"]["workspace"] == ["main"]
    code, out = run(capsys, "ctx", "plan-of", "--project", "p2", "--workspace", "w9")
    assert code == 0 and json.loads(out)["path"] == "dilna/data/plan-of-p2.txt"  # výchozí: řádek na uzel
    assert Handler.calls[-1]["query"] == {"project": ["p1"], "workspace": ["main"], "name": ["plan-of"],
                                          "of": ["p2"], "ofWorkspace": ["w9"]}
    code, out = run(capsys, "ctx", "plan-of", "--project", "p2", "--full")
    assert code == 0 and json.loads(out)["path"] == "dilna/data/plan-of-p2.json"  # zhuštěný JSON pro skripty
    code, out = run(capsys, "ctx", "plan-of", "--project", "p2", "--node", "n7")
    assert code == 0 and json.loads(out)["path"] == "dilna/data/plan-of-p2-n7.json"
    assert Handler.calls[-1]["query"]["ofNode"] == ["n7"]
    code, out = run(capsys, "ctx", "plan-of")
    assert code == 1 and json.loads(out)["code"] == "plan_of_project"


def test_ctx_plan_of_reports_which_nodes_were_cut(server, capsys, tmp_path, monkeypatch):
    marker = {"truncated": True, "total": 3, "shown": 1, "cut": [{"id": "b", "name": "B"}, {"id": "c", "name": "C"}],
              "hint": "…"}
    monkeypatch.setattr(opora_heart, "call", lambda *args, **kwargs: {"items": [{"id": "a"}, marker]})
    code, out = run(capsys, "ctx", "plan-of", "--project", "p2", "--full")
    assert code == 0 and json.loads(out) == {"path": "dilna/data/plan-of-p2.json", "items": 1, "truncated": True,
                                             "total": 3, "cut": ["b", "c"], "bytes": json.loads(out)["bytes"]}
    code, out = run(capsys, "ctx", "plan-of", "--project", "p2")
    assert code == 0 and json.loads(out)["cut"] == ["b", "c"] and json.loads(out)["items"] == 1
    assert (tmp_path / json.loads(out)["path"]).read_text(encoding="utf-8").splitlines() == [
        "a · — ·  · ?", "… vynecháno 2 uzlů (dočti --node): b, c"]


def test_plan_lines_are_one_compact_row_per_node():
    items = [{"id": "s1", "kind": "sector", "name": "MVP", "path": "", "goal": "g" * 200, "steps": ["x"] * 9},
             {"id": "n_a", "kind": "node", "name": "[task] A", "path": "MVP", "stage": "ready", "goal": "g" * 200}]
    assert opora_heart.plan_lines(items) == ["s1 · — · MVP · sector", "n_a · MVP · [task] A · ready"]


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


MEMBER_GRAPH = {"nodes": [{"id": "a_pay", "kind": "area", "name": "Platby"},
                          {"id": "s_core", "kind": "sector", "name": "Jádro"},
                          {"id": "n_card", "kind": "node", "name": "Karta", "memberOf": "a_old"},
                          {"id": "n_done", "kind": "node", "name": "Už tam", "memberOf": "a_pay"},
                          {"id": "x_text", "kind": "text", "name": "Poznámka"}]}


def test_member_sends_only_member_of_updates_and_leaves_acceptance_to_the_human(server, capsys):
    Handler.manifest, Handler.graph = "m1", MEMBER_GRAPH
    code, out = run(capsys, "member", "--area", "a_pay", "--nodes", "s_core, n_card,n_done")
    result = json.loads(out)
    assert code == 0 and result["accepted"] is False and result["proposalId"] == "gp2"
    assert result["changes"] == [{"id": "s_core", "from": None, "to": "a_pay"},
                                 {"id": "n_card", "from": "a_old", "to": "a_pay"}]
    assert result["unchanged"] == ["n_done"] and "člověk" in result["hint"]
    posts = [call for call in Handler.calls if call["method"] == "POST"]
    assert [call["path"] for call in posts] == ["/api/oporahub/graph-proposals"]  # žádné /accept
    body = posts[0]["body"]
    assert (body["parentRevision"], body["expectedGraphDigest"]) == ("r1", "gd") and "Platby" in body["subject"]
    assert body["plan"] == {"updateNodes": [{"id": "s_core", "fields": {"memberOf": "a_pay"}},
                                            {"id": "n_card", "fields": {"memberOf": "a_pay"}}]}
    assert posts[0]["headers"]["X-Opora-Gate-Token"] == "tok-heart"


def accept_action(proposal_id, status="ready"):
    return {"verb": "accept", "method": "POST", "path": f"/api/oporahub/graph-proposals/{proposal_id}/accept",
            "status": status, "preconditions": {"expectedAcceptedHead": "r1", "expectedGraphDigest": "gd"}}


def test_member_with_full_autonomy_accepts_only_its_own_proposal(server, capsys):
    Handler.manifest, Handler.graph = "m1", MEMBER_GRAPH
    Handler.states = [{"autonomy": {"full": True}, "actions": [accept_action("gp_old"), accept_action("gp2")]}]
    result = json.loads(run(capsys, "member", "--area", "a_pay", "--nodes", "n_card")[1])
    assert result["accepted"] is True and result["proposalId"] == "gp2"
    posts = [call for call in Handler.calls if call["method"] == "POST"]
    assert [call["path"] for call in posts] == ["/api/oporahub/graph-proposals",
                                                "/api/oporahub/graph-proposals/gp2/accept"]
    assert posts[1]["body"]["expectedAcceptedHead"] == "r1"


def test_member_with_full_autonomy_reports_failed_acceptance(server, capsys):
    Handler.manifest, Handler.graph = "m1", MEMBER_GRAPH
    Handler.states = [{"autonomy": {"full": True}, "actions": []}]
    result = json.loads(run(capsys, "member", "--area", "a_pay", "--nodes", "n_card")[1])
    assert result["accepted"] is False and result["code"] == "proposal_not_offered"


def test_proposal_accept_uses_the_agent_state_action_and_needs_autonomy(server, capsys):
    Handler.states = [{"autonomy": {"full": True}, "actions": [accept_action("gp_old")]}]
    code, out = run(capsys, "proposal", "--accept", "gp_old")
    assert code == 0 and json.loads(out) == {"proposalId": "gp_old", "accepted": True}
    assert Handler.calls[-1]["path"] == "/api/oporahub/graph-proposals/gp_old/accept"
    code, out = run(capsys, "proposal", "--accept", "gp_x")
    assert code == 1 and json.loads(out)["code"] == "proposal_not_offered"
    Handler.states = [{"autonomy": {"full": False}, "actions": [accept_action("gp_old", "blocked")]}]
    Handler.calls.clear()
    code, out = run(capsys, "proposal", "--accept", "gp_old")
    assert code == 1 and json.loads(out)["hint"] == "Rozhodne člověk v UI."
    assert all(call["method"] == "GET" for call in Handler.calls)
    with pytest.raises(SystemExit):
        opora_heart.main(["proposal"])


def conflict_action(conflict_id, status="ready"):
    return {"verb": "proposal.resolve_conflict", "method": "POST", "targetId": conflict_id, "status": status,
            "path": f"/api/oporahub/auto-rebase/conflicts/{conflict_id}/resolve",
            "preconditions": {"expectedAcceptedHead": "r1", "proposalId": "p_ours"}}


def test_conflict_keep_accepted_posts_keep_and_needs_autonomy(server, capsys):
    Handler.states = [{"autonomy": {"full": True}, "actions": [conflict_action("c1")]}]
    code, out = run(capsys, "conflict", "--resolve", "c1", "--keep-accepted")
    assert code == 0 and json.loads(out)["conflictId"] == "c1"
    last = Handler.calls[-1]
    assert (last["method"], last["path"]) == ("POST", "/api/oporahub/auto-rebase/conflicts/c1/resolve")
    assert last["body"] == {"project": "p1", "workspace": "main", "keep": "accepted"}
    code, out = run(capsys, "conflict", "--resolve", "c_x", "--keep-accepted")
    assert code == 1 and json.loads(out)["code"] == "conflict_not_offered"
    Handler.states = [{"autonomy": {"full": False}, "actions": [conflict_action("c1")]}]
    Handler.calls.clear()
    code, out = run(capsys, "conflict", "--resolve", "c1", "--keep-accepted")
    assert code == 1 and json.loads(out)["hint"] == "Rozhodne člověk v UI."
    assert all(call["method"] == "GET" for call in Handler.calls)
    with pytest.raises(SystemExit):
        opora_heart.main(["conflict", "--resolve", "c1"])


def test_member_none_clears_membership(server, capsys):
    Handler.manifest, Handler.graph = "m1", MEMBER_GRAPH
    result = json.loads(run(capsys, "member", "--area", "none", "--nodes", "n_card,s_core")[1])
    assert result["changes"] == [{"id": "n_card", "from": "a_old", "to": None}] and result["unchanged"] == ["s_core"]
    post = next(call for call in Handler.calls if call["method"] == "POST")
    assert post["body"]["plan"] == {"updateNodes": [{"id": "n_card", "fields": {"memberOf": None}}]}


def test_member_dry_run_and_nothing_to_change_send_nothing(server, capsys):
    Handler.manifest, Handler.graph = "m1", MEMBER_GRAPH
    result = json.loads(run(capsys, "member", "--area", "a_pay", "--nodes", "n_card", "--dry-run")[1])
    assert result["dryRun"] is True and result["changes"] == [{"id": "n_card", "from": "a_old", "to": "a_pay"}]
    assert "proposalId" not in result
    result = json.loads(run(capsys, "member", "--area", "a_pay", "--nodes", "n_done")[1])
    assert result["changes"] == [] and "proposalId" not in result
    assert not [call for call in Handler.calls if call["method"] == "POST"]


@pytest.mark.parametrize(("argv", "code"), [
    (["--area", "s_core", "--nodes", "n_card"], "member_area"),
    (["--area", "a_missing", "--nodes", "n_card"], "member_area"),
    (["--area", "a_pay", "--nodes", "n_card,n_missing"], "member_unknown_node"),
    (["--area", "a_pay", "--nodes", "x_text"], "member_kind"),
    (["--area", "a_pay", "--nodes", "a_pay"], "member_kind"),
    (["--area", "a_pay", "--nodes", " , "], "member_nodes"),
])
def test_member_validates_area_and_nodes_before_sending(server, capsys, argv, code):
    Handler.manifest, Handler.graph = "m1", MEMBER_GRAPH
    exit_code, out = run(capsys, "member", *argv)
    assert exit_code == 1 and json.loads(out)["code"] == code
    assert not [call for call in Handler.calls if call["method"] == "POST"]


ORDER_GRAPH = {"nodes": [{"id": "a_pay", "kind": "area", "name": "Platby"},
                         {"id": "s_core", "kind": "sector", "name": "Jádro", "order": 100},
                         {"id": "n_card", "kind": "node", "name": "Karta", "order": 205},
                         {"id": "n_done", "kind": "node", "name": "Už tam", "order": 102},
                         {"id": "x_text", "kind": "text", "name": "Poznámka"}]}


def test_order_sends_only_order_updates_and_leaves_acceptance_to_the_human(server, capsys):
    Handler.manifest, Handler.graph = "m1", ORDER_GRAPH
    code, out = run(capsys, "order", "--nodes", "n_card=101, s_core=none,n_done=102")
    result = json.loads(out)
    assert code == 0 and result["accepted"] is False and result["proposalId"] == "gp2"
    assert result["changes"] == [{"id": "n_card", "from": 205, "to": 101}, {"id": "s_core", "from": 100, "to": None}]
    assert result["unchanged"] == ["n_done"] and "člověk" in result["hint"]
    posts = [call for call in Handler.calls if call["method"] == "POST"]
    assert [call["path"] for call in posts] == ["/api/oporahub/graph-proposals"]  # žádné /accept
    body = posts[0]["body"]
    assert (body["parentRevision"], body["expectedGraphDigest"]) == ("r1", "gd")
    assert body["plan"] == {"updateNodes": [{"id": "n_card", "fields": {"order": 101}},
                                            {"id": "s_core", "fields": {"order": None}}]}


def test_order_with_full_autonomy_accepts_only_its_own_proposal(server, capsys):
    Handler.manifest, Handler.graph = "m1", ORDER_GRAPH
    Handler.states = [{"autonomy": {"full": True}, "actions": [accept_action("gp_old"), accept_action("gp2")]}]
    result = json.loads(run(capsys, "order", "--nodes", "n_card=101")[1])
    assert result["accepted"] is True and result["proposalId"] == "gp2"
    assert [call["path"] for call in Handler.calls if call["method"] == "POST"] == [
        "/api/oporahub/graph-proposals", "/api/oporahub/graph-proposals/gp2/accept"]


def test_order_dry_run_and_nothing_to_change_send_nothing(server, capsys):
    Handler.manifest, Handler.graph = "m1", ORDER_GRAPH
    result = json.loads(run(capsys, "order", "--nodes", "n_card=101", "--dry-run")[1])
    assert result["dryRun"] is True and result["changes"] == [{"id": "n_card", "from": 205, "to": 101}]
    assert "proposalId" not in result
    result = json.loads(run(capsys, "order", "--nodes", "n_done=102")[1])
    assert result["changes"] == [] and "proposalId" not in result
    assert not [call for call in Handler.calls if call["method"] == "POST"]


@pytest.mark.parametrize(("nodes", "code"), [
    ("n_card=101,n_missing=102", "order_unknown_node"),
    ("x_text=101", "order_kind"),
    ("a_pay=101", "order_kind"),
    ("n_card=0", "order_value"),
    ("n_card=10000", "order_value"),
    ("n_card=1.5", "order_value"),
    ("n_card=-1", "order_value"),
    ("n_card", "order_value"),
    ("=101", "order_value"),
    (" , ", "order_nodes"),
])
def test_order_validates_nodes_and_values_before_sending(server, capsys, nodes, code):
    Handler.manifest, Handler.graph = "m1", ORDER_GRAPH
    exit_code, out = run(capsys, "order", "--nodes", nodes)
    assert exit_code == 1 and json.loads(out)["code"] == code
    assert not [call for call in Handler.calls if call["method"] == "POST"]


PAGES = {"graph": {"nodes": [{"id": "s_app", "kind": "sector", "name": "App", "site": {"kind": "application"}},
                             {"id": "n_home", "kind": "node", "name": "Domů", "parentId": "s_app",
                              "site": {"kind": "page", "path": "/"}, "order": 105},
                             {"id": "n_faq", "kind": "node", "name": "FAQ", "parentId": "s_app",
                              "site": {"kind": "page", "path": "/faq"}}],
                   "edges": [{"id": "e1", "source": "n_home", "target": "n_faq", "port": "next"}]},
         "revision": 7, "digest": "a7"}


def order_with_pages(differs=True):
    Handler.manifest, Handler.graph, Handler.differs = "m1", ORDER_GRAPH, differs
    Handler.architecture = json.loads(json.dumps(PAGES))


def test_order_splits_pages_into_the_architecture_and_cards_into_the_proposal(server, capsys):
    order_with_pages()
    result = json.loads(run(capsys, "order", "--nodes", "n_home=101,n_faq=102,n_card=201")[1])
    assert result["architecture"] == {"revision": 8, "changes": [{"id": "n_home", "from": 105, "to": 101},
                                                                 {"id": "n_faq", "from": None, "to": 102}]}
    assert result["changes"] == [{"id": "n_card", "from": 205, "to": 201}]
    assert result["proposalId"] == "gp2" and result["accepted"] is False and result["adoptArchitecture"] is True
    posts = [call for call in Handler.calls if call["method"] == "POST"]
    assert [call["path"] for call in posts] == ["/api/project-architecture", "/api/oporahub/graph-proposals"]
    saved = posts[0]["body"]
    assert (saved["project"], saved["workspace"], saved["expectedRevision"]) == ("p1", "main", 7)
    before, after = PAGES["graph"], saved["graph"]
    assert after["edges"] == before["edges"] and [node["id"] for node in after["nodes"]] == ["s_app", "n_home", "n_faq"]
    assert [node.get("order") for node in after["nodes"]] == [None, 101, 102]
    assert [{k: v for k, v in node.items() if k != "order"} for node in after["nodes"]] == [
        {k: v for k, v in node.items() if k != "order"} for node in before["nodes"]]  # jinak beze změny
    assert posts[1]["body"]["plan"] == {"adoptArchitectureContext": True,
                                        "updateNodes": [{"id": "n_card", "fields": {"order": 201}}]}


def test_order_of_pages_only_adopts_the_architecture_and_accepts_under_full_autonomy(server, capsys):
    order_with_pages()
    Handler.states = [{"autonomy": {"full": True}, "actions": [accept_action("gp2")]}]
    result = json.loads(run(capsys, "order", "--nodes", "n_home=none")[1])
    assert result["architecture"]["changes"] == [{"id": "n_home", "from": 105, "to": None}]
    assert result["accepted"] is True and result["changes"] == []
    posts = [call for call in Handler.calls if call["method"] == "POST"]
    assert [call["path"] for call in posts] == ["/api/project-architecture", "/api/oporahub/graph-proposals",
                                                "/api/oporahub/graph-proposals/gp2/accept"]
    assert "order" not in posts[0]["body"]["graph"]["nodes"][1]
    assert posts[1]["body"]["plan"] == {"adoptArchitectureContext": True}


def test_order_of_pages_without_an_accepted_plan_needs_no_proposal(server, capsys):
    order_with_pages(differs=False)
    Handler.manifest = None
    result = json.loads(run(capsys, "order", "--nodes", "n_faq=102")[1])
    assert result["path"] == "project-architecture" and result["accepted"] is True and result["proposalId"] is None
    assert [call["path"] for call in Handler.calls if call["method"] == "POST"] == ["/api/project-architecture"]


def test_order_of_pages_dry_run_and_server_refusal(server, capsys):
    order_with_pages()
    result = json.loads(run(capsys, "order", "--nodes", "n_home=101,n_card=201", "--dry-run")[1])
    assert result["dryRun"] is True and result["architecture"]["revision"] == 7 and "proposalId" not in result
    assert not [call for call in Handler.calls if call["method"] == "POST"]
    Handler.refuse = "/api/project-architecture"
    code, out = run(capsys, "order", "--nodes", "n_home=101")
    assert code == 1 and json.loads(out)["status"] == 403
    assert [call["path"] for call in Handler.calls if call["method"] == "POST"] == ["/api/project-architecture"]


def test_ordered_architecture_changes_only_order():
    graph = PAGES["graph"]
    after = opora_heart.ordered_architecture(graph, [{"id": "n_faq", "to": 102}, {"id": "n_home", "to": None}])
    assert [node.get("order") for node in after["nodes"]] == [None, None, 102] and graph["nodes"][1]["order"] == 105


def steps_file(tmp_path, data):
    path = tmp_path / "steps.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def step(title, kind="code", files=("a.py",)):
    return {"title": title, "kind": kind, "files": list(files), "acceptance": [f"{title} hotovo"]}


def test_steps_file_keeps_the_card_rule_and_fills_ids_linearly(tmp_path):
    from backend.canvas.opora_plan_steps import KINDS

    assert opora_heart.STEP_KINDS == KINDS  # kopie v nástroji (jen stdlib) se nerozejde se serverem
    done = opora_heart.read_steps(steps_file(tmp_path, {"steps": [step("A"), step("B", "test", ["test_a.py"])],
                                                        "goal": "Cíl"}))
    assert done["goal"] == "Cíl"
    assert [(item["id"], item["order"], item["dependsOn"]) for item in done["steps"]] == [
        ("s1", 1, []), ("s2", 2, ["s1"])]
    own = opora_heart.read_steps(steps_file(tmp_path, {"steps": [{**step("A"), "id": "x"}, step("B")]}))
    assert own["steps"][1]["dependsOn"] == ["x"]
    for bad, code in (({"steps": [step("A")]}, "steps_count"),
                      ({"steps": [step(str(i)) for i in range(9)]}, "steps_count"),
                      ({"steps": [step("A"), step("B", "build")]}, "steps_kind"),
                      ({"steps": [step("A"), step("B", files=())]}, "steps_files"),
                      ({"steps": [step("A"), step("B")], "non_goals": ""}, "steps_file"),
                      ({"steps": [step("A"), step("B")], "goal": 1}, "steps_file")):
        with pytest.raises(opora_heart.Failure) as failure:
            opora_heart.read_steps(steps_file(tmp_path, bad))
        assert failure.value.payload["code"] == code and "kind" in failure.value.payload["hint"]


def test_ticket_issue_and_answer_go_through_the_gate_with_the_heart_token(server, capsys, tmp_path):
    (tmp_path / "ticket.json").write_text(json.dumps({"body": {"essence": "Proč.", "build": "Co.",
                                                                "doneCriteria": ["npm test"]}}), encoding="utf-8")
    code, out = run(capsys, "ticket-issue", "--file", "@ticket.json", "--profile", "backend")
    assert code == 0 and json.loads(out) == {"ticket": {"ticketId": "tk_1", "status": "issued",
                                                        "machine": {"cardId": None}}}
    run(capsys, "ticket-answer", "--ticket", "tk_1", "--feedback", "tf_1", "--text", "Ano.")
    run(capsys, "ticket-answer", "--ticket", "gt_1", "--text", "Ne.")
    sent = [(call["path"], call["body"], call["headers"]["X-Opora-Gate-Token"]) for call in Handler.calls]
    assert sent == [
        ("/api/gate/requests", {"kind": "ticket.issue", "body": {"body": {"essence": "Proč.", "build": "Co.",
                                                                          "doneCriteria": ["npm test"]},
                                                                 "profile": "backend"}}, "tok-heart"),
        ("/api/gate/requests", {"kind": "ticket.answer", "body": {"ticketId": "tk_1", "text": "Ano.",
                                                                  "feedbackId": "tf_1"}}, "tok-heart"),
        ("/api/gate/requests", {"kind": "ticket.answer", "body": {"ticketId": "gt_1", "text": "Ne."}}, "tok-heart")]
    code, out = run(capsys, "ticket-issue", "--file", "@chybi.json")
    assert code == 1 and json.loads(out)["code"] == "ticket_file"