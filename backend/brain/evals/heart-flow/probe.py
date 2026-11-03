"""Empirická sonda toku mozku OPORY oběma směry (srdce → brána → pracovník, pracovník → lístky → srdce → člověk).

    uv run --project <repo> python backend/brain/evals/heart-flow/probe.py --run r1 [--scenarios F1,F2,...,REAL]

Spustí izolovanou OPORU se srdcem (`opora_serve.py --heart`) na portu 8792 nad `C:\\oe\\heart-flow\\<run>\\data`,
založí jako člověk projekt P1 nad malým git repem (skriptovaní pracovníci) a volitelně P2 nad šablonou T0 (jeden
skutečný pracovník Sonnet, scénář REAL běží souběžně ve vlákně). Pracovníci P1 jsou skriptovaní přes HTTP brány,
takže každý okrajový případ nastane přesně. Výsledky (syrové doklady) jdou do `results.json` vedle skriptu,
po každém scénáři. Produktový kód se nemění. Stdlib + importy harnessu evalu.

Scénáře O (`orch.py`, docs/brain-heart-orchestrator.md): předávka srdce ↔ orchestrátor nad vlastním lokálním
projektem (repo `<run>\app`), server přes `orch_serve.py` se zkráceným hlídačem gitu:

    uv run --project <repo> python backend/brain/evals/heart-flow/probe.py --run o1 --scenarios O1 \
        --variant cards|tasks [--phase auto|all|one] [--rounds 4] [--git-poll 30]
    uv run --project <repo> python backend/brain/evals/heart-flow/probe.py --table   # srovnání O1 z results.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import http.server
import socketserver
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FLOW = REPO / "backend" / "brain" / "evals" / "opora-vs-bare"
MULTI = FLOW / "multi"
sys.path[:0] = [str(MULTI), str(FLOW)]
import grade  # noqa: E402
import heart_arm  # noqa: E402
import run_eval  # noqa: E402
import sessions  # noqa: E402

sys.path.insert(0, str(HERE))
import orch  # noqa: E402

PORT = 8792
ROOT = Path(r"C:\oe\heart-flow")
RESULTS = HERE / "results.json"
WS = "draft"
BUDGET_USD = 6.0
STOP_AT_USD = 5.2          # nad tímto součtem se další scénáře se srdcem přeskočí
ORDER = ["F1", "WALL", "F2", "F3", "F5", "R1", "R2", "R3", "R4", "R5", "F4", "R6", "X1", "X1b", "X2"]
OPENER = build_opener(ProxyHandler({}))

INTENT = """Postav malou webovou aplikaci kurzu keramiky „Hrnek z ničeho“ (React + Vite v tomto repozitáři), dvě stránky:
1. Domů (/): nadpis, dvě věty o kurzu pro úplné začátečníky, termín „každé úterý 18–20 h“ a tlačítko na přihlášku.
2. Přihláška (/prihlaska): formulář jméno + e-mail, chyba u pole, po odeslání poděkování na stejné stránce.

Cílovka: dospělí začátečníci, kteří se bojí, že to nezvládnou. Pocit: klidně, vlídně, bez nátlaku.

Pravidla celé aplikace (platí navždy):
- texty česky a tykáním (oslovujeme „ty“), nikdy vykání;
- barvy jen z src/styles/tokens.css;
- jeden h1 na stránku;
- žádné manipulativní prvky: žádné odpočty, „poslední místa“, falešná naléhavost;
- každý formulář má popisky a chybu u pole s aria-invalid.

