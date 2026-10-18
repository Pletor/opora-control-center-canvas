"""Spustitelná buňka Schránky bez databáze (docs/schranka-bunka.md §3 body 1, 3 a 4).

Buňka = fragment, jehož brána `synthesized` nese `checks`: 1–4 kontroly `{id, command}` pevně určené před výkonem.
`verified.actual.run` je doložený běh přesně těchto kontrol od vnějšího ověřovatele, `learned.kind` se řídí jeho
výsledkem. Tvar hlídá `validate_checks` / `validate_run` (volá je `validate_payload` v `brief_vault_gate_rules`),
pravidla vůči stavu fragmentu `check_run`, `lesson_kind_rule` a `same_checks` (volá je `brief_vault_gates`).

Syntaxe příkazu je společná se CLI ověřovatele (`opora_cycle.py run-checks`, spouští `shlex.split` bez shellu):
příkaz musí projít `shlex.split(command, posix=True)`, nesmí obsahovat `| & ; > < `` ` `` `$(` ani `\\` (cesty jen
s `/`), první token je program z `CHECK_PROGRAMS` a žádný token ani jeho část za `=` nebo `,` nezačíná `/`,
neodpovídá `^[A-Za-z]:` a neobsahuje `..` (příkaz běží v pracovní složce).
"""

import re
import shlex
from datetime import datetime

MAX_CHECKS, MAX_CHECK_COMMAND, MAX_RUN_ACTOR = 4, 300, 80
CHECK_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
CHECK_PROGRAMS = ("python", "py", "uv", "pytest", "npm", "npx", "node")
CHECK_FORBIDDEN = ("|", "&", ";", ">", "<", "`", "$(", "\\")
DRIVE = re.compile(r"^[A-Za-z]:")
RUN_KEYS = ("executor", "verifier", "checks", "at")
RUN_CHECK_KEYS = ("checkId", "command", "exitCode", "durationMs", "outputSha256")
SHA256 = re.compile(r"[0-9a-f]{64}")


def _bad(message):
    from backend.editor.brief_vault.brief_vault_model import bad_request
    bad_request(message)


def _text(value, limit, label):
    if not isinstance(value, str) or "\0" in value or len(value) > limit or not value.strip():
        _bad(f"{label} musí být neprázdný text do {limit} znaků.")
    return value


def _exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        _bad(f"{label} musí být objekt s poli {', '.join(keys)}.")
    return value


def command_error(command):
    """Důvod, proč příkaz kontroly neprojde společnou syntaxí (viz docstring modulu), nebo None."""
    if any(mark in command for mark in CHECK_FORBIDDEN):
        return "command kontroly nesmí obsahovat | & ; > < ` $( ani \\ (spouští se bez shellu, cesty jen s /)."
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return "command kontroly musí projít shlex.split (např. neuzavřené uvozovky)."
    if not tokens or tokens[0] not in CHECK_PROGRAMS:
        return "command kontroly musí začínat programem " + " | ".join(CHECK_PROGRAMS) + "."
    for token in tokens:
        for part in re.split(r"[=,]", token):
            if part.startswith("/") or DRIVE.match(part) or ".." in part:
                return "command kontroly nesmí obsahovat absolutní cestu ani .. (běží v pracovní složce)."
    return None


def validate_checks(checks):
    """`synthesized.checks` (bod 1): 1–4 položky `{id, command}`, jedinečná id, příkaz podle společné syntaxe."""
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS:
        _bad(f"checks musí být pole 1–{MAX_CHECKS} kontrol.")
    seen = set()
    for check in checks:
        _exact(check, ("id", "command"), "kontrola v checks")
        if not isinstance(check["id"], str) or not CHECK_ID.fullmatch(check["id"]) or check["id"] in seen:
            _bad("id kontroly musí být jedinečné [A-Za-z0-9_-]{1,80}.")
        seen.add(check["id"])
        error = command_error(_text(check["command"], MAX_CHECK_COMMAND, "command kontroly"))
        if error:
            _bad(error)


