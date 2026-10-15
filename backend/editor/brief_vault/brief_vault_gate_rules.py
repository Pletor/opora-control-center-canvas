"""Brány cyklu fragmentu bez databáze: pořadí, payloady, otisk vstupů a platnost (docs/schranka-neurony.md §3, §9).

Uložené brány jsou JSON ve sloupci `gates` revize: `{brána: {value, payload, by, actor, at, inputHash, revision}}`,
chybějící = vypnutá. `revision` je revize fragmentu, ve které záznam vznikl; vypnutá brána nechává záznam
`value: false` jako značku, od které revize platí nové návrhy (§9 bod 9). Platná je jen zapnutá brána se
shodným `inputHash` (sha256 názvu, textu a platné disciplíny, §9 bod 4) a se všemi předchozími branami platnými;
cokoli jiného se chová jako vypnuté a zapnutý záznam s jiným otiskem hlásí `gatesStale`.

Kolo fragmentu (`round_of`, §11): 1 + počet nových kol, tj. vypnutí `synthesized` (záznam `value: false`), kterému
od předchozího vypnutí předcházelo neúspěšné `verified` (`verified_outcome`, §13: `planApproved` false nebo `tests` fail). Počítá se z historie revizí (záznamy
podle své `revision`, opakované převzetí téhož záznamu se nepočítá dvakrát). Kolo se zvedne až začátkem nového
kola, ne samotným neúspěšným `verified`: `learned` neúspěšného kola tak ještě patří do fronty. Po `MAX_ROUNDS`
kolech je fragment vyčerpaný (`exhausted`) a čeká na člověka.

Spustitelná buňka (docs/schranka-bunka.md §3): `synthesized.checks?` = 1–4 kontroly `{id, command}` pevně určené před
výkonem, `verified.actual.run?` = doložený běh těchto kontrol od vnějšího ověřovatele. Tvar i pravidla buňky žijí
v `brief_vault_cell`; `validate_payload` z něj volá kontrolu tvaru.
"""

import hashlib
import json

from backend.editor.brief_vault.brief_vault_cell import validate_checks, validate_run

MAX_ROUNDS = 3
GATES = ("scoped", "weighed", "synthesized", "decided", "planned", "placed", "verified", "learned")
# Brány, které payload od klienta nemají (návrh nepotřebují); `planned`/`placed` payload vypočítá server.
NO_PAYLOAD = ("scoped", "planned", "placed")
# Brány plánu struktury (§4, §9 body 1–2): payload skládá server (`brief_vault_placement`), ne klient.
PLAN_GATES = ("planned", "placed")
MICROSTEP_TYPES = ("PIPELINE", "RETRIEVAL", "MEMORY", "TOOL", "ROUTING", "EVAL", "ENCRYPTION", "SCHEMA", "UI", "FLOW",
                   "API", "DATA", "INFRA", "DOC")
