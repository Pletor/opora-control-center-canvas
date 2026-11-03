"""Referenční runner brány cesty zákazníka (`docs/brana-cesty.md` §6).

Stáhne plán přehrání, přehraje jeho segmenty v jednom prohlížeči (Python Playwright, volitelná závislost)
a odevzdá doklad `opora.journey-run/1`. Exit 0 jen když prošly všechny segmenty plánu. Před přehráním ohlásí
start běhu a během něj posílá heartbeat s přechodem (§3a, „cesta právě běží“); selhání těchto hlášení běh nezastaví,
jen vypíše varování. `--dry-run` je neposílá.

    uv run python tools/journey_run.py --server http://127.0.0.1:8740 --project <id> --journey <id>
        [--application <id>] [--base-url URL] [--fixtures file.json] [--headed] [--dry-run] [--log FILE]

`--intent PAGE` místo `--journey` ověří záměr stránky (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §6):
stáhne `intent-plan` aktivní verze záměru, přehraje kroky a očekávání (`intent_run_browser.py`) a odevzdá doklad
`opora.intent-run/1` na `intent-runs`. Exit 0, když žádný uzel neselhal (neověřené uzly exit nekazí).

Exit: 0 prošlo, 1 neprošlo nebo chyba serveru, 2 chybí Playwright nebo špatné zadání.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from tools import intent_run_browser, intent_run_logic
    from tools import journey_run_browser as browser
    from tools import journey_run_logic as logic
except ImportError:  # spuštěno jako skript z tools/
    import intent_run_browser  # type: ignore[no-redef]
    import intent_run_logic  # type: ignore[no-redef]
    import journey_run_browser as browser  # type: ignore[no-redef]
    import journey_run_logic as logic  # type: ignore[no-redef]

INSTALL_HINT = ("Runner potřebuje Python Playwright (volitelná závislost, jako tools/e2e):\n"
                "  uv pip install playwright && uv run playwright install chromium\n"
                "nebo jednorázově: uv run --with playwright python tools/journey_run.py …")


LIVE_TIMEOUT_S = 5


def _http(method: str, url: str, server: str, body: dict | None = None, timeout: float = 30):
    headers = {"Accept": "application/json", "Origin": server}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, raw


def _expect_ok(what: str, status: int, body):
    if status != 200:
        raise RuntimeError(f"{what}: HTTP {status}: {body.get('detail') if isinstance(body, dict) else body}")
    return body


def fetch_plan(server: str, project: str, journey: str, application: str | None) -> dict:
    params = {"project": project, "journey": journey}
    if application:
        params["application"] = application
    url = f"{server}/api/project-architecture/journey-plan?{urllib.parse.urlencode(params)}"
    return logic.check_plan(_expect_ok("plán cesty", *_http("GET", url, server)))


def post_run(server: str, project: str, run: dict) -> dict:
    url = f"{server}/api/project-architecture/journey-runs?{urllib.parse.urlencode({'project': project})}"
    return _expect_ok("doklad", *_http("POST", url, server, run))


class LiveRun:
    """Hlášení „cesta právě běží“ (`docs/brana-cesty.md` §3a): start a heartbeat po segmentech. Jen informuje
    Studio a Editor stránky; když selže, vypíše varování a další hlášení vynechá, přehrání ani doklad nezastaví."""

    def __init__(self, server: str, project: str, plan: dict, warn):
        self.server, self.project, self.plan, self.warn = server, project, plan, warn
        self.run_id: str | None = None

    def _post(self, what: str, path: str, body: dict, expect: int):
        try:
            status, answer = _http("POST", f"{self.server}/api/project-architecture/journey-runs{path}", self.server,
                                   body, timeout=LIVE_TIMEOUT_S)
        except (OSError, ValueError) as error:
            status, answer = None, str(error)
        if status != expect:
            detail = answer.get("detail") if isinstance(answer, dict) else answer
            self.warn(f"varování: {what} se nepodařilo ohlásit ({f'HTTP {status}: ' if status else ''}{detail}); běh pokračuje")
            self.run_id = None
            return None
        return answer

    def start(self) -> None:
        body = {"project": self.project, "journeyId": self.plan["journeyId"], "applicationId": self.plan["applicationId"]}
        answer = self._post("start běhu", "/start", body, 200)
        run_id = answer.get("runId") if isinstance(answer, dict) else None
        self.run_id = run_id if isinstance(run_id, str) and run_id else None

    def progress(self, segment: dict, ok: bool | None = None) -> None:
        if not self.run_id:
            return
        body = {"segment": {"from": segment["from"], "to": segment["to"]}, **({"ok": ok} if ok is not None else {})}
        self._post("průběh běhu", f"/{urllib.parse.quote(self.run_id, safe='')}/progress", body, 204)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Přehraje cestu zákazníka a odevzdá doklad (docs/brana-cesty.md).")
    parser.add_argument("--server", default="http://127.0.0.1:8740")
    parser.add_argument("--project", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--journey")
    target.add_argument("--intent", metavar="PAGE", help="ověří záměr stránky PAGE (nodeId) místo cesty")
    parser.add_argument("--application")
    parser.add_argument("--base-url", help="přepíše baseUrl plánu (digest na něm nezávisí)")
    parser.add_argument("--fixtures", help="JSON {\"<journeyId>/<to>\": {selector|popisek: hodnota}}")
    parser.add_argument("--headed", action="store_true", help="viditelný prohlížeč")
    parser.add_argument("--dry-run", action="store_true", help="doklad jen vypíše, neodešle")
    parser.add_argument("--log", help="soubor průběhu; jeho file:// URL jde do logUrl")
    return parser.parse_args(argv)


def run_intent(server: str, args: argparse.Namespace) -> int:
    """Ověření záměru stránky: plán → přehrání → doklad (bez `--fixtures`, `--log` a hlášení „běží“)."""
    query = urllib.parse.urlencode({"project": args.project, "page": args.intent})
    try:
        plan = intent_run_logic.check_plan(_expect_ok(
            "plán záměru", *_http("GET", f"{server}/api/project-architecture/intent-plan?{query}", server)))
    except (RuntimeError, TypeError, ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    base_url = args.base_url or plan.get("baseUrl")
    if not base_url:
        print("Plán nemá baseUrl (aplikace bez prostředí): dodej --base-url.", file=sys.stderr)
        return 2
    results = intent_run_browser.replay(plan, base_url, args.headed, lambda line: print(line, file=sys.stderr))
    run = intent_run_logic.build_run(plan, results)
    print(json.dumps(run, ensure_ascii=False, indent=2))
    if not args.dry_run:
        url = f"{server}/api/project-architecture/intent-runs?{urllib.parse.urlencode({'project': args.project})}"
        try:
            _expect_ok("doklad záměru", *_http("POST", url, server, run))
        except (RuntimeError, OSError) as error:
            print(error, file=sys.stderr)
            return 1
    return 0 if intent_run_logic.run_passed(run) else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # doklad i důvody v UTF-8 i v rouře na Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    server = args.server.rstrip("/")
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        print(INSTALL_HINT, file=sys.stderr)
        return 2
    if args.intent:
        return run_intent(server, args)
    try:
        fixtures = logic.load_fixtures(args.fixtures)
    except (OSError, TypeError, ValueError) as error:
        print(f"fixtures: {error}", file=sys.stderr)
        return 2
    try:
        plan = fetch_plan(server, args.project, args.journey, args.application)
    except (RuntimeError, TypeError, ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    base_url = args.base_url or plan.get("baseUrl")
    if not base_url:
        print("Plán nemá baseUrl (aplikace bez prostředí): dodej --base-url.", file=sys.stderr)
        return 2
    log_lines: list[str] = []

    def log(line: str) -> None:
        log_lines.append(line)
        print(line, file=sys.stderr)

    live = None
    if not args.dry_run:
        live = LiveRun(server, args.project, plan, lambda line: print(line, file=sys.stderr))
        live.start()
    at = logic.utc_now()
    results = browser.replay(plan, base_url, fixtures, args.headed, log, live.progress if live else None)
    log_url = None
    if args.log:
        log_path = Path(args.log).resolve()
        log_path.write_text("\n".join([f"{at} {base_url}", *log_lines]) + "\n", encoding="utf-8")
        log_url = log_path.as_uri()
    command = logic.command_line([sys.argv[0], *argv])
    run = logic.build_run(plan, command, at, results, log_url)
    print(json.dumps(run, ensure_ascii=False, indent=2))
    if not args.dry_run:
        try:
            post_run(server, args.project, run)
        except (RuntimeError, OSError) as error:
            print(error, file=sys.stderr)
            return 1
    return 0 if logic.run_passed(plan, run) else 1


if __name__ == "__main__":
    sys.exit(main())