""" + sessions.FOOTER

VYKANI = re.compile(r"\b(přihlaste|napište|vyplňte|zadejte|odešlete|pokračujte|klikněte|ozvěte|vaše|vašeho|vaši|váš|"
                    r"vám|vás|jste|budete|chcete|můžete|zkuste|podívejte)\b", re.IGNORECASE)
TYKANI = re.compile(r"\b(přihlas|napiš|vyplň|zadej|odešli|pokračuj|klikni|ozvi|tvoje|tvůj|tvého|tvoji|tobě|tebe|"
                    r"jsi|budeš|chceš|můžeš|zkus|podívej|zvládneš|přijď)\b", re.IGNORECASE)


def now():
    return time.time()


def iso_epoch(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


# --- HTTP ---------------------------------------------------------------------------------------------

class Api:
    def __init__(self, base, secret):
        self.base, self.secret = base, secret

    def req(self, method, path, body=None, query=None, token=None, human=False, timeout=60):
        url = self.base + path + ("?" + urlencode(query) if query else "")
        headers = {"Accept": "application/json", "Origin": self.base}
        if human:
            headers["Cookie"] = f"opora_ui={self.secret}"
        if token:
            headers["X-Opora-Gate-Token"] = token
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json"
        t0 = now()
        try:
            with OPENER.open(Request(url, data=data, headers=headers, method=method), timeout=timeout) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None), round(now() - t0, 3)
        except HTTPError as e:
            raw = e.read()
            try:
                payload = json.loads(raw) if raw else None
            except ValueError:
                payload = {"raw": raw[:300].decode("utf-8", "replace")}
            return e.code, payload, round(now() - t0, 3)

    def human(self, method, path, body=None, query=None):
        status, payload, _ = self.req(method, path, body, query, human=True)
        if status >= 400:
            raise RuntimeError(f"{method} {path} -> {status}: {payload}")
        return payload


class Worker:
    """Skriptovaný pracovník: relace brány a druhy přes HTTP (bez modelu)."""

    def __init__(self, api, project, name):
        self.api, self.project, self.name, self.after = api, project, name, 0
        status, body, _ = api.req("POST", "/api/gate/sessions", {"project": project, "workspace": WS,
                                                                 "worker": {"name": name}})
        if status != 201:
            raise RuntimeError(f"relace {name}: {status} {body}")
        self.token, self.session = body["token"], body["sessionId"]

    def kind(self, kind, body=None, query=None):
        return self.api.req("POST", "/api/gate/requests", {"kind": kind, "body": body or {}}, query, token=self.token)

    def next(self):
        status, body, dt = self.kind("next")
        task = (body or {}).get("answer", {}).get("task") if status == 201 else None
        return status, body, task, dt

    def report(self, task_id, sha, red=False, output=""):
        checks = [{"name": "npm run build", "status": "green"},
                  {"name": "npm test", "status": "red" if red else "green", **({"output": output} if output else {})}]
        return self.kind("report", {"taskId": task_id, "sha": sha, "summary": f"{self.name}: skriptované hlášení",
                                    "checks": checks})

    def ask(self, question, task_id=None):
        return self.kind("ask", {"question": question, **({"taskId": task_id} if task_id else {})})

    def inbox(self, wait=0):
        status, body, dt = self.api.req("GET", "/api/gate/inbox", query={"after": self.after, "wait": wait},
                                        token=self.token, timeout=wait + 30)
        if status == 200:
            self.after = body["last"]
        return status, body, dt

    def wait_answer(self, ticket_id, limit_s=900):
        """Long-poll schránky, dokud nepřijde odpověď na lístek; vrací (sekundy, lístek) nebo (None, None)."""
        t0 = now()
        while now() - t0 < limit_s:
            status, body, _ = self.inbox(wait=30)
            for ticket in (body or {}).get("tickets", []) if status == 200 else []:
                if ticket.get("ticketId") == ticket_id:
                    return round(now() - t0, 1), ticket
        return None, None


# --- běh: server, projekty, srdce ---------------------------------------------------------------------

def git(ws, *args):
    return subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@local", "-c", "core.autocrlf=false",
                           *args], cwd=ws, capture_output=True, text=True, check=True).stdout.strip()


def make_scripted_ws(ws):
    """Malé git repo P1: build/test jsou no-op přes `node -e`, ale struktura odpovídá React + Vite (srdce ji čte)."""
    files = {
        "package.json": json.dumps({"name": "hrnek", "private": True, "type": "module", "scripts": {
            "build": "node -e \"process.exit(0)\"", "test": "node -e \"process.exit(0)\""}}, indent=2),
        "index.html": "<!doctype html><html lang=\"cs\"><body><div id=\"root\"></div>"
                      "<script type=\"module\" src=\"/src/main.tsx\"></script></body></html>\n",
        "src/main.tsx": "import { createRoot } from 'react-dom/client'\nimport App from './App'\n"
                        "createRoot(document.getElementById('root')!).render(<App />)\n",
        "src/App.tsx": "export default function App() {\n  return <main><h1>Kurz keramiky</h1></main>\n}\n",
        "src/App.test.tsx": "import { render, screen } from '@testing-library/react'\nimport App from './App'\n"
                            "test('h1', () => { render(<App />); expect(screen.getByRole('heading', { level: 1 }))"
                            ".toHaveTextContent('Kurz keramiky') })\n",
        "src/styles/tokens.css": ":root { --barva-text: #2b2b2b; --barva-pozadi: #fbf8f3; --barva-akcent: #8a5a44; }\n",
    }
    for rel, text in files.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "kostra")


def make_real_ws(ws):
    shutil.copytree(FLOW / "templates" / "T0", ws, ignore=shutil.ignore_patterns("node_modules", "dist"))
    subprocess.run([shutil.which("npm") or "npm", "ci", "--prefer-offline", "--no-audit", "--no-fund"], cwd=ws,
                   capture_output=True, check=True, timeout=900, shell=os.name == "nt")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "šablona T0")


def start_server(run_dir, git_poll=None):
    """`git_poll` (scénáře O): server přes obal `orch_serve.py`, který zkrátí periodu hlídače gitu srdce."""
    secret = os.urandom(24).hex()
    ready = run_dir / "opora-ready.json"
    ready.unlink(missing_ok=True)
    out = (run_dir / "opora.log").open("ab")
    serve = [str(HERE / "orch_serve.py"), "--git-poll", str(git_poll)] if git_poll else [str(MULTI / "opora_serve.py")]
    proc = subprocess.Popen([shutil.which("uv") or "uv", "run", "--project", str(REPO), "python",
                             *serve, "--heart", "--data", str(run_dir / "data"),
                             "--repo", str(run_dir / "ws-s"), "--port", str(PORT), "--ready-file", str(ready)],
                            cwd=REPO, stdout=out, stderr=out,
                            # child_env zahodí OPORA_*; přepínač enginu srdce sondě předáme výslovně
                            env=run_eval.child_env({"OPORA_EVAL_UI_SECRET": secret,
                                                    "OPORA_FLOW_HEART": os.environ.get("OPORA_FLOW_HEART", "off")}))
    deadline = now() + 180
    api = Api(f"http://127.0.0.1:{PORT}", secret)
    while now() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("OPORA skončila při startu: " + (run_dir / "opora.log").read_text("utf-8", "replace")[-800:])
        if ready.exists():
            try:
                OPENER.open(api.base + "/api/bootstrap", timeout=3).read()
                return proc, api
            except (URLError, OSError, HTTPError):
                pass
        time.sleep(0.5)
    grade.kill_tree(proc)
    raise RuntimeError("OPORA nenaběhla do 180 s")


class Run:
    def __init__(self, name, api, run_dir):
        self.name, self.api, self.dir = name, api, run_dir
        self.projects, self.worker_usd, self.lock = {}, 0.0, threading.Lock()
        self.results = json.loads(RESULTS.read_text("utf-8")) if RESULTS.exists() else {}
        self.results.setdefault("runs", {})[name] = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "port": PORT,
                                                     "dataRoot": str(run_dir / "data"), "scenarios": {}}

    def project(self, key, ws, label):
        made = self.api.human("POST", "/api/local-project", {"name": label, "path": str(ws), "confirmed": True})
        pid = made["id"]
        gate = self.api.human("POST", "/api/brain/gate-setting", {"project": pid, "enabled": True})
        assert gate.get("enabled") is True, gate
        self.projects[key] = {"id": pid, "ws": ws}
        time.sleep(12)  # supervisor si u nového projektu nastaví kurzor (POLL 10 s), než přijdou události
        return pid

    def brain(self, key):
        return heart_arm.project_dir(self.dir / "data", self.projects[key]["id"]) / "brain"

    def db(self, key):
        return heart_arm.project_dir(self.dir / "data", self.projects[key]["id"]) / "project.sqlite"

    def batches(self, key):
        return heart_arm.read_batches(self.brain(key))

    def status(self, key):
        return self.api.human("GET", "/api/brain/heart/status", query={"project": self.projects[key]["id"]})

    def tasks(self, key):
        got = self.api.human("GET", "/api/brain/tasks", query={"project": self.projects[key]["id"], "workspace": WS})
        return got.get("tasks", [])

    def heart_usd(self):
        return round(sum(heart_arm.heart_cost(self.batches(k))["usd"] for k in self.projects), 4)

    def spent(self):
        return round(self.heart_usd() + self.worker_usd, 4)

    def wait_heart(self, key, before, need_new=True, timeout=900, settle=6.0):
        return heart_arm.wait_heart(lambda: self.status(key), lambda: len(self.batches(key)), before,
                                    need_new=need_new, timeout=timeout, settle=settle)

    def save(self, scenario, evidence):
        with self.lock:
            run = self.results["runs"][self.name]
            run["scenarios"][scenario] = evidence
            run["spentUsd"] = self.spent()
            run["heartUsd"], run["workerUsd"] = self.heart_usd(), round(self.worker_usd, 4)
            RESULTS.write_text(json.dumps(self.results, ensure_ascii=False, indent=1), encoding="utf-8")


# --- rozbor dávek a úkolů -----------------------------------------------------------------------------

def batch_view(entry):
    at = iso_epoch(entry["at"])
    return {"at": entry["at"], "endEpoch": round(at + (entry.get("durationMs") or 0) / 1000, 1), "startEpoch": at,
            "status": entry.get("status"), "costUsd": entry.get("costUsd"), "costByModel": entry.get("costByModel"),
            "numTurns": entry.get("numTurns"), "subCostUsd": entry.get("subCostUsd"), "durationS": round((entry.get("durationMs") or 0) / 1000, 1),
            "advisor": entry.get("advisor"), "resumed": entry.get("resumed"), "inputTokens": entry.get("inputTokens"),
            "inputs": [{k: v for k, v in i.items() if k in ("type", "ticketId", "kind", "taskId", "text")}
                       for i in entry.get("inputs", [])],
            "summary": entry.get("summary"), "error": entry.get("error"), "sessionId": entry.get("sessionId"),
            "transcript": transcript_stats(entry)}


def transcript_stats(entry):
    """Tahy dávky z přepisu relace Claude Code (`~/.claude/projects/*/<session>.jsonl`), filtr podle času dávky."""
    sid = entry.get("sessionId")
    files = list((Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl")) if sid else []
    if not files:
        return {"found": False}
    start = iso_epoch(entry["at"]) - 1
    end = start + (entry.get("durationMs") or 0) / 1000 + 5
    tools, errors, commands, advisor = {}, [], [], 0
    for line in files[0].read_text("utf-8", "replace").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        ts = ev.get("timestamp")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if not start <= t <= end:
            continue
        for block in (ev.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") in ("tool_use", "server_tool_use"):
                name = block.get("name", "?")
                tools[name] = tools.get(name, 0) + 1
                if "advisor" in name.lower():
                    advisor += 1
                if name == "Bash":
                    commands.append(str(block.get("input", {}).get("command", ""))[:160])
            if block.get("type") == "tool_result":
                text = json.dumps(block.get("content"), ensure_ascii=False)
                codes = re.findall(r'\\"code\\": \\"([a-z_0-9]+)\\"', text) or re.findall(r'"code": "([a-z_0-9]+)"', text)
                if block.get("is_error") or codes:
                    errors.append({"codes": codes, "text": text[:240]})
    return {"found": True, "tools": tools, "advisorCalls": advisor, "errors": errors, "bash": commands}


def task_shape(task):
    body = task.get("body") or {}
    ctx = body.get("context") or {}
    text = " ".join([task.get("title", ""), body.get("do", ""), " ".join(body.get("doneWhen") or [])])
    return {"id": task.get("taskId"), "title": task.get("title"), "order": task.get("order"),
            "status": task.get("status"), "createdBy": task.get("createdBy"),
            "has": {"why": bool(body.get("why")), "do": bool(body.get("do")), "files": bool(body.get("files")),
                    "doneWhen": bool(body.get("doneWhen")), "dontTouchKey": "dontTouch" in body,
                    "dontTouchNonEmpty": bool(body.get("dontTouch")), "rules": bool(ctx.get("rules")),
                    "model": body.get("model")},
            "files": body.get("files"), "doneWhenN": len(body.get("doneWhen") or []), "rulesN": len(ctx.get("rules") or []),
            "vykani": sorted({m.lower() for m in VYKANI.findall(text)}),
            "tykani": sorted({m.lower() for m in TYKANI.findall(text)}), "doChars": len(body.get("do") or "")}


def task_diff(before, after):
    old = {t["taskId"]: t["status"] for t in before}
    created = [task_shape(t) for t in after if t["taskId"] not in old]
    changed = [{"id": t["taskId"], "title": t["title"], "from": old[t["taskId"]], "to": t["status"]}
               for t in after if t["taskId"] in old and old[t["taskId"]] != t["status"]]
    return {"created": created, "changed": changed}


def escalations(run, key):
    return run.api.human("GET", "/api/brain/heart/escalations",
                         query={"project": run.projects[key]["id"], "workspace": WS})["escalations"]


def new_batches(run, key, before):
    return [batch_view(b) for b in run.batches(key)[before:]]


def sha(run, key):
    return git(run.projects[key]["ws"], "rev-parse", "HEAD")


def wait_tickets_answered(worker, ticket_ids, limit_s=900):
    """Odpovědi na několik lístků jedné relace: {ticketId: (sekundy, odpověď)}."""
    t0, got = now(), {}
    while now() - t0 < limit_s and len(got) < len(ticket_ids):
        status, body, _ = worker.inbox(wait=30)
        for ticket in (body or {}).get("tickets", []) if status == 200 else []:
            if ticket.get("ticketId") in ticket_ids:
                got[ticket["ticketId"]] = (round(now() - t0, 1), ticket.get("answer"), ticket.get("answeredBy"))
    return got


def ask_and_wait(run, key, worker, question, task_id=None, kind="ask", body=None):
    """Lístek pracovníka → dávka srdce → odpověď ve schránce; měří latenci a dávku."""
    before_b, before_t, esc0 = len(run.batches(key)), run.tasks(key), {e["ticketId"] for e in escalations(run, key)}
    t0 = now()
    if kind == "ask":
        status, ticket, dt = worker.ask(question, task_id)
    else:
        status, ticket, dt = worker.kind(kind, body)
    tid = (ticket or {}).get("ticketId")
    latency, answered = worker.wait_answer(tid, 900) if status == 201 else (None, None)
    try:
        run.wait_heart(key, before_b)
    except Exception as error:  # noqa: BLE001
        log("wait_heart:", error)
    batches = new_batches(run, key, before_b)
    esc = [e for e in escalations(run, key) if e["ticketId"] not in esc0]
    first = batches[0] if batches else None
    return {"request": {"status": status, "ticketId": tid, "httpS": dt, "kind": kind},
            "answerLatencyS": latency, "answer": (answered or {}).get("answer"),
            "answeredBy": (answered or {}).get("answeredBy"),
            "batchStartAfterTicketS": round(first["startEpoch"] - t0, 1) if first else None,
            "batchEndAfterTicketS": round(first["endEpoch"] - t0, 1) if first else None,
            "batches": batches, "newEscalations": esc, "tasks": task_diff(before_t, run.tasks(key))}


# --- scénáře ------------------------------------------------------------------------------------------

def plan_from_intent(run, key):
    """F1 (a plán P2 pro REAL): zpráva člověka → dávka → úkoly. Měří čas do 1. úkolu, cenu a tvar."""
    before = len(run.batches(key))
    t0 = now()
    reply = run.api.human("POST", "/api/brain/heart/messages", {"project": run.projects[key]["id"], "workspace": WS,
                                                                "text": INTENT})
    first = None
    while now() - t0 < 900:
        if first is None and run.tasks(key):
            first = round(now() - t0, 1)
        st = run.status(key)
        if len(run.batches(key)) > before and not st.get("running") and not st.get("pending"):
            break
        time.sleep(2)
    total = round(now() - t0, 1)
    tasks = run.tasks(key)
    shapes = [task_shape(t) for t in tasks]
    batches = new_batches(run, key, before)
    snap = run.api.human("GET", "/api/brain/heart/snapshot", query={"project": run.projects[key]["id"],
                                                                   "workspace": WS})["snapshot"]
    orders = [s["order"] for s in shapes]
    return {"messageReply": reply, "firstTaskS": first, "batchDoneS": total, "taskCount": len(tasks),
            "orders": orders, "ordersDistinct": len(set(orders)) == len(orders),
            "shapeComplete": sum(1 for s in shapes if all(s["has"][k] for k in ("why", "do", "files", "doneWhen", "rules"))),
            "withModel": sum(1 for s in shapes if s["has"]["model"]), "withVykani": sum(1 for s in shapes if s["vykani"]),
            "tasks": shapes, "batches": batches, "snapshotAfter": snap,
            "intentInSnapshot": "Hrnek" in snap or "keramik" in snap.lower()}


def s_f1(run):
    return plan_from_intent(run, "P1")


def s_wall(run):
    p1, p2 = run.projects["P1"]["id"], run.projects.get("P2", {}).get("id")
    w = Worker(run.api, p1, "wall-a")
    other = Worker(run.api, p1, "wall-b")
    out = {}

    def rec(label, status, body):
        out[label] = {"status": status, "code": (body or {}).get("code"), "hint": (body or {}).get("hint")}
        if not (body or {}).get("code"):
            out[label]["body"] = json.dumps(body, ensure_ascii=False)[:300]

    s, b, _ = w.kind("task.create", {"title": "x", "body": {"do": "x"}})
    rec("worker_task.create", s, b)
    s, b, _ = w.kind("ticket.answer", {"ticketId": "gt_" + "0" * 32, "text": "x"})
    rec("worker_ticket.answer", s, b)
    s, b, _ = w.kind("escalate", {"text": "x"})
    rec("worker_escalate", s, b)
    s, b, _ = run.api.req("POST", "/api/brain/tasks", {"project": p1, "workspace": WS, "title": "x", "body": {"do": "x"}},
                          token=w.token)
    rec("worker_POST_/api/brain/tasks", s, b)
    s, b, _ = run.api.req("POST", "/api/brain/tasks", {"project": p1, "workspace": WS, "title": "x", "body": {"do": "x"}})
    rec("anonymous_POST_/api/brain/tasks", s, b)
    s, b, _ = run.api.req("POST", "/api/brain/heart/messages", {"project": p1, "workspace": WS, "text": "x"}, token=w.token)
    rec("worker_POST_heart_messages", s, b)
    s, b, _ = run.api.req("GET", "/api/brain/heart/escalations", query={"project": p1, "workspace": WS}, token=w.token)
    rec("worker_GET_escalations", s, b)
    if p2:
        s, b, _ = w.kind("next", query={"project": p2})
        rec("worker_next_other_project(?project=P2)", s, b)
        s, b, _ = run.api.req("POST", "/api/gate/sessions", {"project": p2, "workspace": WS, "worker": {"name": "x"}})
        rec("open_session_on_P2_without_proof", s, {"code": (b or {}).get("code"), "hint": "201 = kdokoli na loopbacku"})
    s, b, _ = run.api.req("POST", "/api/gate/requests", {"kind": "next", "body": {}}, token="neplatny-token")
    rec("invalid_token", s, b)
    s, b, _ = other.ask("cizí lístek")
    foreign = (b or {}).get("ticketId")
    s, b, _ = run.api.req("GET", f"/api/gate/tickets/{foreign}", token=w.token)
    rec("worker_reads_other_workers_ticket", s, b)
    s, b, _ = run.api.req("POST", f"/api/gate/tickets/{foreign}/answer", {"answer": {"text": "x"}},
                          query={"project": p1}, token=w.token)
    rec("worker_answers_ticket", s, b)
    run.api.human("POST", f"/api/gate/tickets/{foreign}/answer", {"answer": {"text": "uklizeno sondou"}},
                  query={"project": p1})
    s, b, _ = run.api.req("GET", "/api/brain/tasks", query={"project": p1, "workspace": WS}, token=w.token)
    out["worker_reads_all_tasks"] = {"status": s, "visibleTasks": len((b or {}).get("tasks", [])),
                                     "seesOtherSessionIds": sorted({t.get("sessionId") for t in (b or {}).get("tasks", [])
                                                                    if t.get("sessionId")})[:3]}
    s, b, _ = run.api.req("GET", "/api/gate/kinds", token=w.token)
    out["worker_kinds"] = {"status": s, "role": (b or {}).get("role"),
                           "kinds": [k["kind"] for k in (b or {}).get("kinds", [])]}
    # report cizího úkolu a vymyšlené sha: úkol od člověka (srdce nebudí), nejvyšší order, aby nepředběhl plán
    made = run.api.human("POST", "/api/brain/tasks", {"project": p1, "workspace": WS, "order": 0,
                                                      "title": "SONDA: zeď", "body": {"do": "nic"}})
    tasks_ready = [t for t in run.tasks("P1") if t["status"] == "ready"]
    held = None
    s, b, held, _ = other.next()
    out["wallTaskIsHumanProbe"] = (held or {}).get("title") == "SONDA: zeď"
    s, b, _ = w.report(held["id"], sha(run, "P1")) if held else (None, None, None)
    rec("worker_reports_other_sessions_task", s, b)
    if held:
        s, b, _ = other.report(held["id"], "0000000")
        out["fake_sha_0000000_accepted"] = {"status": s, "taskStatus": ((b or {}).get("answer") or {}).get("task"),
                                           "taskId": held["id"], "note": "sha není ověřeno proti repu"}
    out["humanTask"] = made["taskId"]
    out["readyBefore"] = len(tasks_ready)
    return out


def s_f2(run):
    before = len(run.batches("P1"))
    w = Worker(run.api, run.projects["P1"]["id"], "f2-worker")
    s, b, task, dt = w.next()
    out = {"next": {"status": s, "httpS": dt, "taskId": (task or {}).get("id"), "title": (task or {}).get("title"),
                    "order": None}}
    if not task:
        return {**out, "error": "fronta prázdná"}
    t_report = now()
    s, b, dt = w.report(task["id"], sha(run, "P1"))
    out["report"] = {"status": s, "httpS": dt, "answer": (b or {}).get("answer")}
    time.sleep(35)
    st = run.status("P1")
    out["after35s"] = {"newBatches": len(run.batches("P1")) - before, "pending": st.get("pending"),
                       "running": st.get("running")}
    out["heartWoken"] = out["after35s"]["newBatches"] > 0 or bool(st.get("pending")) or bool(st.get("running"))
    out["reportToDoneS"] = round(now() - t_report, 1)
    return out


def s_f3(run):
    w = Worker(run.api, run.projects["P1"]["id"], "f3-worker")
    s, b, task, _ = w.next()
    if not task:
        return {"error": "fronta prázdná"}
    out = {"task": {"id": task["id"], "title": task["title"]}}
    before = len(run.batches("P1"))
    s, b, _ = w.report(task["id"], sha(run, "P1"), red=True,
                       output="FAIL src/App.test.tsx > h1: expected 'Kurz keramiky' to be 'Hrnek z ničeho'")
    out["red1"] = {"status": s, "answer": (b or {}).get("answer")}
    time.sleep(30)
    st = run.status("P1")
    out["afterRed1"] = {"newBatches": len(run.batches("P1")) - before, "pending": st.get("pending")}
    s, b, again, _ = w.next()
    out["nextAfterRed1"] = {"sameTask": (again or {}).get("id") == task["id"], "got": (again or {}).get("title"),
                            "attempts": (again or {}).get("attempts")}
    if (again or {}).get("id") != task["id"]:
        out["note"] = "po první červené dostal pracovník jiný úkol; druhá červená jde na ten"
        task = again
    before_t = run.tasks("P1")
    t_fail = now()
    s, b, _ = w.report(task["id"], sha(run, "P1"), red=True,
                       output="FAIL src/App.test.tsx > h1: expected 'Kurz keramiky' to be 'Hrnek z ničeho' (stejně)")
    out["red2"] = {"status": s, "answer": (b or {}).get("answer")}
    try:
        run.wait_heart("P1", before + out["afterRed1"]["newBatches"])
    except Exception as error:  # noqa: BLE001
        out["waitError"] = str(error)
    batches = [x for x in new_batches(run, "P1", before) if any(i.get("type") == "taskFailed" for i in x["inputs"])]
    if batches:
        out["failToBatchStartS"] = round(batches[0]["startEpoch"] - t_fail, 1)
        out["failToBatchEndS"] = round(batches[0]["endEpoch"] - t_fail, 1)
    out["batches"] = batches
    out["tasks"] = task_diff(before_t, run.tasks("P1"))
    out["escalations"] = escalations(run, "P1")
    return out


def s_f5(run):
    p1 = run.projects["P1"]["id"]
    a, b = Worker(run.api, p1, "f5-abandons"), Worker(run.api, p1, "f5-other")
    s, _, held, _ = a.next()
    if not held:
        return {"error": "fronta prázdná"}
    out = {"abandoned": {"id": held["id"], "title": held["title"]}}
    s, _, other, _ = b.next()
    out["otherGets"] = {"id": (other or {}).get("id"), "distinct": (other or {}).get("id") != held["id"]}
    out["releaseKind"] = "neexistuje (kinds: next/ask/report/change/state/inbox); revoke jen v procesu (tokens.revoke)"
    s, body, _ = a.kind("release", {"taskId": held["id"]})
    out["release_attempt"] = {"status": s, "code": (body or {}).get("code")}
    snap = run.api.human("GET", "/api/brain/heart/snapshot", query={"project": p1, "workspace": WS})["snapshot"]
    out["snapshotShowsAssigned"] = [line for line in snap.splitlines() if "assigned" in line or "FRONTA" in line][:4]
    if other:
        b.report(other["id"], sha(run, "P1"))
    s, _, again, _ = b.next()
    out["beforeExpiry_otherNext"] = {"gotAbandoned": (again or {}).get("id") == held["id"]}
    if again and again["id"] != held["id"]:
        b.report(again["id"], sha(run, "P1"))
    # instrumentace: vypršení tokenu (žádné API pro odvolání relace neexistuje); jen izolovaná data běhu
    with sqlite3.connect(run.db("P1"), timeout=10) as con:
        con.execute("UPDATE gate_sessions SET expires_at='2000-01-01T00:00:00Z' WHERE id=?", (a.session,))
    s, body, _ = a.kind("next")
    out["abandonerAfterExpiry"] = {"status": s, "code": (body or {}).get("code")}
    t0 = now()
    s, _, reclaimed, _ = b.next()
    out["afterExpiry_otherNext"] = {"gotAbandoned": (reclaimed or {}).get("id") == held["id"],
                                    "got": (reclaimed or {}).get("title"), "httpS": round(now() - t0, 2)}
    status = next((t["status"] for t in run.tasks("P1") if t["taskId"] == held["id"]), None)
    out["abandonedStatusNow"] = status
    if reclaimed:
        b.report(reclaimed["id"], sha(run, "P1"))
    out["tokenTtlH"] = 8
    return out


def r_worker(run):
    if not hasattr(run, "r_worker"):
        w = Worker(run.api, run.projects["P1"]["id"], "r-worker")
        s, _, task, _ = w.next()
        run.r_worker = (w, task)
    return run.r_worker


def s_r1(run):
    w, task = r_worker(run)
    tid = (task or {}).get("id")
    q = (f"Úkol {tid}: potřebuju upravit src/styles/tokens.css, který není ve files – přidat proměnnou "
         "--barva-chyba (#b3261e) pro chybové hlášky formuláře. Smím?")
    return {"task": (task or {}).get("title"), **ask_and_wait(run, "P1", w, q, tid)}


def s_r2(run):
    w, task = r_worker(run)
    tid = (task or {}).get("id")
    q = (f"Úkol {tid}: marketing chce na Domů červený banner s odpočtem „Poslední 3 místa – přihlas se do 24 h!“. "
         "Mám ho přidat do tohoto úkolu?")
    return ask_and_wait(run, "P1", w, q, tid)


def s_r3(run):
    w, task = r_worker(run)
    tid = (task or {}).get("id")
    body = {"proposal": "Rozděl úkol formuláře přihlášky na dva: (1) pole a validace s aria-invalid, (2) poděkování "
                        "po odeslání a test.", "reason": "Jeden úkol je na 30 min moc; dva menší jdou ověřit zvlášť.",
            **({"taskId": tid} if tid else {})}
    return ask_and_wait(run, "P1", w, None, kind="change", body=body)


def s_r4(run):
    p1 = run.projects["P1"]["id"]
    a, b = Worker(run.api, p1, "r4-a"), Worker(run.api, p1, "r4-b")
    before_b, before_t = len(run.batches("P1")), run.tasks("P1")
    t0 = now()
    _, ta, _ = a.ask("src/App.test.tsx čeká h1 „Kurz keramiky“, ale úkol Domů předepisuje jiný h1. "
                     "Smím test upravit, nebo mám nechat starý h1?")
    time.sleep(2)
    _, tb, _ = b.ask("Test v src/App.test.tsx padne, protože kontroluje starý nadpis „Kurz keramiky“. "
                     "Mám ho přepsat na nový nadpis z úkolu?")
    ids = [ta["ticketId"], tb["ticketId"]]
    got_a = wait_tickets_answered(a, [ids[0]])
    got_b = wait_tickets_answered(b, [ids[1]])
    try:
        run.wait_heart("P1", before_b)
    except Exception as error:  # noqa: BLE001
        log("wait_heart:", error)
    batches = new_batches(run, "P1", before_b)
    return {"tickets": ids, "gapS": 2, "batchCount": len(batches),
            "inputsPerBatch": [len(x["inputs"]) for x in batches],
            "answers": {k: {"latencyS": v[0], "answer": v[1], "by": v[2]} for k, v in {**got_a, **got_b}.items()},
            "batches": batches, "tasks": task_diff(before_t, run.tasks("P1")), "elapsedS": round(now() - t0, 1)}


def s_r5(run):
    esc = escalations(run, "P1")
    out = {"openEscalationsBefore": esc}
    if not esc:
        w, task = r_worker(run)
        out["trigger"] = ask_and_wait(run, "P1", w, "Na Domů chybí cena kurzu a záměr ji neuvádí. Jakou cenu mám "
                                      "uvést (Kč za 8 lekcí)?", (task or {}).get("id"))
        esc = escalations(run, "P1")
    if not esc:
        return {**out, "error": "srdce neeskalovalo ani otázku na cenu"}
    target = esc[0]
    before_b, before_t = len(run.batches("P1")), run.tasks("P1")
    st0 = run.status("P1")
    t0 = now()
    answered = run.api.human("POST", f"/api/gate/tickets/{target['ticketId']}/answer",
                             {"answer": {"text": "Banner s odpočtem ani „poslední místa“ nechceme, žádná falešná "
                                                 "naléhavost. Cenu zatím neuváděj; místo toho na Domů věta "
                                                 "„Cenu ti rádi řekneme na přihlášce.“"}},
                             query={"project": run.projects["P1"]["id"]})
    seen_running = None
    while now() - t0 < 120 and seen_running is None:
        st = run.status("P1")
        if st.get("running") or len(run.batches("P1")) > before_b:
            seen_running = round(now() - t0, 1)
        time.sleep(0.5)
    try:
        run.wait_heart("P1", before_b)
    except Exception as error:  # noqa: BLE001
        out["waitError"] = str(error)
    batches = new_batches(run, "P1", before_b)
    out.update({"answered": target, "answerStatus": answered.get("status"), "capStateBefore": {
                    "nextAllowedAt": st0.get("nextAllowedAt"), "pending": st0.get("pending")},
                "runningSeenAfterS": seen_running,
                "batchStartAfterAnswerS": round(batches[0]["startEpoch"] - t0, 1) if batches else None,
                "batches": batches, "tasks": task_diff(before_t, run.tasks("P1")),
                "openEscalationsAfter": escalations(run, "P1")})
    return out


def s_f4(run):
    p1 = run.projects["P1"]["id"]
    a, b = Worker(run.api, p1, "f4-a"), Worker(run.api, p1, "f4-b")
    ready = sorted([t for t in run.tasks("P1") if t["status"] == "ready"], key=lambda t: t["order"])
    got = {}

    def take(worker):
        got[worker.name] = worker.next()

    threads = [threading.Thread(target=take, args=(w,)) for w in (a, b)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    ta, tb = got["f4-a"][2], got["f4-b"][2]
    by_id = {t["taskId"]: t for t in run.tasks("P1")}
    out = {"readyBefore": [(t["title"], t["order"]) for t in ready],
           "concurrent": {"a": (ta or {}).get("title"), "b": (tb or {}).get("title"),
                          "distinct": bool(ta and tb and ta["id"] != tb["id"]),
                          "orders": [by_id.get((x or {}).get("id"), {}).get("order") for x in (ta, tb)],
                          "httpS": [got["f4-a"][3], got["f4-b"][3]]}}
    for w, t in ((a, ta), (b, tb)):
        if t:
            w.report(t["id"], sha(run, "P1"))
    sequence = []
    for _ in range(40):
        s, body, task, _ = a.next()
        if not task:
            out["emptyQueue"] = {"status": s, "answer": (body or {}).get("answer")}
            break
        sequence.append((task["title"], by_id.get(task["id"], {}).get("order")))
        a.report(task["id"], sha(run, "P1"))
    s, body, task, _ = b.next()
    out["secondWorkerOnEmpty"] = {"status": s, "answer": (body or {}).get("answer")}
    out["drainSequence"] = sequence
    orders = [o for _, o in sequence if o is not None]
    out["orderRespected"] = orders == sorted(orders)
    return out


def automatic_starts(run, key, horizon=3600):
    cutoff = now() - horizon
    return [b for b in run.batches(key) if iso_epoch(b["at"]) >= cutoff
            and not any(i.get("type") == "message" for i in b.get("inputs", []))]


def s_r6(run):
    p1 = run.projects["P1"]["id"]
    w = Worker(run.api, p1, "r6-burst")
    out = {"autoStartsBefore": len(automatic_starts(run, "P1")), "fillers": []}

    def capped():
        allowed = run.status("P1").get("nextAllowedAt")
        return bool(allowed) and iso_epoch(allowed) > now() + 5

    while not capped() and len(out["fillers"]) < 8:
        if run.spent() > STOP_AT_USD:
            return {**out, "skipped": "rozpočet"}
        r = ask_and_wait(run, "P1", w, f"Drobnost {len(out['fillers']) + 1}: má být tlačítko „Přihlas se“ zarovnané "
                                       "vlevo, nebo na střed?")
        out["fillers"].append({k: r[k] for k in ("answerLatencyS", "answer", "batchStartAfterTicketS")}
                              | {"cost": [x["costUsd"] for x in r["batches"]]})
    out["autoStartsJournaledWhenCapped"] = len(automatic_starts(run, "P1"))
    out["capReached"] = capped()
    before_b = len(run.batches("P1"))
    t0 = now()
    s, ticket, _ = w.ask("Sedmá otázka v hodině: smí mít patička odkaz na Instagram?")
    time.sleep(45)
    st = run.status("P1")
    out["seventh"] = {"ticketId": (ticket or {}).get("ticketId"), "after45s": {
        "newBatches": len(run.batches("P1")) - before_b, "pending": st.get("pending"), "running": st.get("running"),
        "nextAllowedAt": st.get("nextAllowedAt"),
        "delayS": round(iso_epoch(st["nextAllowedAt"]) - now(), 0) if st.get("nextAllowedAt") else None}}
    t1 = now()
    run.api.human("POST", "/api/brain/heart/messages", {"project": p1, "workspace": WS,
                                                       "text": "Kontrola spojení: nic nového neplánuj, jen odpověz "
                                                               "na čekající lístky a skonči done."})
    try:
        run.wait_heart("P1", before_b)
    except Exception as error:  # noqa: BLE001
        out["waitError"] = str(error)
    batches = new_batches(run, "P1", before_b)
    out["humanMessage"] = {"batchStartAfterS": round(batches[0]["startEpoch"] - t1, 1) if batches else None,
                           "batches": batches,
                           "cappedTicketRodeAlong": any(i.get("ticketId") == (ticket or {}).get("ticketId")
                                                        for x in batches for i in x["inputs"])}
    out["sinceSeventhS"] = round(now() - t0, 1)
    return out


# --- X: výzkum a dílna (kontrakt docs/brain-heart.md §3b, §3c; chybějící funkce se zapíše jako "absent") ----

REF_PAGE = """<!doctype html><html lang="cs"><head><meta charset="utf-8"><title>Referenční přihláška</title></head><body>
<main><h1>Přihláška</h1>
<div id="summary" role="status" aria-live="polite"></div>
<form id="f" novalidate>
<label for="name">Jméno</label><input id="name" name="name" aria-invalid="false" aria-describedby="name-err">
<span id="name-err" class="err"></span>
<label for="mail">E-mail</label><input id="mail" name="mail" type="email" aria-invalid="false" aria-describedby="mail-err">
<span id="mail-err" class="err"></span>
<button type="submit">Odeslat</button></form></main>
<script>
document.getElementById('f').addEventListener('submit', function (e) {
  e.preventDefault(); var bad = [];
  [['name', 'Vyplň jméno.'], ['mail', 'Vyplň platný e-mail.']].forEach(function (p) {
    var el = document.getElementById(p[0]), ok = el.value.trim() !== '' && (p[0] !== 'mail' || /@/.test(el.value));
    el.setAttribute('aria-invalid', ok ? 'false' : 'true');
    document.getElementById(p[0] + '-err').textContent = ok ? '' : p[1];
    if (!ok) bad.push(el);
  });
  document.getElementById('summary').textContent = bad.length ? 'Formulář má ' + bad.length + ' chyby.' : 'Odesláno.';
  if (bad.length) bad[0].focus();
});
</script></body></html>"""


def serve_reference():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = REF_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def walk(obj):
    """Všechny slovníky v libovolně zanořené struktuře (tvar stromu trezoru není pevně znám)."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def vault_items(run, key):
    """({id: uzel} fragmentů trezoru, chyba); uzel má `kind` (research / duel / ...)."""
    q = {"project": run.projects[key]["id"], "workspace": WS}
    status, tree, _ = run.api.req("GET", "/api/brief-vault", query=q, human=True)
    if status != 200:
        return {}, f"GET /api/brief-vault -> {status}"
    return {n["id"]: n for n in walk(tree) if isinstance(n.get("id"), str) and n.get("kind")}, None