def validate_run(run):
    """Tvar `verified.actual.run` (bod 3); shodu se `synthesized.checks` hlídá `check_run`."""
    _exact(run, RUN_KEYS, "actual.run")
    _text(run["executor"], MAX_RUN_ACTOR, "run.executor")
    _text(run["verifier"], MAX_RUN_ACTOR, "run.verifier")
    if not isinstance(run["checks"], list) or not 1 <= len(run["checks"]) <= MAX_CHECKS:
        _bad(f"run.checks musí být pole 1–{MAX_CHECKS} běhů kontrol.")
    for item in run["checks"]:
        _exact(item, RUN_CHECK_KEYS, "běh v run.checks")
        _text(item["checkId"], 80, "run.checks.checkId")
        _text(item["command"], MAX_CHECK_COMMAND, "run.checks.command")
        if type(item["exitCode"]) is not int:
            _bad("run.checks.exitCode musí být celé číslo.")
        if type(item["durationMs"]) is not int or item["durationMs"] < 0:
            _bad("run.checks.durationMs musí být nezáporné celé číslo.")
        if not isinstance(item["outputSha256"], str) or not SHA256.fullmatch(item["outputSha256"]):
            _bad("run.checks.outputSha256 musí být 64 malých hex znaků (sha256).")
    try:
        zoned = isinstance(run["at"], str) and len(run["at"]) <= 40 and datetime.fromisoformat(run["at"]).tzinfo is not None
    except ValueError:
        zoned = False
    if not zoned:
        _bad("run.at musí být čas ISO 8601 se zónou.")


def check_run(synthesized, actual):
    """Pravidla `verified.actual.run` vůči `synthesized` (bod 3); 400 = porušení. Bez `checks` i bez `run` se nic
    nekontroluje (zpětná kompatibilita). Aktéra zápisu (ověřovatel ≠ vykonavatel) hlídá `brief_vault_gates`."""
    checks = (synthesized or {}).get("checks")
    run = actual.get("run")
    if run is None:
        if checks and actual["tests"] != "untested":
            _bad("synthesized má checks: tests pass/fail jen s run ze skutečného běhu kontrol, jinak tests untested.")
        return
    if not checks:
        _bad("run patří jen buňce: synthesized nemá checks, není co doložit.")
    if [(item["checkId"], item["command"]) for item in run["checks"]] != [(c["id"], c["command"]) for c in checks]:
        _bad("run.checks musí přesně odpovídat synthesized.checks (id i příkaz, totéž pořadí).")
    expected = "pass" if all(item["exitCode"] == 0 for item in run["checks"]) else "fail"
    if actual["tests"] != expected:
        _bad(f"tests musí být {expected}: pass právě když všechny kontroly skončily exitCode 0.")
    if run["executor"] == run["verifier"]:
        _bad("run.executor a run.verifier musí být různí aktéři (vykonavatel se neověřuje sám).")


def lesson_kind_rule(actual, kind):
    """`learned.kind` podle výsledku `verified` (bod 4): po neúspěchu (`verified_outcome`, §13) `antipattern`, po
    úspěchu s `tests == "pass"` `pattern`; úspěch bez prošlých testů druh neurčuje. 400 = porušení."""
    from backend.editor.brief_vault.brief_vault_gate_rules import verified_outcome
    _approved, failed = verified_outcome(actual)
    if failed and kind != "antipattern":
        _bad("po neúspěšném verified je poučení kind antipattern.")
    if not failed and (actual or {}).get("tests") == "pass" and kind != "pattern":
        _bad("po úspěšném verified s prošlými testy je poučení kind pattern.")


def earlier_checks(history):
    """`checks` poslední dříve zapnuté brány `synthesized` (`gates` JSON revizí v pořadí): seznam, `[]` = zapnutá bez
    kontrol, None = `synthesized` dosud nikdy zapnutá."""
    from backend.editor.brief_vault.brief_vault_gate_rules import parse_gates
    found = None
    for raw in history:
        entry = parse_gates(raw).get("synthesized")
        if isinstance(entry, dict) and entry.get("value") is True and isinstance(entry.get("payload"), dict):
            found = entry["payload"].get("checks") or []
    return found


def same_checks(earlier, synthesized):
    """Kontroly jsou měřítko napříč koly: nový `synthesized` po dřívějším zapnutém nese tytéž `checks`, včetně stavu
    „žádné“ (přidání kontrol v dalším kole je změna). 400 jinak; změnu dělá člověk (volající ho pustí)."""
    if earlier is not None and ((synthesized or {}).get("checks") or []) != earlier:
        _bad("kontroly jsou měřítko napříč koly; změnu dělá člověk (checks musí zůstat stejné: id, příkaz, pořadí,"
             " i přidání checks v dalším kole).")
