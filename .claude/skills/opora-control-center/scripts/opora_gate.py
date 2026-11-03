"""Klient brány mozku pro pracovníky (docs/brain-gate.md §4, ticket práce docs/navrhy/2026-11-03-novy-zaklad.md §3.3),
jen standardní knihovna.

    opora_gate.py session --project P --workspace W --name N [--office O] [--floor F]
    opora_gate.py request                                  # držený ticket, jinak nejstarší vydaný (nebere ho)
    opora_gate.py claim --ticket tk_… [--execution ex_…]   # vezme ticket (issued → claimed)
    opora_gate.py feedback --ticket tk_… --kind question "Smím změnit sdílený styl?"
    opora_gate.py deliver --ticket tk_… --summary "…" [--sha S]
    opora_gate.py release --ticket tk_…                    # vzatý ticket zpět do fronty (claimed → issued)
    opora_gate.py ask "Smím upravit X?"
    opora_gate.py inbox [--wait 20]
    opora_gate.py tell "Záměr člověka doslova"   # relé záměru srdci (docs/brain-heart-orchestrator.md §8)

Adresa serveru je v OPORA_BASE_URL (výchozí http://127.0.0.1:8740). Token relace se uloží do
`<cwd>/.opora/gate.json` a `.opora/` se připíše do `.gitignore` v cwd, když tam chybí; na výstup token nejde.
`inbox` si pamatuje kurzor (`after`), takže každá odpověď přijde jednou. Výstup je vždy jeden JSON na stdout.
Kódy: 0 ok, 1 chyba klienta (chybí relace, server neběží), 2 server odmítl (4xx/5xx s `code` a `hint`).
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

DEFAULT_BASE = "http://127.0.0.1:8740"
HEADER = "X-Opora-Gate-Token"
STATE = Path(".opora") / "gate.json"
TIMEOUT = 60
EXIT_CLIENT, EXIT_REFUSED = 1, 2
_OPENER = build_opener(ProxyHandler({}))  # loopback bez systémové proxy


class GateFailure(Exception):
    """Neúspěch, který skript vypíše jako JSON a ukončí nenulovým kódem."""

    def __init__(self, exit_code, payload):
        super().__init__(payload.get("error", ""))
        self.exit_code, self.payload = exit_code, payload


def base_url():
    return os.environ.get("OPORA_BASE_URL", DEFAULT_BASE).rstrip("/")


def call(method, path, body=None, token=None, query=None, name=None):
    """Jedno volání brány; vrací tělo odpovědi, odmítnutí serveru je `GateFailure` s jeho `code` a `hint`."""
    base = base_url()
    url = base + path + ("?" + urlencode(query) if query else "")
    headers = {"Accept": "application/json", "Origin": base}
    if name:
        headers["X-Opora-Actor"] = "agent; name=" + name
    if token:
        headers[HEADER] = token
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json"
    try:
        with _OPENER.open(Request(url, data=data, headers=headers, method=method), timeout=TIMEOUT) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as error:
        try:
            detail = json.loads(error.read() or b"{}")
        except ValueError:
            detail = {}
        detail = detail if isinstance(detail, dict) else {"detail": detail}
        raise GateFailure(EXIT_REFUSED, {"ok": False, "status": error.code, "error": detail.get("error", str(error)),
                                         "code": detail.get("code"), "hint": detail.get("hint")}) from None
    except URLError as error:
        raise GateFailure(EXIT_CLIENT, {"ok": False, "error": f"Server {base} neodpovídá: {error.reason}",
                                        "hint": "Spusťte OPORU (uv run opora) nebo nastavte OPORA_BASE_URL."}) from None


def load_state(cwd):
    path = Path(cwd) / STATE
    if not path.is_file():
        raise GateFailure(EXIT_CLIENT, {"ok": False, "error": "Chybí relace brány v .opora/gate.json.",
                                        "hint": "Založte ji: opora_gate.py session --project P --workspace W --name N"})
    return json.loads(path.read_text("utf-8"))


def save_state(cwd, state):
    path = Path(cwd) / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
    ignore = Path(cwd) / ".gitignore"
    lines = ignore.read_text("utf-8").splitlines() if ignore.is_file() else []
    if not any(line.strip() in (".opora", ".opora/", "/.opora", "/.opora/") for line in lines):
        prefix = "\n" if lines and not ignore.read_text("utf-8").endswith("\n") else ""
        with ignore.open("a", encoding="utf-8") as handle:
            handle.write(prefix + ".opora/\n")


def request(state, kind, body):
    return call("POST", "/api/gate/requests", {"kind": kind, "body": body}, state["token"], name=state.get("name"))


def run(args, cwd):
    if args.command == "session":
        worker = {"name": args.name} | {key: value for key, value in (("office", args.office), ("floor", args.floor))
                                        if value}
        issued = call("POST", "/api/gate/sessions", {"project": args.project, "workspace": args.workspace,
                                                     "worker": worker}, name=args.name)
        save_state(cwd, {"project": args.project, "workspace": args.workspace, "name": args.name,
                         "sessionId": issued["sessionId"], "token": issued["token"],
                         "expiresAt": issued["expiresAt"], "after": 0})
        return {"sessionId": issued["sessionId"], "expiresAt": issued["expiresAt"], "stored": str(STATE)}
    state = load_state(cwd)
    if args.command == "request":
        return request(state, "ticket.request", {})
    if args.command == "claim":
        return request(state, "ticket.claim", {"ticketId": args.ticket}
                       | ({"executionId": args.execution} if args.execution else {}))
    if args.command == "feedback":
        return request(state, "ticket.feedback", {"ticketId": args.ticket, "kind": args.kind, "text": args.text})
    if args.command == "deliver":
        return request(state, "ticket.deliver", {"ticketId": args.ticket, "summary": args.summary}
                       | ({"sha": args.sha} if args.sha else {}))
    if args.command == "release":
        return request(state, "ticket.release", {"ticketId": args.ticket})
    if args.command == "ask":
        return request(state, "ask", {"question": args.text})
    if args.command == "change":
        return request(state, "change", {"proposal": args.text, "reason": args.reason})
    if args.command == "tell":
        return call("POST", "/api/brain/heart/messages", {"project": state["project"], "workspace": state["workspace"],
                                                         "text": args.text}, state["token"], name=state.get("name"))
    box = call("GET", "/api/gate/inbox", token=state["token"], name=state.get("name"),
               query={"after": state.get("after", 0), "wait": args.wait})
    save_state(cwd, {**state, "after": box["last"]})
    return box


def parser():
    root = argparse.ArgumentParser(prog="opora_gate.py", description="Klient brány mozku OPORY pro pracovníky.")
    sub = root.add_subparsers(dest="command", required=True)
    session = sub.add_parser("session", help="založí relaci a uloží token do .opora/gate.json")
    session.add_argument("--project", required=True)
    session.add_argument("--workspace", required=True)
    session.add_argument("--name", required=True)
    session.add_argument("--office")
    session.add_argument("--floor")
    sub.add_parser("request", help="ticket, který relace drží, jinak nejstarší vydaný (nebere ho); nic = null")
    claim = sub.add_parser("claim", help="vezme vydaný ticket (issued → claimed)")
    claim.add_argument("--ticket", required=True)
    claim.add_argument("--execution", help="běžící exekuce karty ticketu; stav pak posouvá i exekuce")
    feedback = sub.add_parser("feedback", help="zpětná vazba k drženému ticketu; otázka čeká na odpověď srdce")
    feedback.add_argument("--ticket", required=True)
    feedback.add_argument("--kind", required=True, choices=("bug", "idea", "improvement", "question"))
    feedback.add_argument("text")
    deliver = sub.add_parser("deliver", help="odevzdá držený ticket se shrnutím (a sha)")
    deliver.add_argument("--ticket", required=True)
    deliver.add_argument("--summary", required=True)
    deliver.add_argument("--sha", help="výstup git rev-parse HEAD")
    release = sub.add_parser("release", help="vrátí vzatý ticket do fronty (claimed → issued)")
    release.add_argument("--ticket", required=True)
    ask = sub.add_parser("ask", help="otázka; odpověď přijde do schránky")
    ask.add_argument("text")
    change = sub.add_parser("change", help="žádost srdci o změnu plánu; odpověď přijde do schránky")
    change.add_argument("text", help="navržená změna plánu")
    change.add_argument("--reason", required=True, help="proč (např. záměr člověka)")
    inbox = sub.add_parser("inbox", help="nové odpovědi na lístky této relace")
    inbox.add_argument("--wait", type=int, default=0, help="long-poll 0..30 s")
    tell = sub.add_parser("tell", help="předá srdci záměr člověka doslova (zpráva s via = jméno relace)")
    tell.add_argument("text")
    return root


def main(argv=None, cwd=None):
    args = parser().parse_args(argv)
    try:
        result = run(args, cwd or os.getcwd())
    except GateFailure as failure:
        print(json.dumps(failure.payload, ensure_ascii=False))
        return failure.exit_code
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # konzole Windows by jinak češtinu nevypsala
    sys.exit(main())