VERDICTS = ("yes", "other", "no")
LESSON_KINDS = ("pattern", "antipattern")
ENTRY_KEYS = {"value", "payload", "by", "actor", "at", "inputHash", "revision"}
# Volitelné kroky mikrokroku (bloky karty, §12) a vrstva karty, která přebije vrstvu z disciplíny (§2, §3).
SYNTH_REQUIRED, SYNTH_OPTIONAL = ("type", "done", "prediction"), ("steps", "layer", "nonGoals", "checks")
MAX_SYNTH_STEPS, MAX_STEP_CHARS, MAX_NON_GOALS, MAX_NON_GOAL_CHARS = 12, 300, 6, 200
VERIFIED_REQUIRED, VERIFIED_OPTIONAL = ("tests", "criticRounds", "unexpected"), ("planApproved", "planScore", "run")
CARD_LAYERS = ("frontend", "backend", "database")
HINTS = {
    "scoped": "Potvrď, že fragment patří projektu a své disciplíně (brána bez payloadu).",
    "weighed": "Zapiš přínos a riziko: {benefit ≤280, risk ≤280}.",
    "synthesized": "Navrhni typovaný mikrokrok: {type, done ≤500, prediction: {tests: pass|fail, criticRounds: 0–2, risk ≤280},"
                   " steps?: [1–12 kroků: text ≤300 nebo {text ≤300, condition ≤300}, jen v rozsahu done], layer?: frontend|backend|database, nonGoals?: [0–6 × ≤200 mimo rozsah],"
                   " checks?: [1–4 × {id, command ≤300}: python|py|uv|pytest|npm|npx|node bez shellu, cesty jen relativní s / a bez ..; určené před výkonem a v dalších kolech beze změny]}.",
    "decided": "Rozhodni: {verdict: yes|other|no, reason ≤500}; other vrátí fragment k mikrokroku, no = slepá ulička.",
    "planned": "Potvrď návrh struktury (brána bez payloadu): server sestaví oblast → sektor → karty, ověří je dryRun a uloží plán;"
               " po potvrzení planned hned potvrď placed (fronta placed nevrací).",
    "placed": "Vlož uložený plán na plátno (brána bez payloadu; zápis na plátno schvaluje člověk).",
    "verified": "Ověř výsledek proti předpovědi: {actual: {tests: pass|fail|untested, planApproved?: bool, planScore?: 0–10, criticRounds: 0–3, unexpected: bool,"
                " run?: {executor, verifier, checks: [{checkId, command, exitCode, durationMs, outputSha256}], at}}};"
                " má-li synthesized checks, tests pass/fail jen s run ze skutečného běhu (opora_cycle.py run-checks), jinak untested.",
    "learned": "Zapiš poučení do paměti disciplíny: {lesson ≤500, kind: pattern|antipattern};"
               " u buňky s checks po neúspěšném verified antipattern, po tests pass pattern.",
}


def _bad(message):
    from backend.editor.brief_vault.brief_vault_model import bad_request
    bad_request(message)


def input_hash(title, text, discipline):
    """Otisk vstupů brány: název + text + platná disciplína fragmentu (§9 bod 4)."""
    return hashlib.sha256(json.dumps([title, text, discipline], ensure_ascii=False).encode("utf-8")).hexdigest()


def gate_index(gate):
    if gate not in GATES:
        _bad("gate musí být jedna z " + ", ".join(GATES) + ".")
    return GATES.index(gate)


def _text(value, limit, label, allow_empty=False):
    if not isinstance(value, str) or "\0" in value or len(value) > limit or (not allow_empty and not value.strip()):
        _bad(f"{label} musí být neprázdný text do {limit} znaků.")
    return value


def _exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        _bad(f"{label} musí být objekt s poli {', '.join(keys)}.")
    return value


def _choice(value, allowed, label):
    if value not in allowed or not isinstance(value, str):
        _bad(f"{label} musí být jedna z {', '.join(allowed)}.")
    return value


def _count(value, high, label):
    if type(value) is not int or not 0 <= value <= high:
        _bad(f"{label} musí být celé číslo 0–{high}.")
    return value


