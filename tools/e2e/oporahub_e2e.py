"""Live end-to-end run of the whole OporaHub loop on an isolated Canvas + agent-office pair.

Never touches the user's Canvas (8740), office (4600) or their data dirs: every run keeps its logs,
snapshots and report under ``--out`` and its Canvas data dir, office home and floor checkout in a
short temp folder (``state.json`` names it). GitHub writes go only to the sandbox repository given
by ``--repo`` (a private throwaway repo you own), and the only merges are of that repo's PRs.

    uv run python tools/e2e/oporahub_e2e.py start  --out <dir> --office <built agent-office checkout> [--upkeep]
    uv run python tools/e2e/oporahub_e2e.py run    --out <dir> [--upkeep] [--only 2a-claim,...] [--keep-going]
    uv run python tools/e2e/oporahub_e2e.py stop   --out <dir>      # kills everything it started

The sandbox is a tiny Node project, created once with
``gh repo create <owner>/oporahub-e2e-sandbox --private --source <seed> --push``: ``package.json``
with ``"test": "node --test \"test/*.test.js\""`` (a bare directory argument fails on Windows) and a
``build`` script, ``src/math.js``, ``test/math.test.js`` and ``.github/pull_request_template.md``
(Testing / Risk / Revert plan). Workers run Claude Code with ``--permission-mode auto`` and the
script answers the one-time folder-trust prompt of a fresh floor through the office's WebSocket
(``office_term.mjs``). Running ``start`` again after ``stop``-ing only the office keeps the floor's
``opora.json`` (its runs), so the office can be restarted mid-run, e.g. with ``--upkeep``.

``start`` launches Canvas (``--canvas-port``, default 8791) with ``OPORA_REVIEW_JOBS=1`` and a small
review config, connects the sandbox repo as a git project, creates a domain, a work workspace and
one card with a tiny spec, routes its pipeline and accepts the baseline as a human (``opora_ui``
session cookie, the same proof the UI uses). Then it launches agent-office (``--office-port``,
default 4691) on a fresh clone of the sandbox with the autopilot on, AUTO_PR on, self-checks,
review workers (PARALLEL=1, a small PER_HOUR) and a cheap model.

``run`` then waits for each stage of the loop and stores every ``agent-state`` snapshot as JSON,
the timings and the failures in ``<out>/report.json``. Nothing here merges anything outside the
sandbox repository.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = "Pletor/oporahub-e2e-sandbox"
CARD_ID = "e2ecard1"
DOMAIN_ID = "e2eapp"
SPEC = {
    "goal": "Add an exported function `multiply(a, b)` to src/math.js that returns a * b, with a node:test test in test/math.test.js.",
    "non_goals": "Do not change add(), package.json, the build script or anything outside src/math.js and test/math.test.js.",
    "acceptance": "`npm test` and `npm run build` pass; the new test covers multiply(3, 4) === 12.",
}
REVIEW_CONFIG = """enabled = true
[jobs]
finders = 2
voters = 1
required_votes = 1
max_rounds = 2
[risk]
medium_lines = 200
high_lines = 1000
medium_files = 10
high_files = 40
sensitive = [".github/workflows/**", "package.json"]
[approvals]
low = 1
medium = 1
high = 2
sensitive_minimum = 1
agent_account_ids = []
[security]
enabled = true
min_tier = "medium"
paths = [".github/workflows/**", "**/auth/**", "package.json"]
[self_checks]
required = ["tests", "build"]
[merge_queue]
enabled = true
required_checks = []
base_max_age_seconds = 900
observe_interval_seconds = 30
[template]
sections = ["Testing", "Risk", "Revert plan"]
"""


# ---------------------------------------------------------------- small helpers

class Http:
    def __init__(self, base, ui_secret):
        self.base = base.rstrip("/")
        self.ui_secret = ui_secret

    def call(self, method, path, body=None, params=None, actor="human", headers=None):
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = json.dumps(body).encode() if body is not None else None
        h = {"Accept": "application/json", "Origin": self.base}
        if data is not None:
            h["Content-Type"] = "application/json"
        if actor == "human":
            h["Cookie"] = "opora_ui=" + self.ui_secret
        elif actor:
            h["X-Opora-Actor"] = "agent; name=" + actor
        h.update(headers or {})
        request = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                return error.code, json.loads(raw)
            except ValueError:
                return error.code, raw.decode(errors="replace")

    def ok(self, method, path, body=None, params=None, actor="human"):
        status, value = self.call(method, path, body, params, actor)
        if status >= 300:
            raise RuntimeError(f"{method} {path} -> {status}: {json.dumps(value)[:800]}")
        return value

    def get(self, path, **params):
        return self.ok("GET", path, params=params)


def run(cmd, cwd=None, check=True, env=None, timeout=600):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=env, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"{cmd!r} failed ({result.returncode}): {result.stderr[-1500:]}{result.stdout[-500:]}")
    return result.stdout.strip()


def wait_for(label, probe, timeout, interval=5.0):
    """Polls `probe()` until it returns a truthy value; returns (value, seconds)."""
    started = time.monotonic()
    last_error = None
    while time.monotonic() - started < timeout:
        try:
            value = probe()
            if value:
                return value, round(time.monotonic() - started, 1)
        except Exception as error:  # noqa: BLE001 - a probe failure is retried until the deadline
            last_error = error
        time.sleep(interval)
    raise TimeoutError(f"{label}: no result in {timeout}s" + (f" (last error: {last_error})" if last_error else ""))


def free(port):
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def kill_tree(pid):
    if not pid:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            pass


class Run:
    """The run's state on disk (`<out>/state.json`), snapshots and the report."""

    def __init__(self, out):
        self.out = Path(out).resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "snapshots").mkdir(exist_ok=True)
        self.state_path = self.out / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.report_path = self.out / "report.json"
        self.report = json.loads(self.report_path.read_text()) if self.report_path.exists() else {"steps": []}
        # Temp data (Canvas data dir, office home, floor clone) lives on a short path: Windows git
        # aborts a clone whose $GIT_DIR is too long, and Canvas nests worktrees deep inside its data.
        work = self.state.get("work") or str(Path(tempfile.gettempdir()) / ("oe2e-" + secrets.token_hex(3)))
        self.state["work"] = work
        self.work = Path(work)
        self.work.mkdir(parents=True, exist_ok=True)

    def save(self):
        self.state_path.write_text(json.dumps(self.state, indent=2))
        self.report_path.write_text(json.dumps(self.report, indent=2))

    def http(self):
        return Http(f"http://127.0.0.1:{self.state['canvasPort']}", self.state["uiSecret"])

    def snapshot(self, label):
        h = self.http()
        scope = {"project": self.state["project"], "workspace": self.state["workspace"]}
        snap = {"label": label, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "agentState": h.get("/api/oporahub/agent-state", **scope)}
        for key, path in (("reviewJobs", "/api/oporahub/review-jobs"), ("gates", "/api/oporahub/review-jobs/gates")):
            status, value = h.call("GET", path, params=scope)
            snap[key] = value if status == 200 else {"status": status, "body": value}
        index = len(list((self.out / "snapshots").glob("*.json"))) + 1
        (self.out / "snapshots" / f"{index:02d}-{label}.json").write_text(json.dumps(snap, indent=2))
        return snap

    def step(self, name, fn):
        started = time.monotonic()
        entry = {"step": name, "status": "running"}
        self.report["steps"] = [s for s in self.report["steps"] if s["step"] != name] + [entry]
        print(f"[e2e] {name} ...", flush=True)
        try:
            entry["detail"] = fn()
            entry["status"] = "pass"
        except Exception as error:  # noqa: BLE001 - every failure is recorded, the run goes on where it can
            entry["status"] = "fail"
            entry["error"] = f"{type(error).__name__}: {error}"
        entry["seconds"] = round(time.monotonic() - started, 1)
        print(f"[e2e] {name}: {entry['status']} ({entry['seconds']}s) {entry.get('error', '')}", flush=True)
        self.save()
        return entry


