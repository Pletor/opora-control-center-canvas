"""Jedna dávka srdce = jeden proces `claude -p` (docs/brain-heart.md §2).

Dávka složí zprávu (snímek, vstupy, pokyn skončit `done`), spustí proces, přečte výsledek JSON a zapíše
jeden řádek do `brain/batches.jsonl`: vstupy, relaci, cenu po modelech (`modelUsage`; poradce = položka Opus),
tahy, chybu, trvání, shrnutí z `done` a cenu dílčích volání dílny (`subCostUsd` z `dilna/runs.jsonl`, §3b). Když poradce za den přesáhne `ADVISOR_DAY_USD`, běží dávka
bez `--advisor` (záznam nese `advisor: false`). Pozná vyčerpaný limit předplatného (`rate_limited`) a vypršení času.
"""
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from backend.brain_opora.heart import command, session
from backend.brain_opora.heart.process import run_process

JOURNAL, LAST_DONE, SNAPSHOT = "batches.jsonl", "last_done.json", "snapshot.txt"
RUNS = Path(command.DILNA) / "runs.jsonl"  # píše ho `opora_heart.py run`
TIMEOUT = 15 * 60
# strop poradce za den (UTC) na projekt; eval m3/m6: poradce = 86 % ceny srdce, nejdražší sezení 0,37 USD
ADVISOR_DAY_USD = 2.0
RATE_LIMIT = re.compile(r"hit your [^\n]{0,60}limit|rate[_ ]limit|usage limit", re.IGNORECASE)
FINISH = ("Až budeš hotové, ukonči dávku příkazem `python opora_heart.py done --summary \"…\"` "
          "(jedna věta: co jsi naplánovalo, zodpovědělo nebo eskalovalo).")


@dataclass
class BatchSpec:
    brain: Path
    claude: str
    base_url: str
    token: str
    project: str
    workspace: str
    snapshot: str
    inputs: list = field(default_factory=list)
    source_root: Path | None = None


def _intake(item):
    """Značka vstupní brány za řádkem vstupu: ` [vstup ie_… · stanovisko · jev 0.82 · oblast A · podobné: ie_…]`
    (jistota jen od Jevu, oblast jen známá); bez vstupu prázdná."""
    entry = item.get("intake") if isinstance(item.get("intake"), dict) else None
    if not entry or not entry.get("id"):
        return ""
    similar = [str(value) for value in entry.get("candidates") or []]
    parts = [f"vstup {entry['id']}", str(entry.get("verdict") or "?")]
    if entry.get("layer") == "jev" and isinstance(entry.get("confidence"), (int, float)):
        parts.append(f"jev {entry['confidence']:.2f}")
    if entry.get("areaId"):
        parts.append(f"oblast {entry['areaId']}")
    if similar:
        parts.append(f"podobné: {', '.join(similar)}")
    return " [" + " · ".join(parts) + "]"


def _input_line(item):
    kind = item.get("type")
    if kind == "message":
        return f"- ZPRÁVA ČLOVĚKA: {item['text']}{_intake(item)}"
    if kind == "ticket":
        body = json.dumps(item.get("body"), ensure_ascii=False, sort_keys=True)
        return f"- LÍSTEK {item['ticketId']} ({item['kind']}) od pracovníka: {body}{_intake(item)}"
    if kind == "taskFailed":
        body = json.dumps(item.get("body"), ensure_ascii=False, sort_keys=True)[:1500]
        report = json.dumps(item.get("report"), ensure_ascii=False, sort_keys=True)[:1500]
        return (f"- ÚKOL SELHAL {item['taskId']} „{item.get('title', '')}“ (druhá červená, už uzavřený): "
                f"zadání {body}; report {report}")
    if kind == "merged":
        pr = f"PR #{item['pr']}" if item.get("pr") else "lokální sloučení"
        return (f"- SLOUČENO: karta {item.get('nodeId') or '?'}, {pr}, sha {str(item.get('mergeSha') or '?')[:12]}"
                f" (běh {item.get('executionId') or '?'})")
    if kind == "commits":
        log = "; ".join(item.get("log") or []) or "(bez výpisu)"
        return f"- NOVÉ COMMITY {str(item.get('from') or '?')[:7]}..{str(item.get('to') or '?')[:7]}: {log}"
    return "- " + json.dumps(item, ensure_ascii=False, sort_keys=True)


def message(snapshot_text, inputs):
    """Zpráva dávky: snímek, vstupy této dávky a pokyn k ukončení."""
    lines = ["SNÍMEK PROJEKTU", snapshot_text, "", "VSTUPY TÉTO DÁVKY"]
    lines += [_input_line(item) for item in inputs] or ["- (žádné)"]
    return "\n".join([*lines, "", FINISH])


