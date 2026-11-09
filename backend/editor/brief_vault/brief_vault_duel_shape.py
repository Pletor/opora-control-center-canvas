"""Tvar a odvozený stav duelu a představy Schránky (docs/schranka-duel.md §1–§3).

Duel je fragment `kind: "duel"`, představa fragment `kind: "vision"`; jejich stav nese `brief_fragment_details`
(`fields.duel`, `fields.vision`), takže nevzniká tabulka ani migrace. `validate_duel` a `validate_vision` hlídají
uložený tvar (zápis i obnova verze plátna přes `validate_details`); pravidla tahů hlídá `brief_vault_duel`.
`duel_state` skládá z uloženého stavu matematiku (`brief_vault_duel_math`): P(B > A), kdo je na tahu, kola stran
a zda už jde rozhodnout. `open_duels` vrací otevřené duely prostoru pro frontu `/next`.
"""

from backend.editor.brief_vault.brief_vault_duel_delegation import ROLES, participant
from backend.editor.brief_vault.brief_vault_duel_math import (
    MAX_ROUNDS,
    decide,
    duel_probability,
    on_turn,
    rounds,
)
from backend.editor.brief_vault.brief_vault_model import fail, text_of

SUBJECT_KINDS = ("fragment", "node", "project")
SIDES = ("A", "B", "human", "judge")
TURN_KINDS = ("claim", "grill", "answer", "concede", "synthesis", "note")
STATUSES = ("open", "grill", "synthesis", "decided")
OUTCOMES = ("keep", "adopt", "synthesis")
MAX_DIRECTION, MAX_TURN_TEXT, MAX_SOURCE, MAX_QUOTE, MAX_EVIDENCE = 4000, 2000, 500, 200, 6
DEFENDED_AT = 6
MAX_REFS, MAX_TURNS, MAX_SCORES, MAX_POINTS, MAX_REASON, MAX_POINT_NOTE = 20, 300, 2000, 2000, 500, 500
DUEL_KEYS = {"subject", "incumbent", "challenger", "turns", "scores", "status", "decision"}
TURN_KEYS = {"id", "side", "kind", "text", "refs", "evidence", "by", "actor", "at"}
SCORE_KEYS = {"id", "turnId", "judge", "strength", "supports", "actor", "at"}
DECISION_KEYS = {"outcome", "text", "p", "by", "actor", "at"}
POINT_KEYS = {"score", "note", "by", "actor", "at"}


def _keys(value, required, optional, label):
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional:
        fail(f"{label} má pole {', '.join(sorted(required))}" + (f" a volitelně {', '.join(sorted(optional))}." if optional else "."))
    return value


def _score_value(value, label):
    if type(value) is not int or not 0 <= value <= 10:
        fail(f"{label} musí být celé číslo 0 až 10.")
    return value


def _signed(value, label):
    text_of(value["by"], 120, f"{label}.by")
    text_of(value["actor"], 20, f"{label}.actor")
    text_of(value["at"], 40, f"{label}.at", allow_empty=False)


def _delegated(value):
    if "delegateRole" not in value and "principalSessionId" not in value:
        return
    if not isinstance(value.get("delegateRole"), str) or value["delegateRole"] not in ROLES:
        fail("Invalid delegated role.")
    text_of(value.get("principalSessionId"), 200, "principalSessionId", allow_empty=False)


def _subject(value):
    _keys(value, {"kind", "id"}, set(), "subject")
    if value["kind"] not in SUBJECT_KINDS:
        fail("subject.kind musí být fragment, node nebo project.")
    text_of(value["id"], 200, "subject.id", allow_empty=False)


def _turn(turn):
    _keys(turn, TURN_KEYS, {"delegateRole", "principalSessionId"}, "výměna duelu")
    _delegated(turn)
    if turn["side"] not in SIDES or turn["kind"] not in TURN_KINDS:
        fail("výměna duelu má neplatnou stranu nebo druh.")
    text_of(turn["id"], 64, "turn.id", allow_empty=False)
    text_of(turn["text"], MAX_TURN_TEXT, "turn.text", allow_empty=False)
    if not isinstance(turn["refs"], list) or len(turn["refs"]) > MAX_REFS or any(not isinstance(ref, str) for ref in turn["refs"]):
        fail(f"turn.refs je pole nejvýše {MAX_REFS} id výměn.")
    if not isinstance(turn["evidence"], list) or len(turn["evidence"]) > MAX_EVIDENCE:
        fail(f"turn.evidence je pole nejvýše {MAX_EVIDENCE} doložení.")
    for item in turn["evidence"]:
        _keys(item, {"source", "quote"}, set(), "doložení")
        text_of(item["source"], MAX_SOURCE, "evidence.source", allow_empty=False)
        text_of(item["quote"], MAX_QUOTE, "evidence.quote")
    _signed(turn, "turn")