def research_view(run, key, node, needles):
    q = {"project": run.projects[key]["id"], "workspace": WS, "id": node["id"]}
    status, detail, _ = run.api.req("GET", "/api/brief-vault/fragment", query=q, human=True)
    found = next((d["research"] for d in walk(detail) if isinstance(d.get("research"), dict)), None)
    if found is None:
        found = next((d for d in walk(detail) if "verdict" in d), {})
    evidence = found.get("evidence") or []
    text = json.dumps(evidence, ensure_ascii=False)
    return {"id": node["id"], "title": node.get("title"), "status": node.get("status"), "fragmentHttp": status,
            "verdict": found.get("verdict"), "confidence": found.get("confidence"), "evidenceN": len(evidence),
            "evidenceSources": [str(e.get("source"))[:160] for e in evidence if isinstance(e, dict)][:8],
            "evidenceMentionsRef": any(n in text for n in needles),
            "alternatives": [str(a.get("approach"))[:120] for a in found.get("alternatives") or [] if isinstance(a, dict)],
            "approach": str(found.get("approach"))[:300]}


def duel_view_of(run, key, node):
    q = {"project": run.projects[key]["id"], "workspace": WS, "id": node["id"]}
    status, body, _ = run.api.req("GET", "/api/brief-vault/duel", query=q, human=True)
    if status != 200:
        return {"id": node["id"], "httpStatus": status}
    keep = ("probability", "outcome", "canDecide", "rounds", "onTurn", "decided", "status")
    return {"id": node["id"], **{k: body.get(k) for k in keep if k in body}}


