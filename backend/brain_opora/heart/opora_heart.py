"""Jediný nástroj srdce (docs/brain-heart.md §4), jen standardní knihovna. Jedno volání = jeden záměr.

    python opora_heart.py snapshot
    python opora_heart.py task --title T --do D [--why W] [--file F]… [--done-when C]… [--dont-touch P[@kdo]]…
                               [--rule R]… [--intent I] [--node N] [--order N] [--commit C]
    python opora_heart.py answer --ticket ID --text T
    python opora_heart.py cancel --task ID
    python opora_heart.py escalate --text T
    python opora_heart.py done --summary S

Adresa, token srdce, projekt a pracovní prostor jsou v prostředí (OPORA_BASE_URL, OPORA_HEART_TOKEN,
OPORA_PROJECT, OPORA_WORKSPACE); token se nikam nezapisuje. `done` zapíše shrnutí do `last_done.json` v cwd.
Výstup je jeden JSON na stdout (`snapshot` vypíše text); chyba vypíše `code` a `hint` a skončí nenulovým kódem.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

HEADER = "X-Opora-Gate-Token"
TIMEOUT = 60
LAST_DONE = "last_done.json"
_OPENER = build_opener(ProxyHandler({}))  # loopback bez systémové proxy


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


def call(method, path, body=None, query=None):
    """Jedno volání OPORY s tokenem srdce; odmítnutí serveru je `Failure` s jeho `code` a `hint`."""
    base = env("OPORA_BASE_URL").rstrip("/")
    url = base + path + ("?" + urlencode(query) if query else "")
    headers = {"Accept": "application/json", "Origin": base, "X-Opora-Actor": "agent; name=heart",
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
    if args.node:
        payload["nodeId"] = args.node
    if args.order is not None:
        payload["order"] = args.order
    return payload


def run(args):
    project = env("OPORA_PROJECT")
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
    summary = {"summary": args.summary, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
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
    answer = commands.add_parser("answer")
    answer.add_argument("--ticket", required=True)
    answer.add_argument("--text", required=True)
    commands.add_parser("cancel").add_argument("--task", required=True)
    commands.add_parser("escalate").add_argument("--text", required=True)
    commands.add_parser("done").add_argument("--summary", required=True)
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