def _score(score):
    _keys(score, SCORE_KEYS, {"rebuttedBy", "evidenceOk", "delegateRole", "principalSessionId"}, "skóre duelu")
    _delegated(score)
    if "evidenceOk" in score and type(score["evidenceOk"]) is not bool:
        fail("score.evidenceOk musí být true nebo false.")
    _score_value(score["strength"], "strength")
    if score["supports"] not in ("A", "B"):
        fail("supports musí být A nebo B.")
    for key in ("id", "turnId", "rebuttedBy"):
        if key in score:
            text_of(score[key], 64, f"score.{key}", allow_empty=False)
    text_of(score["judge"], 120, "score.judge", allow_empty=False)
    text_of(score["actor"], 20, "score.actor")
    text_of(score["at"], 40, "score.at", allow_empty=False)


def _decision(value):
    _keys(value, DECISION_KEYS, {"override", "synthesisTurnId", "applied", "appliedRevision", "reason"}, "decision")
    if "applied" in value and type(value["applied"]) is not bool:
        fail("decision.applied musí být true nebo false.")
    if value.get("appliedRevision") is not None and (type(value["appliedRevision"]) is not int or value["appliedRevision"] < 1):
        fail("decision.appliedRevision musí být kladné celé číslo nebo null.")
    if "reason" in value:
        text_of(value["reason"], MAX_REASON, "decision.reason", allow_empty=False)
    if value["outcome"] not in OUTCOMES:
        fail("decision.outcome musí být keep, adopt nebo synthesis.")
    text_of(value["text"], MAX_DIRECTION, "decision.text")
    if not isinstance(value["p"], int | float) or not 0 <= value["p"] <= 1:
        fail("decision.p musí být pravděpodobnost 0 až 1.")
    _signed(value, "decision")
    if "override" in value:
        _keys(value["override"], {"reason", "ruleOutcome"}, set(), "decision.override")
        text_of(value["override"]["reason"], MAX_REASON, "override.reason", allow_empty=False)
        if value["override"]["ruleOutcome"] not in (*OUTCOMES, None):
            fail("override.ruleOutcome musí být výsledek pravidla nebo null.")


def validate_duel(value):
    """Uložený stav duelu (`fields.duel`); vrací ho beze změny."""
    _keys(value, DUEL_KEYS, {"visionRef", "delegation"}, "duel")
    if "delegation" in value:
        owner = _keys(value["delegation"], {"mode", "principal", "sessionId"}, set(), "delegation")
        if owner["mode"] != "single-principal-role-simulation":
            fail("Invalid delegation mode.")
        text_of(owner["principal"], 120, "principal", allow_empty=False)
        text_of(owner["sessionId"], 200, "sessionId", allow_empty=False)
    if "visionRef" in value:
        ref = _keys(value["visionRef"], {"fragmentId", "revision"}, set(), "visionRef")
        text_of(ref["fragmentId"], 64, "visionRef.fragmentId", allow_empty=False)
        if type(ref["revision"]) is not int or ref["revision"] < 1:
            fail("visionRef.revision musí být kladné celé číslo.")
    _subject(value["subject"])
    _keys(value["incumbent"], {"text"}, {"ref"}, "incumbent")
    text_of(value["incumbent"]["text"], MAX_DIRECTION, "incumbent.text", allow_empty=False)
    if "ref" in value["incumbent"]:
        ref = _keys(value["incumbent"]["ref"], {"fragmentId", "revision"}, set(), "incumbent.ref")
        if type(ref["revision"]) is not int or ref["revision"] < 1:
            fail("incumbent.ref.revision musí být kladné celé číslo.")
    _keys(value["challenger"], {"text", "by", "actor", "at"}, {"delegateRole", "principalSessionId"}, "challenger")
    _delegated(value["challenger"])
    text_of(value["challenger"]["text"], MAX_DIRECTION, "challenger.text", allow_empty=False)
    _signed(value["challenger"], "challenger")
    if not isinstance(value["turns"], list) or len(value["turns"]) > MAX_TURNS:
        fail(f"duel má nejvýše {MAX_TURNS} výměn.")
    if not isinstance(value["scores"], list) or len(value["scores"]) > MAX_SCORES:
        fail(f"duel má nejvýše {MAX_SCORES} skóre.")
    for turn in value["turns"]:
        _turn(turn)
    for score in value["scores"]:
        _score(score)
    for item in [value["challenger"], *value["turns"], *value["scores"]]:
        owner = value.get("delegation")
        if owner:
            if (item.get("by", item.get("judge")) != owner["principal"] or item["actor"] != "agent"
                    or item.get("principalSessionId") != owner["sessionId"] or item.get("delegateRole") not in ROLES):
                fail("Delegated participant must retain the recorded principal and session.")
            expected = item.get("side", "judge" if "judge" in item else "B")
            if ROLES[item["delegateRole"]] != expected:
                fail("Delegated participant role does not match side.")
        elif "delegateRole" in item or "principalSessionId" in item:
            fail("Role metadata requires explicit duel delegation.")
    if value["status"] not in STATUSES:
        fail("duel.status musí být open, grill, synthesis nebo decided.")
    if (value["status"] == "decided") != (value["decision"] is not None):
        fail("rozhodnutý duel nese decision, otevřený ne.")
    if value["decision"] is not None:
        _decision(value["decision"])
    return value