def validate_payload(gate, payload):
    """Payload brány podle §3 (přesná pole, limity znaků, výčty, typ mikrokroku); vrací ho beze změny. 400 = chyba."""
    gate_index(gate)
    if gate in NO_PAYLOAD:
        if payload is not None:
            _bad(f"brána {gate} payload nemá.")
        return None
    if gate == "weighed":
        _exact(payload, ("benefit", "risk"), "payload weighed")
        _text(payload["benefit"], 280, "benefit")
        _text(payload["risk"], 280, "risk")
    elif gate == "synthesized":
        if not isinstance(payload, dict) or not set(SYNTH_REQUIRED) <= set(payload)                 or set(payload) - set(SYNTH_REQUIRED) - set(SYNTH_OPTIONAL):
            _bad("payload synthesized musí být objekt s poli type, done, prediction a volitelně steps, layer, nonGoals, checks.")
        if "checks" in payload:
            validate_checks(payload["checks"])
        if "steps" in payload:
            steps = payload["steps"]
            if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_SYNTH_STEPS:
                _bad(f"steps musí být pole 1–{MAX_SYNTH_STEPS} kroků.")
            for step in steps:
                if isinstance(step, dict):
                    _exact(step, ("text", "condition"), "krok ve steps")
                    _text(step["text"], MAX_STEP_CHARS, "text kroku ve steps")
                    _text(step["condition"], MAX_STEP_CHARS, "condition kroku ve steps")
                else:
                    _text(step, MAX_STEP_CHARS, "krok ve steps")
        if "nonGoals" in payload:
            goals = payload["nonGoals"]
            if not isinstance(goals, list) or len(goals) > MAX_NON_GOALS:
                _bad(f"nonGoals musí být pole 0–{MAX_NON_GOALS} textů.")
            for goal in goals:
                _text(goal, MAX_NON_GOAL_CHARS, "položka nonGoals")
        if "layer" in payload:
            _choice(payload["layer"], CARD_LAYERS, "layer")
        _choice(payload["type"], MICROSTEP_TYPES, "type")
        _text(payload["done"], 500, "done")
        prediction = _exact(payload["prediction"], ("tests", "criticRounds", "risk"), "prediction")
        _choice(prediction["tests"], ("pass", "fail"), "prediction.tests")
        _count(prediction["criticRounds"], 2, "prediction.criticRounds")
        _text(prediction["risk"], 280, "prediction.risk")
    elif gate == "decided":
        _exact(payload, ("verdict", "reason"), "payload decided")
        _choice(payload["verdict"], VERDICTS, "verdict")
        _text(payload["reason"], 500, "reason")
    elif gate == "verified":
        actual = _exact(payload, ("actual",), "payload verified")["actual"]
        if not isinstance(actual, dict) or not set(VERIFIED_REQUIRED) <= set(actual)                 or set(actual) - set(VERIFIED_REQUIRED) - set(VERIFIED_OPTIONAL):
            _bad("actual musí být objekt s poli tests, criticRounds, unexpected a volitelně planApproved, planScore, run.")
        if "run" in actual:
            validate_run(actual["run"])
        _choice(actual["tests"], ("pass", "fail", "untested"), "actual.tests")
        if "planApproved" in actual and type(actual["planApproved"]) is not bool:
            _bad("actual.planApproved musí být true nebo false.")
        if "planScore" in actual:
            _count(actual["planScore"], 10, "actual.planScore")
        _count(actual["criticRounds"], 3, "actual.criticRounds")
        if type(actual["unexpected"]) is not bool:
            _bad("actual.unexpected musí být true nebo false.")
    elif gate == "learned":
        _exact(payload, ("lesson", "kind"), "payload learned")
        _text(payload["lesson"], 500, "lesson")
        _choice(payload["kind"], LESSON_KINDS, "kind")
    return payload


def verified_outcome(actual):
    """Výsledek `verified` (§13): `(planApproved, failed)`. Bez `planApproved` platí `tests == "pass"`;
    neúspěch = plán neschválen nebo testy `fail`."""
    actual = actual if isinstance(actual, dict) else {}
    approved = actual["planApproved"] if type(actual.get("planApproved")) is bool else actual.get("tests") == "pass"
    return approved, approved is False or actual.get("tests") == "fail"


def prediction_error(prediction, actual):
    """`e = (t + r + u) / 3` z §3, zaokrouhleno na dvě desetinná místa (0–1).
    `t`: při `untested` se `planApproved` porovná s předpovědí (`prediction.tests == "pass"` = plán projde)."""
    if actual["tests"] == "untested":
        t = 1 if verified_outcome(actual)[0] != (prediction["tests"] == "pass") else 0
    else:
        t = 1 if actual["tests"] != prediction["tests"] else 0
    r = min(abs(actual["criticRounds"] - prediction["criticRounds"]), 2) / 2
    u = 1 if actual["unexpected"] else 0
    return round((t + r + u) / 3, 2)