def research_evidence(run, key, before_ids, needles=()):
    """Co srdce po vstupu přidalo do trezoru: fragmenty `research` a `duel` (jen nové proti stavu před)."""
    items, error = vault_items(run, key)
    new = [n for i, n in items.items() if i not in before_ids]
    out = {"vaultError": error, "vaultNewCount": len(new), "newKinds": sorted({str(n.get("kind")) for n in new}),
           "research": [research_view(run, key, n, needles) for n in new if n.get("kind") == "research"],
           "duels": [duel_view_of(run, key, n) for n in new if n.get("kind") == "duel"]}
    out["researchAbsent"] = not out["research"]
    out["duelAbsent"] = not out["duels"]
    return out


def cost_block(batches):
    return {"batches": len(batches), "costUsd": round(sum(b.get("costUsd") or 0 for b in batches), 4),
            "subCostUsd": round(sum(b.get("subCostUsd") or 0 for b in batches), 4),
            "numTurns": sum(b.get("numTurns") or 0 for b in batches),
            "durationS": round(sum(b.get("durationS") or 0 for b in batches), 1),
            "inputTokens": [b.get("inputTokens") for b in batches],
            "heartCommands": [c for b in batches for c in (b.get("transcript") or {}).get("bash", [])],
            "tools": [(b.get("transcript") or {}).get("tools") for b in batches]}


