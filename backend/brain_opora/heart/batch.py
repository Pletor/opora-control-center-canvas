"""Jedna dávka srdce = jeden proces `claude -p` (docs/brain-heart.md §2).

Dávka složí zprávu (snímek, vstupy, pokyn skončit `done`), spustí proces, přečte výsledek JSON a zapíše
jeden řádek do `brain/batches.jsonl`: vstupy, relaci, cenu po modelech (`modelUsage`; poradce = položka Opus),
tahy, chybu, trvání, shrnutí z `done`, cenu dílčích volání dílny (`subCostUsd` z `dilna/runs.jsonl`, §3b) a piny
skillů srdce z Brainu (`brainPins`, s jakou verzí promptu a postupů dávka běžela).
Cena: `claude -p --resume` vrací součet celé relace, proto u navázané dávky nesou `costUsd` a `costByModel` jen
přírůstek proti poslednímu záznamu téže relace a `sessionCostUsd` / `sessionCostByModel` surové kumulativní hodnoty
(nová relace: obě dvojice stejné).
Tokeny: `inputTokens` je součet vstupu přes všechny tahy, `contextTokens` kontext posledního tahu (podle něj se
rotuje relace, `session.context_tokens`) a `fresh`, `cacheRead`, `cacheCreation`, `output` rozpad `usage` dávky. Když poradce za den přesáhne `ADVISOR_DAY_USD`, běží dávka
bez `--advisor` (záznam nese `advisor: false`). Pozná vyčerpaný limit předplatného (`rate_limited`) a vypršení času.
"""
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from backend.brain_opora.determinism.brief import REASONS as BRIEF_REASONS
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
    skills: command.HeartSkills  # aktivní skilly srdce z Brainu (`command.heart_skills`)
    inputs: list = field(default_factory=list)
    source_root: Path | None = None
    model: str = command.MODEL  # uzel `model.claude` enginu toků; výchozí = dnešní srdce
    advisor_model: str = command.ADVISOR
    subcommands: tuple | None = None  # uzel `tool.opora_heart`: povolené podpříkazy, None = všechny


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
    if kind == "workFailed":  # ticket práce selhal (ticket.failed, docs/navrhy/2026-11-03-novy-zaklad.md §3.3)
        body = json.dumps(item.get("body"), ensure_ascii=False, sort_keys=True)[:1500]
        delivery = json.dumps(item.get("delivery"), ensure_ascii=False, sort_keys=True)[:1500]
        return (f"- TICKET SELHAL {item['ticketId']} (karta {item.get('cardId') or '?'}, už uzavřený): "
                f"{item.get('reason') or 'bez důvodu'}; tělo {body}; odevzdání {delivery}")
    if kind == "merged":
        pr = f"PR #{item['pr']}" if item.get("pr") else "lokální sloučení"
        return (f"- SLOUČENO: karta {item.get('nodeId') or '?'}, {pr}, sha {str(item.get('mergeSha') or '?')[:12]}"
                f" (běh {item.get('executionId') or '?'})")
    if kind == "commits":
        log = "; ".join(item.get("log") or []) or "(bez výpisu)"
        return f"- NOVÉ COMMITY {str(item.get('from') or '?')[:7]}..{str(item.get('to') or '?')[:7]}: {log}"
    if kind == "milestoneDone":  # spouštěč milestone.done (docs/navrhy/2026-10-30-metriky-a-spoustece.md §4)
        deferred = ", ".join(f"{rq.get('id')} „{rq.get('title')}“" for rq in item.get("deferred") or []) or "žádné"
        return (f"- MILNÍK SPLNĚN {item.get('milestoneId')} „{item.get('title')}“ (oblast {item.get('areaId')}):"
                f" odložené požadavky k otevření: {deferred}")
    if kind == "cardTrigger":  # spouštěč karty (determinism/triggers.py)
        return f"- SPOUŠTĚČ {item.get('kind')} · {item.get('nodeId')} „{item.get('title')}“: {item.get('detail')}"
    if kind == "brief":  # spouštěč výslechu (docs/navrhy/2026-10-30-vyslech-srdce.md §2, determinism/brief.py)
        if item.get("nodeId"):
            return f"- VÝSLECH (krátký): karta {item['nodeId']} „{item.get('title')}“ ({item.get('detail')})"
        spis = f" · spis: {item['detail']}" if item.get("detail") else ""
        return (f"- VÝSLECH: {item.get('requirementId')} „{item.get('title')}“"
                f" ({BRIEF_REASONS.get(item.get('reason'), item.get('reason'))}){spis}")
    if kind == "idle":  # spouštěč prázdné fronty (determinism/idle.py, OPORA-002)
        return (f"- PRÁZDNÁ FRONTA od {item.get('since')} (karet {item.get('cardsTotal')}, sloučeno {item.get('done')}):"
                " Plán nemá žádnou kartu k převzetí a nic neběží. Podle cíle projektu a stavu aplikace naplánuj"
                " další malou kartu (nebo ukonči fázi otázkou člověku, pokud cíl je splněný)."
                + ("\n  OPUŠTĚNÉ KARTY (PR zavřené bez sloučení, nikdo na nich nepracuje): "
                   + ", ".join(f"{a.get('nodeId')} (PR #{a.get('pr')})" for a in item["abandoned"])
                   + ". Ověř na origin/main: je-li práce sloučená jinde nebo jde o duplikát, kartu odeber z plánu"
                   " a navazující karty napoj na její předchůdce; jinak ji připrav k novému převzetí."
                   if item.get("abandoned") else "")
                + ("\n  PŘIJATÉ KARTY BEZ KROKŮ (nic je neblokuje, ale bez spec.steps je nikdo nepřevezme): "
                   + ", ".join(item["unplanned"]) + ". Rozepiš jim kroky (nejdřív ty nahoře), než založíš nové karty."
                   if item.get("unplanned") else "")
                + ("\n  ČEKÁ NA ČLOVĚKA (blokuje jen sebe a navazující karty): " + _waiting(item["waitingHuman"])
                   + ". Tyto karty ani svou otázku neopakuj a nečekej na ně: naplánuj práci, která na nich nezávisí"
                   " (jiná oblast nebo obrazovka podle cíle projektu)."
                   if item.get("waitingHuman") else "")
                + ("\n  CÍL PROJEKTU (docs/cil-projektu.md na main, rozhodnutí člověka; plánuj k němu, ne podle starého plánu):"
                   f"\n{item['goal']}" if item.get("goal") else ""))
    if kind == "humanChange":
        return f"- SPOUŠTĚČ {item.get('kind')}: člověk změnil plán (revize {item.get('revision')})"
    return "- " + json.dumps(item, ensure_ascii=False, sort_keys=True)


