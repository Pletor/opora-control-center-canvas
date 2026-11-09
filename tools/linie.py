"""Agent v terminálu nad úkolem Linie (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §4), jen standardní knihovna.

    uv run python tools/linie.py task [--ticket tk_…] [--project P --workspace W]
    uv run python tools/linie.py report [--check "npm test=green"]… [--sha HEAD] [--allow-unmarked]
                                        [--try "screen=pletor&part=linie"] [--step "Klikni na … → uvidíš …"]…
    uv run python tools/linie.py trace [--mark OP-…]
    uv run python tools/linie.py board [--mine] [--all]   # text přehledu jako obrazovka Linie (GET /board.txt)
    uv run python tools/linie.py status | preview | merge | defer | resume | block --reason "…"

Server je v OPORA_BASE_URL (výchozí http://127.0.0.1:8740), identita OPORA_AGENT_NAME → `X-Opora-Actor`, token brány
z `<cwd>/.opora/gate.json`. Aktivní ticket se pamatuje v `<cwd>/.opora/linie.json`. Skript nikdy neslučuje ani
nepushuje; Git jen čte. Kódy: 0 ok, 1 server odmítl (409 …), 2 jiný kontext nebo nejasný úkol, 3 evidence nedostupná.
"""
import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

DEFAULT_BASE = "http://127.0.0.1:8740"
API = "/api/pletor/linie"
STATE = Path(".opora") / "linie.json"
GATE = Path(".opora") / "gate.json"
SESSION = Path(".opora") / "session.json"  # zapisuje hook SessionStart (tools/opora_session_hook.py)
TIMEOUT = 30
EXIT_REFUSED, EXIT_CONTEXT, EXIT_DOWN = 1, 2, 3
_open = build_opener(ProxyHandler({})).open  # loopback bez systémové proxy; testy ho podvrhnou


class Stop(Exception):
    def __init__(self, code, text):  # konec s textem a kódem (odmítnutí, jiný kontext, nedostupná evidence)
        super().__init__(text)
        self.code, self.text = code, text


def git(cwd, *args):
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8",
                          check=False)
    return done.stdout.strip() if done.returncode == 0 else ""


def same_path(a, b):
    return bool(a and b) and os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def read_json(path):
    return json.loads(path.read_text("utf-8")) if path.is_file() else {}


SCOPE = {}  # project/workspace z voleb nebo .opora/linie.json; všechny routy Linie je chtějí


def call(cwd, method, path, body=None, query=None, text=False):
    query = {**{k: v for k, v in SCOPE.items() if v}, **(query or {})}
    base = os.environ.get("OPORA_BASE_URL", DEFAULT_BASE).rstrip("/")
    headers = {"Accept": "text/plain" if text else "application/json", "Origin": base}
    gate = read_json(Path(cwd) / GATE)
    name = os.environ.get("OPORA_AGENT_NAME") or gate.get("name")
    headers |= {"X-Opora-Actor": "agent; name=" + name} if name else {}
    headers |= {"X-Opora-Gate-Token": gate["token"]} if gate.get("token") else {}
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body, ensure_ascii=False).encode("utf-8"), "application/json"
    url = base + API + path + ("?" + urlencode(query) if query else "")
    try:
        with _open(Request(url, data=data, headers=headers, method=method), timeout=TIMEOUT) as response:
            raw = response.read()
            return raw.decode("utf-8") if text else json.loads(raw) if raw else {}
    except HTTPError as error:
        try:
            detail = json.loads(error.read() or b"{}")
        except ValueError:
            detail = {}
        detail = detail if isinstance(detail, dict) else {"detail": detail}
        message = detail.get("message") or detail.get("error") or detail.get("detail") or str(error)
        code = ", " + detail["code"] if detail.get("code") else ""
        raise Stop(EXIT_REFUSED, f"Server odmítl ({error.code}{code}): {message}") from None
    except (URLError, TimeoutError, ConnectionError) as error:
        reason = getattr(error, "reason", error)
        raise Stop(EXIT_DOWN, f"Evidence nedostupná, kód zachován, blokace: {base} neodpovídá ({reason}).") from None