def s_x1(run):
    server, url = serve_reference()
    try:
        port = url.rsplit(":", 1)[1].rstrip("/")
        before_ids = set(vault_items(run, "P1")[0])
        before_b, before_t, t0 = len(run.batches("P1")), run.tasks("P1"), now()
        text = (f"Na přihlášce chci validaci formuláře jako na referenčním webu {url} . Nevím, jak to tam dělají. "
                "Zjisti, co tam funguje, a jestli existuje jiná cesta; pak naplánuj.")
        reply = run.api.human("POST", "/api/brain/heart/messages", {"project": run.projects["P1"]["id"],
                                                                   "workspace": WS, "text": text})
        try:
            run.wait_heart("P1", before_b, timeout=1500)
        except Exception as error:  # noqa: BLE001
            log("wait_heart:", error)
        batches = new_batches(run, "P1", before_b)
        diff = task_diff(before_t, run.tasks("P1"))
        seen = {t["taskId"] for t in before_t}
        created = [t for t in run.tasks("P1") if t["taskId"] not in seen]
        blob = json.dumps(created, ensure_ascii=False).lower()
        return {"refUrl": url, "messageReply": reply, "elapsedS": round(now() - t0, 1),
                **research_evidence(run, "P1", before_ids, (url, f":{port}", "127.0.0.1")),
                "tasks": diff, "taskCreatedN": len(diff["created"]),
                "taskMentions": {w: w in blob for w in ("aria-live", "aria-describedby", "aria-invalid", "focus")},
                "cost": cost_block(batches), "batches": batches}
    finally:
        server.shutdown()