def _waiting(waits):
    """Co čeká na člověka, jednou větou: karty (PR ke schválení / výsledek k revizi), otázky, rozhodnutí."""
    why = {"approval": "PR ke schválení", "round_cap": "PR za stropem kol revize", "review": "výsledek k revizi"}
    parts = [f"{c.get('nodeId')} ({why.get(c.get('why'), c.get('why'))}" + (f" #{c['pr']})" if c.get("pr") else ")")
             for c in waits.get("cards") or []]
    if waits.get("questions"):
        parts.append(f"otázky srdce: {waits['questions']}")
    if waits.get("decisions"):
        parts.append(f"rozhodnutí: {waits['decisions']}")
    return ", ".join(parts) or "—"


def message(snapshot_text, inputs):
    """Zpráva dávky: snímek, vstupy této dávky a pokyn k ukončení."""
    lines = ["SNÍMEK PROJEKTU", snapshot_text, "", "VSTUPY TÉTO DÁVKY"]
    lines += [_input_line(item) for item in inputs] or ["- (žádné)"]
    return "\n".join([*lines, "", FINISH])


def parse(stdout):
    """Objekt výsledku `claude -p` (`stream-json` i `json`): poslední řádek, který je objekt JSON s `type` `result`
    nebo bez `type` (řádek deníku); události proudu (`system`, `assistant`, `user`) se přeskočí. Jinak None."""
    for line in reversed((stdout or "").strip().splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("type", "result") == "result":
            return value
    return None


def costs(result):
    """`{model: costUSD}` z `modelUsage` výsledku."""
    usage = (result or {}).get("modelUsage")
    if not isinstance(usage, dict):
        return {}
    return {model: round(float(item.get("costUSD") or 0), 6) for model, item in usage.items() if isinstance(item, dict)}


def _round_cost(value):
    return round(max(float(value or 0), 0.0), 6)


def previous_session_cost(brain, session_id):
    """`(costUsd, costByModel)` kumulativní ceny relace z posledního záznamu deníku se stejným `sessionId`, jinak None.
    Starší záznamy bez `sessionCostUsd` ukládaly kumulativní hodnoty do `costUsd` / `costByModel`."""
    try:
        lines = (Path(brain) / JOURNAL).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        entry = parse(line)
        if entry and entry.get("sessionId") == session_id:
            total = entry["sessionCostUsd"] if "sessionCostUsd" in entry else entry.get("costUsd")
            by_model = entry["sessionCostByModel"] if "sessionCostByModel" in entry else entry.get("costByModel")
            return total, by_model if isinstance(by_model, dict) else {}
    return None


def batch_cost(total, by_model, previous):
    """`(costUsd, costByModel)` dávky: bez předchozího záznamu relace kumulativní hodnoty, jinak nezáporný přírůstek
    (model, který v předchozím záznamu nebyl, se bere celý)."""
    if previous is None:
        return total, by_model
    before_total, before_models = previous
    delta_total = None if total is None else _round_cost(float(total) - float(before_total or 0))
    return delta_total, {model: _round_cost(cost - float(before_models.get(model) or 0)) for model, cost in by_model.items()}


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
    settings_path, mcp_path, prompt_path = command.write_config(brain, spec.skills, spec.source_root)
    prompt_digest = hashlib.sha256(spec.skills.prompt.encode("utf-8")).hexdigest()
    session_id, resume = session.choose(brain, prompt_digest=prompt_digest)
    started = clock()
    advisor = advisor_spent(brain, started) < ADVISOR_DAY_USD
    line = command.build_command(spec.claude, session_id=session_id, resume=resume, settings_path=settings_path,
                                 mcp_path=mcp_path, prompt_file=prompt_path, source_root=spec.source_root, advisor=advisor, model=spec.model,
                                 advisor_model=spec.advisor_model, subcommands=spec.subcommands)
    env = command.child_env(base_url=spec.base_url, token=spec.token, project=spec.project, workspace=spec.workspace,
                            source_root=spec.source_root)
    outcome = runner(line, cwd=str(brain), env=env, stdin_text=message(spec.snapshot, spec.inputs), timeout=TIMEOUT)
    result = parse(outcome.stdout)
    status = _status(outcome, result, outcome.stderr)
    usage = (result or {}).get("usage")
    used, context = session.input_tokens(usage), session.context_tokens(outcome.stdout, result)
    if result and isinstance(result.get("session_id"), str) and status != "rate_limited":
        # Chybná dávka (třeba ztracená relace) vynutí rotaci, aby se další dávka nezasekla na --resume.
        session.record(brain, result["session_id"], context if status == "ok" else session.ROTATE_AT + 1,
                       prompt_digest)
    total, by_model = (result or {}).get("total_cost_usd"), costs(result)
    own_session = (result or {}).get("session_id") or session_id
    cost, cost_by_model = batch_cost(total, by_model, previous_session_cost(brain, own_session) if resume else None)
    at = datetime.fromtimestamp(started, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"at": at, "project": spec.project,
             "workspace": spec.workspace, "status": status, "inputs": spec.inputs,
             "sessionId": own_session, "resumed": resume, "advisor": advisor, "brainPins": spec.skills.pins,
             "costUsd": cost, "costByModel": cost_by_model,
             "sessionCostUsd": total, "sessionCostByModel": by_model,
             "numTurns": (result or {}).get("num_turns"), "isError": bool((result or {}).get("is_error", True)),
             "durationMs": int((clock() - started) * 1000), "inputTokens": used, "summary": _summary(brain),
             "subCostUsd": sub_cost(brain, at), "contextTokens": context, **session.parts(usage)}
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
