"""Jediný nástroj srdce (docs/brain-heart.md §4), jen standardní knihovna. Jedno volání = jeden záměr.

    python opora_heart.py snapshot
    python opora_heart.py task --title T --do D [--why W] [--file F]… [--done-when C]… [--dont-touch P[@kdo]]…
                               [--rule R]… [--intent I] [--node N] [--order N] [--commit C] [--model M]
    python opora_heart.py answer --ticket ID --text T
    python opora_heart.py cancel --task ID
    python opora_heart.py escalate --text T
    python opora_heart.py decide --text T [--node N] [--pin]
    python opora_heart.py rule --text T
    python opora_heart.py done --summary S
    python opora_heart.py ctx tasks|tickets|journal|messages|rules|decisions|tree
    python opora_heart.py run SCRIPT [ARG…]
    python opora_heart.py research --question Q --title T [--target URL|cesta]… [--fragment F] [--deep]
    python opora_heart.py duel --subject F --a TEXT --b TEXT

Adresa, token srdce, projekt a pracovní prostor jsou v prostředí (OPORA_BASE_URL, OPORA_HEART_TOKEN,
OPORA_PROJECT, OPORA_WORKSPACE); token se nikam nezapisuje. `done` zapíše shrnutí do `last_done.json` v cwd.
Dílna (§3b, cwd = `brain/`): `ctx` zapíše data do `dilna/data/<name>.json` a vypíše jen cestu, počet a velikost;
`run` spustí `dilna/scripts/<SCRIPT>.py` (`python -I`, cwd `dilna/`, 120 s) bez tokenu srdce a klíčů API
ve vlastní skupině procesů (po vypršení zemře celý strom i s pod-voláními `claude`) a zapíše řádek do `dilna/runs.jsonl`.
`research` a `duel` (§3c) jsou v `opora_research.py` vedle nástroje (výzkumník s REA, duel s pod-voláními Haiku).
Výstup je jeden JSON na stdout (`snapshot` vypíše text); chyba vypíše `code` a `hint` a skončí nenulovým kódem.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

HEADER = "X-Opora-Gate-Token"
TIMEOUT = 60
LAST_DONE = "last_done.json"
_OPENER = build_opener(ProxyHandler({}))  # loopback bez systémové proxy
DILNA = Path("dilna")
CONTEXTS = ("tasks", "tickets", "journal", "messages", "rules", "decisions", "tree")
SCRIPT = re.compile(r"[A-Za-z0-9_-]+\Z")
RUN_TIMEOUT, STDOUT_LIMIT, STDERR_LIMIT = 120, 8000, 2000
# Prostředí skriptu: bez tokenu srdce a adresy (skript OPORU nemění) a bez klíčů API (kopie command.STRIPPED,
# nástroj je jen stdlib).
SCRIPT_STRIPPED = ("OPORA_HEART_TOKEN", "OPORA_BASE_URL", "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "CELERIS_API_KEY")
# `-I` nedá cwd do sys.path: zavaděč ho přidá, aby skript našel `rlm.py`, a spustí skript jako __main__.
BOOT = ("import os,runpy,sys;sys.path.insert(0,os.getcwd());sys.argv=sys.argv[1:];"
        "runpy.run_path(sys.argv[0],run_name='__main__')")


class Failure(Exception):
    def __init__(self, payload):
        super().__init__(payload.get("error", ""))
        self.payload = payload


def env(name):
    value = os.environ.get(name, "")
    if not value:
        raise Failure({"error": f"Chybí {name}.", "code": "heart_env_missing",
                       "hint": "Nástroj spouští jen dávka srdce, která prostředí nastaví."})
    return value


def call(method, path, body=None, query=None, actor="heart"):
    """Jedno volání OPORY s tokenem srdce; odmítnutí serveru je `Failure` s jeho `code` a `hint`.
    `actor` = jméno agenta v X-Opora-Actor (duel: strany a soudci jsou různí aktéři, token zůstává srdce)."""
    base = env("OPORA_BASE_URL").rstrip("/")
    url = base + path + ("?" + urlencode(query) if query else "")
    headers = {"Accept": "application/json", "Origin": base, "X-Opora-Actor": f"agent; name={actor}",
               HEADER: env("OPORA_HEART_TOKEN")}
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json"
    try:
        with _OPENER.open(Request(url, data=data, headers=headers, method=method), timeout=TIMEOUT) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as error:
        try:
            payload = json.loads(error.read() or b"{}")
        except ValueError:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        raise Failure({"error": payload.get("error") or f"HTTP {error.code}", "status": error.code,
                       "code": payload.get("code") or f"http_{error.code}",
                       "hint": payload.get("hint") or "Zkontrolujte argumenty příkazu."}) from None
    except (URLError, OSError) as error:
        raise Failure({"error": f"OPORA neodpovídá: {error}", "code": "server_unreachable",
                       "hint": "Server OPORY neběží nebo je na jiné adrese než OPORA_BASE_URL."}) from None


def scope():
    return {"project": env("OPORA_PROJECT"), "workspace": env("OPORA_WORKSPACE")}


def held(value):
    path, _, holder = value.partition("@")
    return {"path": path.strip(), "heldBy": holder.strip() or "jiný úkol"}


def task_payload(args):
    """Tělo `POST /api/brain/tasks` v pevném tvaru úkolu (docs/brain-gate.md §6)."""
    body = {"do": args.do, "why": args.why or "", "files": args.file, "doneWhen": args.done_when,
            "dontTouch": [held(item) for item in args.dont_touch], "commit": args.commit or ""}
    context = {key: value for key, value in (("rules", args.rule), ("intent", args.intent)) if value}
    payload = {**scope(), "title": args.title, "body": {**body, "context": context}}
    if args.model:
        payload["body"]["model"] = args.model
    if args.node:
        payload["nodeId"] = args.node
    if args.order is not None:
        payload["order"] = args.order
    return payload


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def item_payload(item):
    """Přidání položky paměti (`POST /api/desktop-v3/decision|rule`, CAS: `expected` null)."""
    return {**scope(), "id": item["id"], "op": "add", "expected": None, "item": item}


def decision_payload(args):
    """Rozhodnutí srdce v paměti prostoru (DECISION_KEYS); `by: agent`, cesta prázdná."""
    return item_payload({"id": "hd_" + uuid.uuid4().hex, "text": args.text, "pinned": args.pin, "path": "",
                         "nodeId": args.node or "", "createdAt": now(), "by": "agent"})


def rule_payload(args):
    """Pravidlo celé aplikace; `by: agent` (návrh do schválení člověkem) doplní server."""
    return item_payload({"id": "hr_" + uuid.uuid4().hex, "text": args.text, "kind": "must", "scope": "project",
                         "target": ""})


def load_context(name):
    """`ctx <name>`: data z OPORY do `dilna/data/<name>.json`; vrací jen cestu, počet položek a velikost."""
    items = call("GET", "/api/brain/heart/context", query={**scope(), "name": name})["items"]
    path = DILNA / "data" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(items, ensure_ascii=False).encode("utf-8")
    path.write_bytes(raw)
    return {"path": path.as_posix(), "items": len(items), "bytes": len(raw)}


def _cut(text, limit):
    return text if len(text) <= limit else text[:limit] + f"\n… (zkráceno, celkem {len(text)} znaků)"


def _sub_usage(log):
    calls = cost = 0
    try:
        lines = log.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0, 0.0
    for line in lines:
        try:
            cost += float(json.loads(line).get("costUsd") or 0)
            calls += 1
        except (ValueError, AttributeError, TypeError):
            continue
    return calls, round(cost, 6)


def _group():
    """Skript ve vlastní skupině procesů, ať po vypršení jde zabít celý strom (§3b)."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def kill_tree(process):
    """Zabije proces i všechny jeho potomky (pod-volání `claude` z `rlm.py`); na Windows `taskkill /T`."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=30, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    process.kill()  # pojistka, kdyby strom už nebyl celý


def _execute(argv, cwd, env, timeout=None, input_text=None):
    """`(exit, stdout, stderr, timedOut)`; po `timeout` (výchozí `RUN_TIMEOUT`) zabije strom a dočte, co proces stihl vypsat.
    `input_text` jde na stdin (zadání výzkumníka a pod-volání duelu)."""
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               stdin=subprocess.DEVNULL if input_text is None else subprocess.PIPE,
                               encoding="utf-8", errors="replace", **_group())
    try:
        out, err = process.communicate(input=input_text, timeout=RUN_TIMEOUT if timeout is None else timeout)
        return process.returncode, out, err, False
    except subprocess.TimeoutExpired:
        kill_tree(process)
        try:
            out, err = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:  # roura drží ještě někdo jiný; výstup oželíme
            out, err = "", ""
        return None, out, err, True


def log_run(script, script_args, exit_code, ms, calls, cost):
    """Řádek do `dilna/runs.jsonl` (běh skriptu, výzkum, duel); dávka z něj sečte `subCostUsd` do deníku."""
    entry = {"at": now(), "script": script, "args": list(script_args), "exit": exit_code, "ms": ms,
             "subCalls": calls, "subCostUsd": round(cost, 6)}
    DILNA.mkdir(parents=True, exist_ok=True)
    with (DILNA / "runs.jsonl").open("a", encoding="utf-8") as runs:
        runs.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def research_module():
    """`opora_research.py`: kopie vedle nástroje v `brain/`, v testech modul balíčku."""
    try:
        import opora_research
    except ImportError:
        from backend.brain_opora.heart import opora_research
    return opora_research


def run_script(script, script_args):
    """`run <script>`: skript dílny v odděleném prostředí; výsledek a řádek do `dilna/runs.jsonl`."""
    if not SCRIPT.match(script):
        raise Failure({"error": f"Neplatné jméno skriptu {script!r}.", "code": "script_name",
                       "hint": "Jméno bez přípony a cesty, jen písmena, číslice, _ a -; skript leží v dilna/scripts/."})
    dilna = DILNA.resolve()
    if not (dilna / "scripts" / f"{script}.py").is_file():
        raise Failure({"error": f"Skript {script}.py neexistuje.", "code": "script_missing",
                       "hint": "Napiš ho nástrojem Write do dilna/scripts/<jméno>.py (první řádek docstringu = co dělá)."})
    log = dilna / f".sub-{uuid.uuid4().hex}.jsonl"
    env = {key: value for key, value in os.environ.items() if key not in SCRIPT_STRIPPED}
    env.update({"OPORA_RLM_LOG": str(log), "PYTHONIOENCODING": "utf-8"})
    env.pop("OPORA_RLM_DEPTH", None)
    started = time.time()
    exit_code, out, err, timed_out = _execute([sys.executable, "-I", "-c", BOOT, f"scripts/{script}.py", *script_args],
                                              str(dilna), env)
    ms = int((time.time() - started) * 1000)
    calls, cost = _sub_usage(log)
    log.unlink(missing_ok=True)
    entry = log_run(script, script_args, exit_code, ms, calls, cost)
    result = {**entry, "stdout": _cut(out or "", STDOUT_LIMIT)}
    if err:
        result["stderr"] = (err or "")[-STDERR_LIMIT:]
    if timed_out:
        result["timedOut"] = True
    return result


def run(args):
    project = env("OPORA_PROJECT")
    if args.command == "ctx":
        return load_context(args.name)
    if args.command == "run":
        return run_script(args.script, args.script_args)
    if args.command in ("research", "duel"):
        return getattr(research_module(), args.command)(args, sys.modules[__name__])
    if args.command == "snapshot":
        return call("GET", "/api/brain/heart/snapshot", query=scope())["snapshot"]
    if args.command == "task":
        task = call("POST", "/api/brain/tasks", task_payload(args))
        return {key: task[key] for key in ("taskId", "title", "status", "order")}
    if args.command == "answer":
        ticket = call("POST", f"/api/gate/tickets/{quote(args.ticket, safe='')}/answer",
                      {"answer": {"text": args.text}}, {"project": project})
        return {key: ticket[key] for key in ("ticketId", "status", "answeredBy")}
    if args.command == "cancel":
        task = call("POST", f"/api/brain/tasks/{quote(args.task, safe='')}/cancel", {}, {"project": project})
        return {key: task[key] for key in ("taskId", "status")}
    if args.command == "escalate":
        return call("POST", "/api/brain/heart/escalate", {**scope(), "text": args.text})
    if args.command in ("decide", "rule"):
        path, payload = (("/api/desktop-v3/decision", decision_payload(args)) if args.command == "decide"
                         else ("/api/desktop-v3/rule", rule_payload(args)))
        item = call("POST", path, payload)["item"]
        return {key: item.get(key) for key in ("id", "text", "by")}
    summary = {"summary": args.summary, "at": now()}
    Path(LAST_DONE).write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return {"done": True}


def parser():
    root = argparse.ArgumentParser(prog="opora_heart.py", description="Nástroj srdce OPORY.")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("snapshot")
    task = commands.add_parser("task")
    task.add_argument("--title", required=True)
    task.add_argument("--do", required=True)
    task.add_argument("--why")
    for flag in ("--file", "--done-when", "--dont-touch", "--rule"):
        task.add_argument(flag, action="append", default=[])
    for flag in ("--intent", "--node", "--commit"):
        task.add_argument(flag)
    task.add_argument("--order", type=int)
    task.add_argument("--model", choices=("sonnet", "opus", "haiku", "fable"))
    answer = commands.add_parser("answer")
    answer.add_argument("--ticket", required=True)
    answer.add_argument("--text", required=True)
    commands.add_parser("cancel").add_argument("--task", required=True)
    commands.add_parser("escalate").add_argument("--text", required=True)
    decide = commands.add_parser("decide")
    decide.add_argument("--text", required=True)
    decide.add_argument("--node")
    decide.add_argument("--pin", action="store_true")
    commands.add_parser("rule").add_argument("--text", required=True)
    commands.add_parser("done").add_argument("--summary", required=True)
    commands.add_parser("ctx").add_argument("name", choices=CONTEXTS)
    script = commands.add_parser("run")
    script.add_argument("script")
    script.add_argument("script_args", nargs=argparse.REMAINDER)
    research = commands.add_parser("research")
    research.add_argument("--question", required=True)
    research.add_argument("--title", required=True)
    research.add_argument("--target", action="append", default=[])
    research.add_argument("--fragment")
    research.add_argument("--deep", action="store_true")
    duel = commands.add_parser("duel")
    for flag in ("--subject", "--a", "--b"):
        duel.add_argument(flag, required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except Failure as failure:
        print(json.dumps(failure.payload, ensure_ascii=False))
        return 1
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