def s_x1b(run):
    p1 = run.projects["P1"]["id"]
    w = Worker(run.api, p1, "x1b-worker")
    _, _, task, _ = w.next()
    if not task:
        run.api.human("POST", "/api/brain/tasks", {"project": p1, "workspace": WS, "order": 0, "title": "SONDA: validace",
                                                   "body": {"do": "Vlastní validace formuláře přihlášky.",
                                                            "files": ["src/App.tsx"]}})
        _, _, task, _ = w.next()
    before_ids = set(vault_items(run, "P1")[0])
    body = {"proposal": "Místo vlastní validace použijme knihovnu react-hook-form + zod, bude to kratší.",
            "reason": "Méně vlastního kódu.", **({"taskId": task["id"]} if task else {})}
    r = ask_and_wait(run, "P1", w, None, kind="change", body=body)
    ev = research_evidence(run, "P1", before_ids)
    return {"task": (task or {}).get("title"), "answer": r["answer"], "answeredBy": r["answeredBy"],
            "latencyS": r["answerLatencyS"], "researchCreated": not ev["researchAbsent"],
            "duelCreated": not ev["duelAbsent"], **ev, "tasks": r["tasks"], "cost": cost_block(r["batches"]),
            "request": r["request"], "batches": r["batches"]}


THEMES = [
    ("barvy", ["Smím v {c} použít barvu #{h} přímo, nebo musí být z tokens.css?",
               "Token --barva-{c} chybí; mám ho přidat do tokens.css pro {c}?"]),
    ("test-h1", ["Test h1 v {c} očekává starý nadpis, úkol předepisuje nový. Mám test přepsat?",
                 "App.test.tsx padá na h1 ({c}); smím ho upravit?"]),
    ("chyby-formulare", ["U pole {c} má chyba mít aria-invalid a text pod polem, nebo shrnutí nahoře?",
                         "Kam dát chybovou hlášku pro {c}: aria-describedby, nebo role=alert?"]),
    ("routing", ["Stránka {c} má být na /{c}, nebo na /prihlaska/{c}? Jak řešit zpět na Domů?",
                 "Mám pro {c} přidat react-router, nebo stačí hash odkaz?"]),
    ("obrazky-alt", ["Obrázek {c} potřebuje alt text; jak popsat ozdobný obrázek?",
                     "Smím u {c} nechat alt prázdný, když je obrázek jen dekorace?"]),
    ("ton-textu", ["Text {c} zní vykáním (Vaše); mám ho přepsat na tykání?",
                   "V textu {c} je „Poslední místa“; smím ponechat, nebo je to nátlak?"]),
]