def scope(cwd, args):  # projekt a workspace: volby, pak .opora/linie.json, pak OPORA_PROJECT / OPORA_WORKSPACE
    saved = read_json(Path(cwd) / STATE)
    project = args.project or saved.get("project") or os.environ.get("OPORA_PROJECT")
    workspace = args.workspace or saved.get("workspace") or os.environ.get("OPORA_WORKSPACE")
    SCOPE.update(project=project, workspace=workspace)
    return project, workspace


def find_ticket(cwd, args):
    ticket_id = args.ticket or read_json(Path(cwd) / STATE).get("ticketId")
    if ticket_id:
        return ticket_id
    project, workspace = scope(cwd, args)
    if not (project and workspace):
        raise Stop(EXIT_CONTEXT, "Neznám úkol: zadej --ticket, nebo --project a --workspace (OPORA_PROJECT/…).")
    branch = git(cwd, "branch", "--show-current")
    board = call(cwd, "GET", "/board", query={"project": project, "workspace": workspace})
    mine = [ball for ball in board.get("balls", []) if branch and ball.get("branch") == branch]
    if len(mine) != 1:
        listed = "\n".join(f"  {ball.get('ticketId')}  {ball.get('branch')}  {ball.get('stateLabel') or ball.get('state')}"
                           for ball in (mine or board.get("balls", [])))
        raise Stop(EXIT_CONTEXT, f"Na větvi {branch or '(žádná)'} je {'víc úkolů' if mine else 'žádný úkol'}; "
                                 f"zadej --ticket.\n{listed}".rstrip())
    return mine[0]["ticketId"]


def remember(cwd, ticket_id, args):
    project, workspace = scope(cwd, args)
    path = Path(cwd) / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ticketId": ticket_id, "project": project, "workspace": workspace},
                               ensure_ascii=False, indent=2), "utf-8")
    exclude = Path(cwd) / git(cwd, "rev-parse", "--git-path", "info/exclude")  # lokální, necommituje se
    known = exclude.read_text("utf-8") if exclude.is_file() else ""
    if ".opora/" not in known:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(known + "\n.opora/\n", "utf-8")


def task(cwd, args):
    ticket_id = find_ticket(cwd, args)
    found = call(cwd, "GET", f"/work/{quote(ticket_id)}")
    work = found.get("work") or {}
    top, branch = git(cwd, "rev-parse", "--show-toplevel"), git(cwd, "branch", "--show-current")
    expected = work.get("worktree") or work.get("repository")
    # worktree téhož repozitáře (i náhled z Velínu) sdílí společný .git; cesty se liší
    common = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    same_repo = bool(common) and same_path(common, git(work.get("repository") or ".", "rev-parse",
                                                       "--path-format=absolute", "--git-common-dir"))
    if not (same_repo or same_path(top, work.get("repository")) or same_path(top, work.get("worktree"))) \
            or branch != work.get("branch"):
        raise Stop(EXIT_CONTEXT, f"Jiný kontext: očekává se {work.get('branch')} v {expected}, jsi na "
                                 f"{branch or '(žádná větev)'} v {top or cwd}. Nezačínej, nic nezahazuj.")
    remember(cwd, ticket_id, args)
    session = read_json(Path(cwd) / SESSION)
    try:
        call(cwd, "POST", f"/work/{quote(ticket_id)}/run", {
            "sessionId": session.get("sessionId") or os.environ.get("OPORA_SESSION_ID") or uuid.uuid4().hex,
            "agent": os.environ.get("OPORA_AGENT_NAME") or "terminal", "transcriptPath": session.get("transcriptPath")})
        run_line = None
    except Stop as stop:
        if stop.code != EXIT_REFUSED or "(404" not in stop.text:  # jen chybějící routa; ostatní chyby jako dosud
            raise
        run_line = "Relace: server ji neeviduje (starší verze)"
    ticket = found.get("ticket") or {}
    brief = ticket.get("body") or ticket
    dirty = git(cwd, "status", "--porcelain")
    lines = [f"Úkol {ticket_id}: {ticket.get('title', '')}".rstrip(),
             f"Větev {work.get('branch')}",
             (f"Rodič: {work.get('baseBranch')}@{(work.get('baseSha') or '')[:7]}; "
              f"začlení se do: {work.get('target') or '-'}"),
             f"Stav: {found.get('stateLabel') or found.get('state')}; další krok: {work.get('next') or '-'}"]
    lines += [f"{label}: {brief[key]}" for key, label in (("essence", "Podstata"), ("build", "Stavba"),
                                                         ("doneCriteria", "Hotovo když")) if brief.get(key)]
    lines += [run_line] if run_line else []
    mark = work.get("mark")
    lines += [f"Vodotisk: {mark}", f'Commit: trailer "Opora-Mark: {mark}"; podstata v kódu "# {mark}.<krok>: proč"'] \
        if mark else ["Vodotisk: neevidován"]
    lines.append("Necommitnuté změny:\n" + dirty if dirty else "Necommitnuté změny: žádné")
    return "\n".join(lines)