def validate_vision(value):
    """Uložená představa (`fields.vision`): body trajektorie shody platného směru s představou."""
    _keys(value, {"points"}, {"directionRevision"}, "vision")
    if "directionRevision" in value and (type(value["directionRevision"]) is not int or value["directionRevision"] < 1):
        fail("vision.directionRevision musí být kladné celé číslo.")
    if not isinstance(value["points"], list) or len(value["points"]) > MAX_POINTS:
        fail(f"vision.points je pole nejvýše {MAX_POINTS} bodů.")
    for point in value["points"]:
        _keys(point, POINT_KEYS, {"duelId", "visionRevision"}, "bod trajektorie")
        if "visionRevision" in point and (type(point["visionRevision"]) is not int or point["visionRevision"] < 1):
            fail("point.visionRevision musí být kladné celé číslo.")
        _score_value(point["score"], "score")
        text_of(point["note"], MAX_POINT_NOTE, "point.note", allow_empty=False)
        _signed(point, "point")
        if "duelId" in point:
            text_of(point["duelId"], 64, "point.duelId", allow_empty=False)
    return value


def parties(duel):
    """Aktéři stran {A: {by}, B: {by}}; autor challengeru patří ke straně B. `note` za stranu není argument, aktéra
    ke straně nepřipíše (soudce smí za stranu psát jen note, docs/schranka-duel.md §2)."""
    found = {"A": set(), "B": {participant(duel["challenger"])}}
    for turn in duel["turns"]:
        if turn["side"] in found and turn["kind"] != "note":
            found[turn["side"]].add(participant(turn))
    return found


def defended_syntheses(duel):
    """Obhájené syntézy {turnId: průměrná síla}: výměna `synthesis`, kterou ohodnotil aspoň jeden soudce mimo strany
    s průměrnou silou ≥ `DEFENDED_AT` (docs/schranka-duel.md §3.2)."""
    sides = parties(duel)
    inside = sides["A"] | sides["B"]
    found = {}
    for turn in duel["turns"]:
        if turn["kind"] != "synthesis":
            continue
        values = [score["strength"] for score in duel["scores"]
                  if score["turnId"] == turn["id"] and participant(score) not in inside]
        if values and sum(values) / len(values) >= DEFENDED_AT:
            found[turn["id"]] = sum(values) / len(values)
    return found


def duel_state(duel):
    """Odvozený stav: P(B > A) s rozpadem, kdo je na tahu, kola stran a zda už jde rozhodnout (pravidlem)."""
    probability = duel_probability(duel["turns"], duel["scores"])
    waiting = on_turn(duel["turns"])
    played = {side: rounds(duel["turns"], side) for side in ("A", "B")}
    exhausted = all(count >= MAX_ROUNDS for count in played.values())
    ruled = decide(probability, len(waiting), exhausted)
    return {"probability": probability, "onTurn": waiting, "rounds": played, "roundsExhausted": exhausted,
            "rule": ruled, "canDecide": duel["status"] != "decided" and ruled["outcome"] is not None}


def summary(duel):
    """Malý výtah duelu do stromu: stav, předmět, počty, P(B > A) (u rozhodnutého z rozhodnutí) a výsledek."""
    decision = duel["decision"]
    p = decision["p"] if decision else duel_probability(duel["turns"], duel["scores"])["p"]
    return {"status": duel["status"], "subject": dict(duel["subject"]), "turns": len(duel["turns"]),
            "scores": len(duel["scores"]), "p": p, "outcome": (decision or {}).get("outcome"),
            **({"delegation": dict(duel["delegation"])} if "delegation" in duel else {})}


def open_duels(rows, details, live):
    """Otevřené (nerozhodnuté) živé duely prostoru [(řádek, duel)] seřazené podle otevření."""
    found = []
    for fragment_id in live:
        row = rows[fragment_id]
        duel = (details.get(fragment_id) or {}).get("duel")
        if row["kind"] == "duel" and duel and duel["status"] != "decided":
            found.append((row, duel))
    found.sort(key=lambda item: (item[1]["challenger"]["at"], item[0]["fragment_id"]))
    return found