def parse_gates(raw):
    """Uložené brány revize {brána: záznam}; NULL nebo poškozený JSON = žádné brány."""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def stored_gates_valid(raw):
    """Tvar sloupce `gates` pro zápis revize i uloženou verzi plátna."""
    if raw is None:
        return True
    if not isinstance(raw, str):
        return False
    try:
        value = json.loads(raw)
    except ValueError:
        return False
    return isinstance(value, dict) and all(
        gate in GATES and isinstance(entry, dict) and set(entry) == ENTRY_KEYS and type(entry["value"]) is bool
        and type(entry["revision"]) is int for gate, entry in value.items())


def encode_gates(entries):
    """Kanonický JSON bran v pořadí cyklu; prázdné = NULL."""
    ordered = {gate: entries[gate] for gate in GATES if gate in entries}
    return json.dumps(ordered, ensure_ascii=False, sort_keys=False) if ordered else None


def gate_state(row, discipline):
    """Platné brány revize: {entries, on (prefix platných bran), stale, hash, next}."""
    entries = parse_gates(row.get("gates"))
    current = input_hash(row["title"], row["text"], discipline)
    on, stale = [], False
    for gate in GATES:
        entry = entries.get(gate)
        valid = bool(entry) and entry.get("value") is True and entry.get("inputHash") == current
        if entry and entry.get("value") is True and entry.get("inputHash") != current:
            stale = True
        if not valid or len(on) != GATES.index(gate):
            continue
        on.append(gate)
    return {"entries": entries, "on": on, "stale": stale, "hash": current,
            "next": GATES[len(on)] if len(on) < len(GATES) else None}


def dead_end(state):
    """`decided` platně zapnutá s verdiktem `no` (slepá ulička)."""
    return "decided" in state["on"] and (state["entries"]["decided"].get("payload") or {}).get("verdict") == "no"


def summary(state):
    """Brány pro strom a odpověď zápisu: jen booleany a `predictionError`, `gateStep`, `gatesStale`."""
    gates = {gate: gate in state["on"] for gate in GATES}
    verified = state["entries"].get("verified") if "verified" in state["on"] else None
    gates["predictionError"] = (verified.get("payload") or {}).get("predictionError") if verified else None
    return {"gates": gates, "gateStep": len(state["on"]), "gatesStale": state["stale"], "deadEnd": dead_end(state)}


def detail(state):
    """Brány pro detail fragmentu: záznamy s payloadem a příznakem, zda platí."""
    return {gate: {**entry, "valid": gate in state["on"]} for gate, entry in state["entries"].items()}


def round_of(history):
    """Kolo fragmentu z uložených bran jeho revizí (`gates` JSON v pořadí revizí), viz docstring modulu."""
    events = set()
    for raw in history:
        entries = parse_gates(raw)
        verified, synthesized = entries.get("verified"), entries.get("synthesized")
        if isinstance(verified, dict) and verified.get("value") is True and isinstance(verified.get("payload"), dict)                 and verified_outcome(verified["payload"].get("actual"))[1]:
            events.add((verified.get("revision", 0), 0))
        if isinstance(synthesized, dict) and synthesized.get("value") is False:
            events.add((synthesized.get("revision", 0), 1))
    rounds, failed = 1, False
    for _revision, kind in sorted(events):
        if kind == 0:
            failed = True
        elif failed:
            rounds, failed = rounds + 1, False
    return rounds


def round_fields(rounds, fragment_id):
    """`round` a `exhausted` fragmentu pro strom, detail a frontu (`rounds` = {id: kolo}, chybějící = 1)."""
    number = (rounds or {}).get(fragment_id, 1)
    return {"round": number, "exhausted": number > MAX_ROUNDS}