def status(cwd, args):
    found = call(cwd, "GET", f"/work/{quote(find_ticket(cwd, args))}")
    work = found.get("work") or {}
    return (f"{found.get('stateLabel') or found.get('state')}; větev {work.get('branch')} "
            f"@{(work.get('headSha') or '')[:7] or '-'}; další krok: {work.get('next') or '-'}"
            + (f"; blokace: {work['blocked'].get('reason')}" if work.get("blocked") else ""))


def board(cwd, args):
    project, workspace = scope(cwd, args)
    if not (project and workspace):
        raise Stop(EXIT_CONTEXT, "Neznám projekt: zadej --project a --workspace (OPORA_PROJECT/…).")
    return call(cwd, "GET", "/board.txt", query={"project": project, "workspace": workspace,
                                                  **({"mine": 1} if args.mine else {}),
                                                  **({"all": 1} if args.all else {})}, text=True).strip()


def post(cwd, args, action, body=None):
    return json.dumps(call(cwd, "POST", f"/work/{quote(find_ticket(cwd, args))}/{action}", body or {}),
                      ensure_ascii=False)


def report(cwd, args):
    checks = []
    for item in args.check:
        name, sep, state = item.rpartition("=")
        if not sep or not name or state not in ("green", "red", "pending"):
            raise Stop(EXIT_CONTEXT, f"Kontrola {item!r} má tvar \"název=green|red|pending\".")
        checks.append({"name": name, "status": state})
    sha = git(cwd, "rev-parse", args.sha or "HEAD")
    if not sha:
        raise Stop(EXIT_CONTEXT, f"Commit {args.sha or 'HEAD'} v {cwd} neexistuje.")
    mark = (call(cwd, "GET", f"/work/{quote(find_ticket(cwd, args))}").get("work") or {}).get("mark")
    if mark and not args.allow_unmarked \
            and f"Opora-Mark: {mark}" not in git(cwd, "log", "-1", "--format=%B", sha).splitlines():
        raise Stop(EXIT_CONTEXT, f"Commit {sha[:7]} nemá řádek \"Opora-Mark: {mark}\". Doplň ho "
                                 f"(`git commit --amend`, jen u vlastního nesdíleného commitu), nebo použij "
                                 f"--allow-unmarked u cizího commitu či úklidu.")
    body = {"sha": sha, "checks": checks, "worktree": str(cwd)}
    if args.tryout is not None or args.step:  # bez nich server převezme předchozí `tryout`
        body["tryout"] = {"at": args.tryout or "", "steps": args.step}
    return post(cwd, args, "report", body)


def accept(cwd, args):
    sha = git(cwd, "rev-parse", args.sha or "HEAD")
    if not sha:
        raise Stop(EXIT_CONTEXT, "Revize pro přijetí neexistuje.")
    return post(cwd, args, "accept", {"sha": sha, "note": args.note or "", "untested": args.untested})