def parse(stdout):
    """Objekt výsledku `--output-format json`; poslední řádek, který je objekt JSON, jinak None."""
    for line in reversed((stdout or "").strip().splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def costs(result):
    """`{model: costUSD}` z `modelUsage` výsledku."""
    usage = (result or {}).get("modelUsage")
    if not isinstance(usage, dict):
        return {}
    return {model: round(float(item.get("costUSD") or 0), 6) for model, item in usage.items() if isinstance(item, dict)}


def rate_limited(result, stderr=""):
    """Vyčerpaný limit předplatného: `is_error` s `rate_limit` nebo text „hit your … limit“."""
    text = json.dumps(result, ensure_ascii=False) if result else ""
    errored = bool(result and result.get("is_error"))
    return bool((errored or not result) and RATE_LIMIT.search(text + "\n" + (stderr or "")))


def _summary(brain):
    try:
        value = json.loads((brain / LAST_DONE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value.get("summary") if isinstance(value, dict) else None


def _status(outcome, result, stderr):
    if outcome.timed_out:
        return "timeout"
    if rate_limited(result, stderr):
        return "rate_limited"
    return "error" if result is None or result.get("is_error") else "ok"


def run(spec, runner=run_process, clock=time.time):
    """Spustí dávku a vrátí její záznam (stejný, jaký zapíše do `batches.jsonl`)."""
    brain = Path(spec.brain)
    brain.mkdir(parents=True, exist_ok=True)
    (brain / SNAPSHOT).write_text(spec.snapshot, encoding="utf-8")
    (brain / LAST_DONE).unlink(missing_ok=True)
    settings_path, mcp_path = command.write_config(brain, spec.source_root)
    prompt_digest = hashlib.sha256(Path(command.PROMPT_FILE).read_bytes()).hexdigest()
    session_id, resume = session.choose(brain, prompt_digest=prompt_digest)
    started = clock()
    advisor = advisor_spent(brain, started) < ADVISOR_DAY_USD
    line = command.build_command(spec.claude, session_id=session_id, resume=resume, settings_path=settings_path,
                                 mcp_path=mcp_path, source_root=spec.source_root, advisor=advisor)
    env = command.child_env(base_url=spec.base_url, token=spec.token, project=spec.project, workspace=spec.workspace,
                            source_root=spec.source_root)
    outcome = runner(line, cwd=str(brain), env=env, stdin_text=message(spec.snapshot, spec.inputs), timeout=TIMEOUT)
    result = parse(outcome.stdout)
    status = _status(outcome, result, outcome.stderr)
    used = session.input_tokens((result or {}).get("usage"))
    if result and isinstance(result.get("session_id"), str) and status != "rate_limited":
        # Chybná dávka (třeba ztracená relace) vynutí rotaci, aby se další dávka nezasekla na --resume.
        session.record(brain, result["session_id"], used if status == "ok" else session.ROTATE_AT + 1, prompt_digest)
    at = datetime.fromtimestamp(started, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"at": at, "project": spec.project,
             "workspace": spec.workspace, "status": status, "inputs": spec.inputs,
             "sessionId": (result or {}).get("session_id") or session_id, "resumed": resume, "advisor": advisor,
             "costUsd": (result or {}).get("total_cost_usd"), "costByModel": costs(result),
             "numTurns": (result or {}).get("num_turns"), "isError": bool((result or {}).get("is_error", True)),
             "durationMs": int((clock() - started) * 1000), "inputTokens": used, "summary": _summary(brain),
             "subCostUsd": sub_cost(brain, at)}
    if status != "ok":
        entry["error"] = ((result or {}).get("result") or outcome.stderr or "")[-1000:]
    with (brain / JOURNAL).open("a", encoding="utf-8") as journal:
        journal.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def sub_cost(brain, since):
    """Součet `subCostUsd` běhů dílny od `since` (čas začátku dávky, stejný tvar ISO UTC)."""
    try:
        lines = (Path(brain) / RUNS).read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0.0
    entries = (parse(line) for line in lines)
    return round(sum(float(entry.get("subCostUsd") or 0) for entry in entries
                     if entry and str(entry.get("at", "")) >= since), 6)


def advisor_spent(brain, now):
    """Cena poradce (položky Opus v `costByModel`) z dávek dne `now` (UTC) v deníku."""
    day = datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%d")
    try:
        lines = (Path(brain) / JOURNAL).read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0.0
    entries = (parse(line) for line in lines)
    return sum(float(cost or 0) for entry in entries if entry and str(entry.get("at", "")).startswith(day)
               for model, cost in (entry.get("costByModel") or {}).items() if "opus" in model.lower())


def read_journal(brain, last=5):
    """Posledních `last` záznamů dávek (nejnovější poslední); poškozené řádky se přeskočí."""
    try:
        lines = (Path(brain) / JOURNAL).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = [entry for entry in (parse(line) for line in lines[-last * 2:]) if entry]
    return entries[-last:]