def s_x2(run):
    p1 = run.projects["P1"]["id"]
    dilna = run.brain("P1") / "dilna"
    w = Worker(run.api, p1, "x2-seed")
    seed_before, ids, t_seed = len(run.batches("P1")), [], now()
    for i in range(66):  # lístek hned zodpovíme jako člověk; odpověď člověka srdce nebudí (ověřit: batchesWokenBySeeding)
        theme, variants = THEMES[i % len(THEMES)]
        q = variants[(i // len(THEMES)) % len(variants)].format(c=f"sekce-{i}", h=f"{(i * 37) % 0xFFFFFF:06x}")
        s, ticket, _ = w.ask(q)
        tid = (ticket or {}).get("ticketId")
        if s == 201 and tid:
            ids.append(tid)
            run.api.req("POST", f"/api/gate/tickets/{tid}/answer", {"answer": {"text": f"Ano ({theme}), dle pravidel."}},
                        query={"project": p1}, human=True)
    seeding = {"ticketsSeeded": len(ids), "seedS": round(now() - t_seed, 1),
               "batchesWokenBySeeding": len(run.batches("P1")) - seed_before}
    try:  # případná dávka probuzená sesazováním musí doběhnout, ať se nepletou do měření
        run.wait_heart("P1", len(run.batches("P1")), need_new=False, timeout=900)
    except Exception as error:  # noqa: BLE001
        seeding["settleError"] = str(error)
    runs_file = dilna / "runs.jsonl"
    runs0 = len(runs_file.read_text("utf-8").splitlines()) if runs_file.exists() else 0
    scripts0 = {p.name for p in (dilna / "scripts").glob("*")} if (dilna / "scripts").exists() else set()
    state0 = run.api.req("GET", "/api/desktop-v3/state", query={"project": p1, "workspace": WS}, human=True)[1] or {}
    rules0 = {r.get("id") for r in walk((state0.get("state") or state0).get("rules")) if r.get("id")}
    before_b, t0 = len(run.batches("P1")), now()
    reply = run.api.human("POST", "/api/brain/heart/messages", {
        "project": p1, "workspace": WS,
        "text": "Projdi všechny lístky pracovníků v projektu, najdi témata, která se opakují, a ke každému navrhni "
                "pravidlo aplikace."})
    try:
        run.wait_heart("P1", before_b, timeout=1800)
    except Exception as error:  # noqa: BLE001
        log("wait_heart:", error)
    batches = new_batches(run, "P1", before_b)
    run_lines = runs_file.read_text("utf-8").splitlines()[runs0:] if runs_file.exists() else []
    scripts = []
    for path in sorted((dilna / "scripts").glob("*.py")) if (dilna / "scripts").exists() else []:
        text = path.read_text("utf-8", "replace")
        m = re.search(r'"""(.*?)(?:\n|""")', text, re.S)
        scripts.append({"name": path.name, "doc": (m.group(1).strip() if m else "")[:160], "lines": len(text.splitlines()),
                        "newInThisScenario": path.name not in scripts0})
    data_files = sorted(p.name for p in (dilna / "data").glob("*.json")) if (dilna / "data").exists() else []
    state1 = run.api.req("GET", "/api/desktop-v3/state", query={"project": p1, "workspace": WS}, human=True)[1] or {}
    new_rules = [{"id": r.get("id"), "by": r.get("by"), "text": str(r.get("text"))[:200]}
                 for r in walk((state1.get("state") or state1).get("rules")) if r.get("id") and r["id"] not in rules0]
    return {"seeding": seeding, "elapsedS": round(now() - t0, 1), "messageReply": reply,
            "dilnaRunsAdded": len(run_lines), "dilnaRunsRaw": run_lines[:12], "dilnaPresent": dilna.exists(),
            "scriptsCreated": scripts, "dataFiles": data_files, "rulesProposed": new_rules,
            "rulesByAgent": sum(1 for r in new_rules if r["by"] == "agent"), "cost": cost_block(batches),
            "batches": batches, "absent": {"dilna": not dilna.exists(), "runs": not run_lines,
                                           "scripts": not scripts, "rules": not new_rules}}


SCENARIOS = {"F1": s_f1, "WALL": s_wall, "F2": s_f2, "F3": s_f3, "F5": s_f5, "R1": s_r1, "R2": s_r2, "R3": s_r3,
             "R4": s_r4, "R5": s_r5, "F4": s_f4, "R6": s_r6, "X1": s_x1, "X1b": s_x1b, "X2": s_x2}


def x_comparison(run):
    """Kompaktní srovnání X1 / X1b / X2: co vzniklo (výzkum, duel, dílna, pravidla) za jakou cenu."""
    done = run.results["runs"][run.name]["scenarios"]
    out = {}
    for name in ("X1", "X1b", "X2"):
        e = done.get(name)
        if not e:
            continue
        cost = e.get("cost") or {}
        out[name] = {"error": e.get("error"), "wallS": e.get("wallS"), "costUsd": cost.get("costUsd"),
                     "subCostUsd": cost.get("subCostUsd"), "numTurns": cost.get("numTurns"),
                     "research": len(e.get("research") or []), "duels": len(e.get("duels") or []),
                     "duelProb": [d.get("probability") for d in e.get("duels") or []],
                     "tasksCreated": e.get("taskCreatedN"), "dilnaRuns": e.get("dilnaRunsAdded"),
                     "scripts": [s["name"] for s in e.get("scriptsCreated") or []], "dataFiles": e.get("dataFiles"),
                     "rulesProposed": len(e.get("rulesProposed") or []), "absent": e.get("absent")}
    return out


# --- skutečný pracovník (P2, souběžně) ------------------------------------------------------------------

def stream_stats(raw):
    events = []
    for line in raw.read_text("utf-8", "replace").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    tools, gate_calls = {}, []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for block in (e.get("message") or {}).get("content") or []:
            if block.get("type") == "tool_use":
                tools[block["name"]] = tools.get(block["name"], 0) + 1
                cmd = str((block.get("input") or {}).get("command", ""))
                if "opora_gate.py" in cmd:
                    gate_calls.append(cmd.split("opora_gate.py", 1)[1][:120])
    return {"numTurns": result.get("num_turns"), "costUsd": result.get("total_cost_usd"),
            "isError": result.get("is_error"), "durationS": round((result.get("duration_ms") or 0) / 1000, 1),
            "denials": [{"tool": d.get("tool_name"), "input": json.dumps(d.get("tool_input"), ensure_ascii=False)[:160]}
                        for d in result.get("permission_denials") or []],
            "tools": tools, "gateCalls": gate_calls, "final": (result.get("result") or "")[:1200]}


def real_worker(run):
    out = {}
    try:
        ws = run.dir / "ws-r"
        if not (ws / ".git").exists():
            make_real_ws(ws)
        run.project("P2", ws, "Sonda-real")
        out["plan"] = plan_from_intent(run, "P2")
        run.save("REAL", out)
        if run.spent() > STOP_AT_USD - 1.5:
            out["skipped"] = "rozpočet před pracovníkem"
            return
        gate_py = str(heart_arm.install_gate_client(run.dir, "REAL")).replace("\\", "/")
        footer = sessions.FOOTER + ("\nUdělej nejvýš 2 úkoly z fronty: po druhém hlášení (report) skonči, i když fronta "
                                    "není prázdná.")
        prompt = heart_arm.worker_prompt(gate_py, run.projects["P2"]["id"], "REAL", footer)
        cmd = run_eval.agent_command(prompt, "sonnet", "B")
        i = cmd.index("--disallowedTools")
        cmd[i:i] = [f"Bash(python {gate_py}:*)"]
        recipe = run.dir / "recipe-c.md"
        recipe.write_text(sessions.c_recipe().replace(
            "`npm run build && npm test` pusť jednou na ucelený kus práce (`&&`: test jen po prošlém buildu)",
            "`npm run build`, a když projde, `npm test` (dva samostatné příkazy) pusť jednou na ucelený kus práce"),
            encoding="utf-8")
        cmd += ["--append-system-prompt-file", str(recipe)]
        before_b, before_t = len(run.batches("P2")), run.tasks("P2")
        raw = run.dir / "real-worker.jsonl"
        t0 = now()
        code, dt = run_eval.run_agent(cmd, ws, run_eval.child_env({"OPORA_BASE_URL": run.api.base}), raw, 45 * 60)
        stats = stream_stats(raw)
        with run.lock:
            run.worker_usd += float(stats["costUsd"] or 0)
        try:
            run.wait_heart("P2", len(run.batches("P2")), need_new=False, timeout=900)
        except Exception as error:  # noqa: BLE001
            out["waitError"] = str(error)
        with sqlite3.connect(f"file:{run.db('P2')}?mode=ro", uri=True, timeout=10) as con:
            rows = con.execute("SELECT t.kind, t.body, t.status, t.answer, t.answered_by, t.created_at, t.answered_at "
                               "FROM gate_tickets t JOIN gate_sessions s ON s.id=t.session_id WHERE s.role='worker' "
                               "AND t.kind IN ('ask','change') ORDER BY t.seq").fetchall()
        checks = {}
        for name, args in (("build", ["run", "build"]), ("test", ["test"])):
            r = subprocess.run([shutil.which("npm") or "npm", *args], cwd=ws, capture_output=True, text=True,
                               shell=os.name == "nt", timeout=600)
            checks[name] = {"exit": r.returncode, "tail": (r.stdout + r.stderr)[-400:]}
        out["worker"] = {"exit": code, "wallS": round(dt, 1), **stats,
                         "tickets": [{"kind": k, "body": json.loads(b), "status": s, "answer": a, "by": by,
                                      "created": c, "answered": at} for k, b, s, a, by, c, at in rows],
                         "commits": git(ws, "log", "--oneline", "-10").splitlines(),
                         "tasks": task_diff(before_t, run.tasks("P2")),
                         "taskStatuses": [(t["title"], t["status"], t["attempts"]) for t in run.tasks("P2")],
                         "heartBatchesDuring": new_batches(run, "P2", before_b), "finalChecks": checks}
    except Exception as error:  # noqa: BLE001
        out["error"] = f"{type(error).__name__}: {error}"
        log("REAL selhal:", out["error"])
    finally:
        run.save("REAL", out)
        log("REAL hotovo")


# --- hlavní běh -----------------------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--run", default="r1")
    p.add_argument("--scenarios", default=",".join([n for n in ORDER if not n.startswith("X")] + ["REAL"]),
                   help="X1, X1b, X2 (výzkum, paralelní cesta, dílna) a O1 (srdce ↔ orchestrátor) jsou opt-in")
    p.add_argument("--variant", choices=("cards", "tasks"), default="cards",
                   help="O1: cards = karty `plan` + pruh executions, tasks = fronta brány `task` + next/report")
    p.add_argument("--phase", choices=("auto", "all", "one"), default="auto",
                   help="O1: nápověda srdci v záměru (vše najednou / jen fáze 1 a pak reagovat / nic)")
    p.add_argument("--rounds", type=int, default=4, help="O1: nejvýš kol orchestrátora")
    p.add_argument("--git-poll", type=float, default=30.0, help="O1: perioda hlídače gitu srdce v s (produkt 300)")
    p.add_argument("--heart-wait", type=float, default=900.0, help="O1: strop čekání na reakci srdce po kole (s)")
    p.add_argument("--round-timeout", type=float, default=1800.0, help="O1: tvrdý strop jednoho kola orchestrátora (s)")
    p.add_argument("--hint-schema", action="store_true",
                   help="O1 cards: přidá do záměru tvar dávky `plan` (srdce ho v promptu nemá)")
    p.add_argument("--table", action="store_true", help="jen vypíše srovnávací tabulku O1 z results.json")
    args = p.parse_args(argv)
    if args.table:
        print(orch.table(json.loads(RESULTS.read_text("utf-8")) if RESULTS.exists() else {}))
        return 0
    wanted = [s.strip().upper() for s in args.scenarios.split(",") if s.strip()]
    wanted = [{"X1B": "X1b"}.get(s, s) for s in wanted]
    run_dir = ROOT / args.run
    if "opora-data" in str(run_dir).lower():
        sys.exit("zakázaná datová složka")
    run_dir.mkdir(parents=True, exist_ok=True)
    ws = run_dir / "ws-s"
    if not (ws / ".git").exists():
        make_scripted_ws(ws)  # --repo serveru; scénáře O ho jen předají, projekt nad ním nezakládají
    only_o = all(s.startswith("O") for s in wanted)
    proc, api = start_server(run_dir, args.git_poll if any(s.startswith("O") for s in wanted) else None)
    run = Run(args.run, api, run_dir)
    real = None
    try:
        if only_o:  # scénáře O mají vlastní lokální projekt nad repem aplikace; P1 se nezakládá
            for name in wanted:
                key = f"{name}-{args.variant}-{args.phase}" + ("-schema" if args.hint_schema else "")
                log(f"{key} start")
                t0 = now()
                evidence = orch.s_o1(run, args, sys.modules[__name__])
                evidence["wallS"] = evidence.get("wallS") or round(now() - t0, 1)
                run.save(key, evidence)
                log(f"{key} hotovo za {evidence['wallS']} s; útrata O {(evidence.get('cost') or {}).get('totalUsd')} USD")
            print(orch.table(run.results))
            return 0
        run.project("P1", ws, "Sonda-skript")
        st = run.status("P1")
        if not st.get("enabled"):
            raise RuntimeError(f"supervisor neběží: {st}")
        if "REAL" in wanted:
            real = threading.Thread(target=real_worker, args=(run,), daemon=True)
            real.start()
        if "F1" not in wanted:  # bez plánu srdce: úkoly napíše člověk (srdce nebudí)
            for i in range(1, 7):
                api.human("POST", "/api/brain/tasks", {"project": run.projects["P1"]["id"], "workspace": WS,
                                                       "order": i, "title": f"Ruční úkol {i}",
                                                       "body": {"do": f"Krok {i}", "files": ["src/App.tsx"]}})
        for name in ORDER:
            if name not in wanted:
                continue
            if name != "WALL" and run.spent() > STOP_AT_USD:
                run.save(name, {"skipped": f"rozpočet {run.spent()} USD"})
                continue
            log(f"{name} start (útrata {run.spent()} USD)")
            t0 = now()
            try:
                evidence = SCENARIOS[name](run)
            except Exception as error:  # noqa: BLE001
                evidence = {"error": f"{type(error).__name__}: {error}"}
            evidence["wallS"] = round(now() - t0, 1)
            run.save(name, evidence)
            log(f"{name} hotovo za {evidence['wallS']} s (útrata {run.spent()} USD)")
        if real:
            real.join(timeout=60 * 60)
    finally:
        run.save("_final", {"spentUsd": run.spent(), "heartUsd": run.heart_usd(), "workerUsd": run.worker_usd,
                            "finished": time.strftime("%Y-%m-%dT%H:%M:%S"), "xComparison": x_comparison(run)})
        grade.kill_tree(proc)
        grade.kill_leftovers(run_dir)
        log("server ukončen; útrata", run.spent(), "USD")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