def trace(cwd, args):
    mark = args.mark or (call(cwd, "GET", f"/work/{quote(find_ticket(cwd, args))}").get("work") or {}).get("mark")
    if not mark:
        raise Stop(EXIT_CONTEXT, "Úkol nemá vodotisk (starý ticket); zadej --mark OP-….")
    t = call(cwd, "GET", f"/trace/{quote(mark)}")
    ticket, card = t.get("ticket") or {}, t.get("card") or {}

    def flat(value):  # PR, přijetí, … jako "klíč=hodnota"; tvar hran určuje server
        return ", ".join(f"{k}={v}" for k, v in value.items() if v not in (None, "", [], {})) if value else "-"

    out = [f"== {mark}: {ticket.get('title') or '-'} ==", "Proč",
           f"  karta: {card.get('name') or '-'}{' ' + card['link'] if card.get('link') else ''}; "
           f"revize: {t.get('revision') or '-'}",
           f"  podstata: {(ticket.get('body') or {}).get('essence') or '-'}"]
    out += [f"  krok {step.get('order')}: {step.get('title')}" for step in t.get("plan") or []]
    out.append("Kdo")
    out += [f"  {r.get('agent')} {r.get('startedAt')} od {(r.get('fromSha') or '')[:7] or '-'} {r.get('status')}"
            for r in t.get("runs") or []] or ["  žádná relace"]
    out.append("Co")
    out += [f"  {c.get('sha7')} {c.get('title')} {c.get('status')} {c.get('runId') or 'bez relace'}"
            for c in t.get("commits") or []]
    out += [f"  {c.get('path')}:{c.get('line')} {c.get('symbol') or '-'} {c.get('status')}"
            for c in t.get("code") or []]
    out.append("Kde")
    out += [f"  {label}: {flat(t.get(key))}" for key, label in (("pr", "PR"), ("acceptance", "přijetí"),
                                                                  ("merged", "začlenění"), ("preview", "náhled"))]
    out += [f"  kontrola: {flat(check)}" for check in t.get("checks") or []]
    out.append("Mezery")
    out += [f"  {gap.get('text')}" for gap in t.get("gaps") or []] or ["  žádné"]
    return "\n".join(out + ["", t.get("sentence") or ""]).rstrip()


COMMANDS = {"task": task, "status": status, "board": board, "report": report, "trace": trace, "accept": accept,
            "allow-merge": lambda cwd, args: post(cwd, args, "allow-merge", {"target": args.target}),
            "block": lambda cwd, args: post(cwd, args, "block", {"reason": args.reason})}
COMMANDS |= {action: lambda cwd, args, action=action: post(cwd, args, action)
             for action in ("preview", "merge", "defer", "resume", "forget")}


def parser():
    root = argparse.ArgumentParser(prog="linie.py", description="Úkol Linie z terminálu (evidence v OPOŘE).")
    sub = root.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        command = sub.add_parser(name)
        for option in ("--ticket", "--project", "--workspace"):
            command.add_argument(option)
        if name == "accept":
            command.add_argument("--sha", help="výchozí HEAD")
            command.add_argument("--note")
            command.add_argument("--untested", action="store_true", help="výslovně bez lidské zkoušky")
        if name == "allow-merge":
            command.add_argument("--target")
        if name == "report":
            command.add_argument("--check", action="append", default=[], help='"npm test=green"')
            command.add_argument("--sha", help="výchozí HEAD")
            command.add_argument("--allow-unmarked", action="store_true", help="přeskočí kontrolu Opora-Mark")
            command.add_argument("--try", dest="tryout", help='kde vyzkoušet, query "screen=pletor&part=linie"')
            command.add_argument("--step", action="append", default=[], help='krok "co udělat → co uvidíš"')
        if name == "board":
            command.add_argument("--mine", action="store_true", help="jen kuličky volajícího agenta")
            command.add_argument("--all", action="store_true", help="i uzavřené řádky s kuličkami")
        if name == "trace":
            command.add_argument("--mark", help="OP-…, výchozí značka úkolu")
        if name == "block":
            command.add_argument("--reason", required=True)
    return root


def main(argv=None, cwd=None):
    args = parser().parse_args(argv)
    try:
        scope(Path(cwd or os.getcwd()), args)
        print(COMMANDS[args.command](Path(cwd or os.getcwd()), args))
    except Stop as stop:
        print(stop.text)
        return stop.code
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # konzole Windows by jinak češtinu nevypsala
    sys.exit(main())