def stage(agent_state, stage_id):
    return next((s for s in agent_state["stages"] if s["id"] == stage_id), {})


def gh_token():
    return run(["gh", "auth", "token"])


# ---------------------------------------------------------------- start

def start_canvas(r: Run, args):
    if not free(args.canvas_port):
        raise SystemExit(f"port {args.canvas_port} is taken; pick another --canvas-port")
    data = r.work / "canvas-data"
    data.mkdir(exist_ok=True)
    config = r.out / "review-jobs.toml"
    config.write_text(REVIEW_CONFIG)
    secret = secrets.token_urlsafe(32)
    env = {**os.environ, "OPORA_UI_SECRET": secret, "OPORA_REVIEW_JOBS": "1", "OPORA_REVIEW_JOBS_CONFIG": str(config),
           "OPORA_MAP_REFRESH_WORKER": "0", "OPORA_EXECUTION_PR_DISCOVERY_SECONDS": "30",
           "OPORA_AUTO_REBASE_SECONDS": "3", "OPORA_GITHUB_TOKEN": gh_token(), "PYTHONUNBUFFERED": "1"}
    for key in ("OPORA_ACCESS_TOKEN", "OPORA_MIRROR_URL", "OPORA_OPENVIKING_URL"):
        env.pop(key, None)
    log = open(r.out / "canvas.log", "ab")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(["uv", "run", "--project", str(ROOT), "python", "-m", "tools.opora", "--port", str(args.canvas_port),
                                "--data", str(data), "--no-open", "--no-build"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                               creationflags=flags, start_new_session=os.name != "nt")
    r.state.update(canvasPid=process.pid, canvasPort=args.canvas_port, uiSecret=secret, repo=args.repo)
    r.save()
    _, seconds = wait_for("canvas health", lambda: r.http().call("GET", "/api/bootstrap")[0] == 200, 180, 2)
    return {"pid": process.pid, "port": args.canvas_port, "secondsToHealthy": seconds}


def setup_project(r: Run, args):
    h = r.http()
    url = f"https://github.com/{r.state['repo']}"
    before = {p["id"] for p in h.get("/api/bootstrap").get("projects", [])}
    h.ok("POST", "/api/connect", {"url": url, "approved": True})

    def project():
        return next((p for p in h.get("/api/bootstrap").get("projects", []) if p["id"] not in before), None)

    item, clone_seconds = wait_for("clone of the sandbox", project, 240, 3)
    pid = item["id"]
    architecture = h.get("/api/project-architecture", project=pid)
    domain = {"id": DOMAIN_ID, "parentId": None, "kind": "sector", "name": "Sandbox app", "purpose": "E2E sandbox", "x": 0, "y": 0,
              "site": {"kind": "application", "environments": [{"name": "Produkce", "host": "sandbox.example.invalid"}]}}
    h.ok("POST", "/api/project-architecture", {"project": pid, "workspace": "main", "expectedRevision": architecture.get("revision", 0),
                                                "graph": {"nodes": [domain], "edges": []}})
    workspace = h.ok("POST", "/api/workspaces", {"project": pid, "nodeId": DOMAIN_ID, "actor": "E2E"})["id"]
    scope = {"project": pid, "workspace": workspace}
    view = h.get("/api/view", **scope)
    card = {"id": CARD_ID, "parentId": DOMAIN_ID, "kind": "node", "name": "[task] multiply()", "purpose": "Add multiply with a test",
            "x": 40, "y": 40}
    graph = {"nodes": [*view["graph"]["nodes"], card], "edges": view["graph"]["edges"]}
    h.ok("POST", "/api/graph", {**scope, "graph": graph, "digest": view["digest"]})
    spec = h.get("/api/node-spec", **scope, node=CARD_ID)
    h.ok("POST", "/api/node-spec", {**scope, "node": CARD_ID, "expected_revision": spec["revision"], "fields": SPEC})
    state = h.get("/api/desktop-v3/state", **scope)
    h.ok("POST", "/api/desktop-v3/pipeline", {**scope, "nodeId": CARD_ID, "expectedRevision": state["revision"], "op": "route",
                                               "profile": "custom", "stages": [{"kind": "work", "lens": "", "title": "Implementation", "brief": "Implement the spec with its test."}],
                                               "reason": "E2E: one implementation session, the office reviews the PR."})
    context = h.get("/api/oporahub/changesets/context", **scope)
    baseline = h.ok("POST", "/api/oporahub/baselines", {**scope, "subject": "E2E baseline", "expectedAcceptedHead": None,
                                                         "expectedGraphDigest": context["graphDigest"],
                                                         "expectedSpecificationsVersion": context["specificationsVersion"]})
    r.state.update(project=pid, workspace=workspace, baseline=baseline["id"])
    r.save()
    r.snapshot("01-accepted")
    return {"project": pid, "workspace": workspace, "baseline": baseline["id"], "cloneSeconds": clone_seconds}


def start_office(r: Run, args):
    if not free(args.office_port):
        raise SystemExit(f"port {args.office_port} is taken; pick another --office-port")
    home, floor = r.work / "office-home", r.work / "floor"
    home.mkdir(exist_ok=True)
    if not floor.exists():
        run(["git", "clone", f"https://github.com/{r.state['repo']}.git", str(floor)])
        run(["git", "config", "user.name", "OporaHub E2E"], cwd=floor)
        run(["git", "config", "user.email", "e2e@example.invalid"], cwd=floor)
    data = floor / ".agent-office"
    data.mkdir(exist_ok=True)
    if not (data / "opora.json").exists():  # a restart keeps the bridge's runs and choices
        (data / "opora.json").write_text(json.dumps({"runs": [], "autopilot": True, "maxRuns": 1, "autopilotBy": "E2E",
                                                  "linkedTo": r.state["project"], "workspace": r.state["workspace"],
                                                  "focus": [], "handOut": False}, indent=2))
    office = Path(args.office).resolve()
    env = {**os.environ, "AGENT_OFFICE_HOME": str(home), "AGENT_OFFICE_OPORA_URL": f"http://127.0.0.1:{r.state['canvasPort']}",
           "AGENT_OFFICE_OPORA_AUTO_PR": "on", "AGENT_OFFICE_OPORA_SELF_CHECKS": json.dumps({"tests": "npm test", "build": "npm run build"}),
           "AGENT_OFFICE_OPORA_SELF_CHECK_TIMEOUT_MIN": "5", "AGENT_OFFICE_OPORA_REVIEWS": "on",
           "AGENT_OFFICE_OPORA_REVIEW_PARALLEL": "1", "AGENT_OFFICE_OPORA_REVIEW_PER_HOUR": "6",
           "AGENT_OFFICE_OPORA_REVIEW_TIMEOUT_MIN": "8", "AGENT_OFFICE_OPORA_REVIEW_MODEL": args.model,
           "AGENT_OFFICE_OPORA_UPKEEP": "on" if args.upkeep else "off", "AGENT_OFFICE_OPORA_UPKEEP_INTERVAL_MIN": "1",
           "AGENT_OFFICE_OPORA_CHECK_COMMAND": "npm test", "AGENT_OFFICE_OPORA_RESOLVE_MODEL": args.model,
           "AGENT_OFFICE_OPORA_RESOLVE_PER_HOUR": "2", "AGENT_OFFICE_MAX_WORKERS": "1"}
    for key in ("AGENT_OFFICE_OPORA_DIR", "AGENT_OFFICE_OPORA_CONTEXT_VERSION", "PORT"):
        env.pop(key, None)
    log = open(r.out / "office.log", "ab")
    agent_args = f"--model {args.model} --permission-mode auto --allowedTools " + " ".join(
        f'"{tool}"' for tool in ("Bash(git:*)", "Bash(npm:*)", "Bash(node:*)", "PowerShell(*)", "Edit", "Write", "Read", "Glob", "Grep"))
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    login_key = secrets.token_hex(12)  # throwaway per-run office login, generated at runtime
    r.state.update(officePassword=login_key, office=str(office))
    process = subprocess.Popen(["node", str(office / "bin" / "agent-office.js"), str(floor), "--port", str(args.office_port),
                                "--password", login_key, "--no-open", "--agent-args", agent_args],
                               cwd=office, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                               start_new_session=os.name != "nt")
    r.state.update(officePid=process.pid, officePort=args.office_port, floor=str(floor))
    r.save()

    def up():
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{args.office_port}/", timeout=5) as response:
                return response.status < 500
        except urllib.error.HTTPError as error:
            return error.code < 500
    _, seconds = wait_for("office up", up, 120, 2)
    return {"pid": process.pid, "port": args.office_port, "secondsToUp": seconds}


# ---------------------------------------------------------------- the loop

def executions(r):
    h = r.http()
    return h.get("/api/oporahub/executions", project=r.state["project"], workspace=r.state["workspace"]).get("executions", [])


def unblock_trust(r: Run):
    """A fresh temp floor isn't a folder the user's Claude Code trusts yet, so each new worker opens on
    the one-time folder-trust prompt; answer it like a person would (down to "Yes", Enter)."""
    done = set(r.state.get("trusted", []))
    for f in (Path(r.state["floor"]) / ".agent-office" / "scrollback").glob("*.ansi"):
        worker = f.stem
        if worker in done:
            continue
        tail = f.read_bytes()[-4000:].decode("utf-8", errors="replace").replace(" ", "")
        if "Itrustthisfolder" in tail or "trustthisfolder" in tail:
            run(["node", str(Path(__file__).with_name("office_term.mjs")), f"http://127.0.0.1:{r.state['officePort']}",
                 r.state["officePassword"], worker, json.dumps(["\x1b[B", "\r"])], cwd=r.state["office"], check=False)
            done.add(worker)
            r.state["trusted"] = sorted(done)
            r.save()


def step_claim(r: Run, timeout):
    item, seconds = wait_for("office claims the card", lambda: next(iter(executions(r)), None), timeout)
    r.state["execution"] = item["executionId"] if "executionId" in item else item["id"]
    r.save()
    r.snapshot("02-claimed")
    return {"execution": r.state["execution"], "secondsToClaim": seconds}


def step_result(r: Run, timeout):
    h = r.http()
    scope = {"project": r.state["project"], "workspace": r.state["workspace"]}

    def results():
        unblock_trust(r)
        value = h.get(f"/api/oporahub/executions/{r.state['execution']}/results", **scope)
        items = value.get("results", [])
        return items or None
    items, seconds = wait_for("worker result", results, timeout, 10)
    r.snapshot("03-result")
    return {"secondsToResult": seconds, "summary": str(items[0].get("result", {}).get("summary", ""))[:300]}


def step_pull_request(r: Run, timeout):
    h = r.http()
    scope = {"project": r.state["project"], "workspace": r.state["workspace"]}

    def link():
        status, value = h.call("GET", f"/api/oporahub/executions/{r.state['execution']}/pull-request", params=scope)
        return value if status == 200 else None
    value, seconds = wait_for("PR link on Canvas", link, timeout, 10)
    r.state.update(pr=value["number"], headSha=value["headSha"])
    r.save()
    body = run(["gh", "pr", "view", str(value["number"]), "-R", r.state["repo"], "--json", "body,headRefName,url"])
    pr = json.loads(body)
    trailers = {k: (f"{k}: " in pr["body"]) for k in ("Opora-Execution", "Opora-Revision", "Opora-Card")}
    r.snapshot("04-pr-linked")
    return {"number": value["number"], "url": pr["url"], "branch": pr["headRefName"], "trailers": trailers,
            "source": value.get("source"), "enrollment": value.get("enrollment"), "secondsToLink": seconds}


def step_review(r: Run, timeout):
    h = r.http()
    scope = {"project": r.state["project"], "workspace": r.state["workspace"]}

    def gate():
        items = h.get("/api/oporahub/review-jobs/gates", **scope).get("items", [])
        g = next((g for g in items if g.get("number") == r.state["pr"]), None)
        if not g:
            return None
        checks = (g.get("mergeReadiness") or {}).get("selfChecks", {}).get("status")
        jobs = h.get("/api/oporahub/review-jobs", **scope).get("jobs", [])
        code = [j for j in jobs if j.get("kind", "code") == "code" and j.get("headSha") == g["headSha"]]
        return g if checks in ("ok", "failed") and code and code[-1].get("phase") == "completed" else None
    g, seconds = wait_for("self-checks + completed review round", gate, timeout, 15)
    r.snapshot("05-reviewed")

    def posted():
        reviews = json.loads(run(["gh", "api", f"repos/{r.state['repo']}/pulls/{r.state['pr']}/reviews"]))
        return [x for x in reviews if "opora-review-job:" in (x.get("body") or "")] or None
    reviews, post_seconds = wait_for("COMMENT review on GitHub", posted, 180, 10)
    return {"gate": g.get("reviewGate"), "selfChecks": g.get("mergeReadiness", {}).get("selfChecks"),
            "secondsToReviewed": seconds, "githubReviews": [{"state": x["state"], "user": x["user"]["login"]} for x in reviews],
            "secondsToPosted": post_seconds}


def step_gate(r: Run):
    h = r.http()
    scope = {"project": r.state["project"], "workspace": r.state["workspace"]}
    attempt = subprocess.run(["gh", "pr", "review", str(r.state["pr"]), "-R", r.state["repo"], "--approve", "-b",
                              f"Opora-Plan: {r.state['project']}/{r.state['workspace']}@{r.state['baseline']}"],
                             capture_output=True, text=True)
    approval = {"exit": attempt.returncode, "stderr": attempt.stderr.strip()[-400:]}
    context = h.get("/api/oporahub/github-evidence", **scope)
    status, evidence = h.call("POST", "/api/oporahub/github-evidence", {**scope, "expectedAcceptedHead": context.get("acceptedHead"),
                                                                     "prNumber": r.state["pr"]})
    time.sleep(5)
    snap = r.snapshot("06-gate")
    g = next((g for g in snap["gates"].get("items", []) if g.get("number") == r.state["pr"]), {})
    return {"humanApproval": approval, "evidenceImport": {"status": status, "complete": (evidence or {}).get("complete") if isinstance(evidence, dict) else None},
            "gate": g.get("reviewGate"), "reviewStage": stage(snap["agentState"], "review")}


def step_merge(r: Run, timeout):
    merge = subprocess.run(["gh", "pr", "merge", str(r.state["pr"]), "-R", r.state["repo"], "--squash", "--delete-branch"],
                           capture_output=True, text=True)
    if merge.returncode:
        raise RuntimeError(f"gh pr merge failed: {merge.stderr.strip()[-400:]}")
    h = r.http()
    scope = {"project": r.state["project"], "workspace": r.state["workspace"]}

    def merged():
        value = h.get(f"/api/oporahub/executions/{r.state['execution']}/pull-request", **scope)
        return value if value.get("state") == "merged" else None
    value, seconds = wait_for("execution.merged", merged, timeout, 10)
    snap = r.snapshot("07-merged")
    events = [e.get("kind") or e.get("type") for e in value.get("events", [])]
    decisions = [d["kind"] for d in snap["agentState"]["decisions"]]
    actions = [a["verb"] for a in snap["agentState"]["actions"]]
    return {"secondsToMerged": seconds, "mergeSha": value.get("mergeSha"), "events": events,
            "awaitingHumanClose": value.get("awaitingHumanClose"), "planWrittenBack": value.get("planWrittenBack"),
            "planWritebackStage": stage(snap["agentState"], "plan_writeback"), "decisions": decisions,
            "closeCardAction": "close_card" in actions}


def step_auto_rebase(r: Run, timeout):
    """Two proposals on the same accepted head touching different fields; accepting one makes the
    other stale, and the server's auto-rebase loop must re-propose it on the new head."""
    h = r.http()
    scope = {"project": r.state["project"], "workspace": r.state["workspace"]}
    context = h.get("/api/oporahub/changesets/context", **scope)
    doc = next(d for d in context["documents"] if d["nodeId"] == CARD_ID)
    accepted = next(d for d in context["acceptedDocuments"] if d["nodeId"] == CARD_ID) if "acceptedDocuments" in context else doc

    def propose(field, text, actor):
        fields = {**accepted["fields"], field: text}
        return h.ok("POST", "/api/oporahub/changesets", {**scope, "subject": f"E2E change {field}", "parentRevision": context["acceptedHead"],
                                                         "expectedGraphDigest": context["graphDigest"],
                                                         "changes": [{"nodeId": CARD_ID, "expectedRevision": doc["revision"], "fields": fields}]},
                    actor=actor)
    stale = propose("non_goals", accepted["fields"]["non_goals"] + " Also leave README.md alone.", "e2e-planner")
    other = propose("acceptance", accepted["fields"]["acceptance"] + " CI stays green.", "e2e-planner")
    h.ok("POST", f"/api/oporahub/changesets/{other['id']}/accept", {**scope, "expectedAcceptedHead": context["acceptedHead"],
                                                                    "by": {"kind": "human"}})

    def rebased():
        items = h.get("/api/oporahub/changesets", **scope)["items"]
        return next((p for p in items if p.get("supersedes") == stale["id"]), None)
    value, seconds = wait_for("auto-rebase of the stale proposal", rebased, timeout, 3)
    snap = r.snapshot("08-auto-rebased")
    return {"stale": stale["id"], "rebased": value["id"], "by": value.get("by"), "secondsToRebase": seconds,
            "proposalStage": stage(snap["agentState"], "proposal")}


def step_upkeep_conflict(r: Run, timeout):
    """An Opora-branch PR that conflicts with a later main commit; PR upkeep must rebase it."""
    floor = Path(r.state["floor"])
    tmp = r.work / "conflict-clone"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    run(["git", "clone", f"https://github.com/{r.state['repo']}.git", str(tmp)])
    for k, v in (("user.name", "OporaHub E2E"), ("user.email", "e2e@example.invalid")):
        run(["git", "config", k, v], cwd=tmp)
    branch = f"opora/e2econflict1/e2e-{int(time.time())}"
    run(["git", "checkout", "-b", branch], cwd=tmp)
    readme = tmp / "README.md"
    readme.write_text(readme.read_text() + "\nUpkeep line from the PR branch.\n")
    run(["git", "commit", "-am", "docs: PR side of the upkeep conflict"], cwd=tmp)
    run(["git", "push", "-u", "origin", branch], cwd=tmp)
    body = "Upkeep conflict probe.\n\n## Testing\nnpm test\n\n## Risk\nNone, docs only.\n\n## Revert plan\nClose the PR.\n"
    url = run(["gh", "pr", "create", "-R", r.state["repo"], "--head", branch, "--base", "main", "--title", "E2E upkeep conflict", "--body", body])
    run(["git", "checkout", "main"], cwd=tmp)
    readme.write_text(readme.read_text() + "\nUpkeep line from main.\n")
    run(["git", "commit", "-am", "docs: main side of the upkeep conflict"], cwd=tmp)
    run(["git", "push", "origin", "main"], cwd=tmp)
    number = url.rstrip("/").rsplit("/", 1)[-1]
    head = run(["git", "rev-parse", branch], cwd=tmp)
    r.state["conflictPr"] = number
    r.save()

    def moved():
        pr = json.loads(run(["gh", "pr", "view", number, "-R", r.state["repo"], "--json", "headRefOid,comments,mergeable"]))
        comments = [c["body"][:300] for c in pr["comments"]]
        if pr["headRefOid"] != head or comments:
            return {"newHead": pr["headRefOid"], "rebased": pr["headRefOid"] != head, "comments": comments, "mergeable": pr["mergeable"]}
        return None
    value, seconds = wait_for("PR upkeep acts on the conflicting PR", moved, timeout, 20)
    events = floor / ".agent-office" / "opora-upkeep" / "events.jsonl"
    return {**value, "pr": url, "secondsToUpkeep": seconds,
            "events": events.read_text(encoding="utf-8").splitlines()[-8:] if events.exists() else []}


# ---------------------------------------------------------------- commands

def cmd_start(args):
    r = Run(args.out)
    r.report.setdefault("startedAt", time.strftime("%Y-%m-%dT%H:%M:%S"))
    if not r.state.get("canvasPid"):
        r.step("0a-start-canvas", lambda: start_canvas(r, args))
    if not r.state.get("project"):
        r.step("1-create-and-accept", lambda: setup_project(r, args))
    if r.state.get("project") and not r.state.get("officePid"):
        r.step("0b-start-office", lambda: start_office(r, args))


def cmd_run(args):
    r = Run(args.out)
    t = args.timeout
    steps = [
        ("2a-claim", lambda: step_claim(r, t)),
        ("2b-result", lambda: step_result(r, 2 * t)),
        ("3-pr-and-link", lambda: step_pull_request(r, t)),
        ("4-self-checks-and-review", lambda: step_review(r, 2 * t)),
        ("5-gate-and-human", lambda: step_gate(r)),
        ("6-merge-and-writeback", lambda: step_merge(r, t)),
        ("7a-auto-rebase", lambda: step_auto_rebase(r, 120)),
    ]
    if args.upkeep:
        steps.append(("7b-upkeep-conflict", lambda: step_upkeep_conflict(r, t)))
    only = set(args.only.split(",")) if args.only else None
    for name, fn in steps:
        if only and name not in only:
            continue
        entry = r.step(name, fn)
        if entry["status"] == "fail" and not args.keep_going:
            break
    r.report["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    r.save()


def cmd_stop(args):
    r = Run(args.out)
    for key in ("officePid", "canvasPid"):
        kill_tree(r.state.get(key))
        r.state[key] = None
    r.save()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["start", "run", "stop"])
    parser.add_argument("--out", required=True, help="run directory: logs, snapshots, report, temp data")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="sandbox GitHub repo owner/name (never a real project)")
    parser.add_argument("--office", default=str(ROOT.parent / "agent-office"), help="agent-office checkout (built)")
    parser.add_argument("--canvas-port", type=int, default=8791)
    parser.add_argument("--office-port", type=int, default=4691)
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per waiting step (some steps get 2x)")
    parser.add_argument("--upkeep", action="store_true", help="also turn PR upkeep on and probe a conflicting PR")
    parser.add_argument("--only", help="comma-separated step names for `run`")
    parser.add_argument("--keep-going", action="store_true")
    args = parser.parse_args(argv)
    if args.canvas_port in (8740,) or args.office_port in (4600,):
        raise SystemExit("refusing the user's own ports 8740/4600")
    {"start": cmd_start, "run": cmd_run, "stop": cmd_stop}[args.command](args)


if __name__ == "__main__":
    main()
