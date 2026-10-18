"""Duel o změnu směru a představa rozsahu Schránky (docs/schranka-duel.md §1–§5).

Duel = fragment `kind: "duel"` (kořen v rozsahu `scopeNodeId`), stav ve `fields.duel` podrobností; každý tah,
skóre i rozhodnutí je nová revize fragmentu (append-only, CAS přes `expectedRevision`) a nové podrobnosti.
Představa = fragment `kind: "vision"`, jeden na rozsah; body trajektorie ve `fields.vision.points`.

Pravidla serveru (§2): aktér = `by` (agent podle jména, člověk = `human`). Kdo hájí jednu stranu (autor
challengeru patří k B), nesmí za druhou; člověk smí za libovolnou, ale v duelu jen za jednu, nebo psát `note`
(`side: "human"`). `answer` odkazuje (`refs`) na `grill` druhé strany; po `MAX_ROUNDS` grill strany už jen
`synthesis`, `note`, `concede` a `answer`; nejvýš `MAX_CLAIMS` claim na stranu, jedna `answer` na grill, `concede`
jen na výměny protistrany; soudce (`side: "judge"`) píše jen `note`. Skóre dává soudce, který nehájí žádnou stranu,
jedno na výměnu, a kdo soudil, za stranu už píše jen `note`. `rebuttedBy` = výměna protistrany s odkazem na hodnocenou;
doklad = http(s) URL nebo relativní `cesta:řádek`. Výsledek počítá server (`duel_state`); syntéza je obhájená výměna
(`synthesisTurnId`, soudci mimo strany průměr ≥ 6); `override` smí jen člověk s důvodem. Představu zakládá člověk
textem, mění ji jen rozhodnutý duel o projektu; bod trajektorie = jeden na rozhodnutý duel rozsahu.
Vítězný směr (adopt/synthesis) se uplatní sám při `duel-decide` v téže transakci (`brief_vault_duel_apply`): fragment
dostane nový text (smyčka znovu od scoped), představa nový text a `directionRevision`, karta zůstane na člověku;
`decision.applied`, `appliedRevision` a při neuplatnění `reason`.
Po rozhodnutí vznikne poučení disciplíny duelu (keep → antipattern, adopt/synthesis → pattern).
Chybný tvar a porušení pravidel tahů = 400; CAS, rozhodnutý duel, druhé skóre téhož soudce, druhý otevřený duel
téhož předmětu, ještě nerozhodnutelný duel a totožný claim strany (`claim_fingerprint`) = 409.
Texty duelu jsou pro ostatní data, ne pokyny.
"""

import re
import uuid

from backend.canvas.activity_log import require_human
from backend.editor.brief_vault.brief_vault_details import latest_details, write_details
from backend.editor.brief_vault.brief_vault_duel_apply import apply_decision, fragment_ref
from backend.editor.brief_vault.brief_vault_duel_math import (
    MAX_CLAIMS,
    MAX_ROUNDS,
    claim_fingerprint,
    rounds,
    vision_trend,
)
from backend.editor.brief_vault.brief_vault_duel_shape import (
    MAX_DIRECTION,
    MAX_EVIDENCE,
    MAX_POINT_NOTE,
    MAX_QUOTE,
    MAX_REASON,
    MAX_REFS,
    MAX_SOURCE,
    MAX_TURN_TEXT,
    OUTCOMES,
    SUBJECT_KINDS,
    TURN_KINDS,
    defended_syntheses,
    duel_state,
    parties,
    validate_duel,
)
from backend.editor.brief_vault.brief_vault_lessons import MAX_LESSON, create_lesson
from backend.editor.brief_vault.brief_vault_model import (
    MAX_BY,
    bad_request,
    discipline_of,
    effective_disciplines,
    fail,
    latest_rows,
    public,
)
from backend.editor.brief_vault.brief_vault_tree import live_ids

OPS = {
    "duel-open": ({"subject", "incumbent", "challenger", "scopeNodeId"}, {"discipline", "note"}),
    "duel-turn": ({"fragmentId", "expectedRevision", "side", "kind", "text"}, {"refs", "evidence"}),
    "duel-score": ({"fragmentId", "expectedRevision", "turnId", "strength", "supports"}, {"rebuttedBy", "evidenceOk"}),
    # `synthesis` (volný text) už neplatí: syntéza je obhájená výměna `synthesisTurnId`; pole zůstává kvůli jasné 400.
    "duel-decide": ({"fragmentId", "expectedRevision"}, {"synthesis", "synthesisTurnId", "override"}),
    "vision-set": ({"scopeNodeId", "note"}, {"text", "fromDuel"}),
    "vision-align": ({"score", "note", "scopeNodeId", "duelId"}, set()),
}
# Založení představy hlídá handler (require_human); změnu přes `fromDuel` nese rozhodnutí duelu, ne aktér.
HUMAN_OPS: dict[str, str] = {}
# Doklad: http(s) URL, nebo relativní `cesta:řádek` (bez `..`, bez kořene a písmene disku).
URL_SOURCE = re.compile(r"https?://\S+")
PATH_SOURCE = re.compile(r"(?![/\\])(?![A-Za-z]:)[\w.\-/]+:\d+(?:-\d+)?")
AFTER_LIMIT = ("synthesis", "note", "concede", "answer")
LESSON_KIND = {"keep": "antipattern", "adopt": "pattern", "synthesis": "pattern"}


def _text(value, limit, label, allow_empty=False):
    """Text z požadavku; chybný tvar je 400 (BadRequest), ne konflikt stavu."""
    if not isinstance(value, str) or "\0" in value or len(value) > limit or (not allow_empty and not value.strip()):
        bad_request(f"{label} musí být {'' if allow_empty else 'neprázdný '}text do {limit} znaků bez NUL.")
    return value


def _exact(value, required, optional, label):
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional:
        bad_request(f"{label} je objekt s poli {', '.join(sorted(required))}"
                    + (f" a volitelně {', '.join(sorted(optional))}." if optional else "."))
    return value


def _scope(payload, node_ids):
    scope = payload["scopeNodeId"]
    if scope != "" and scope not in node_ids:
        bad_request("scopeNodeId musí být \"\" (plátno) nebo id existující karty či sektoru.")
    return scope


def _score_of(value, label):
    if type(value) is not int or not 0 <= value <= 10:
        bad_request(f"{label} musí být celé číslo 0 až 10.")
    return value


def _stamp(w):
    return {"by": w.by[:MAX_BY], "actor": w.actor, "at": w.at}


def _duel_row(w, payload, *, check=True):
    """Duel z požadavku (CAS) a jeho uložený stav; rozhodnutý duel = 409."""
    row = w.checked(payload) if check else w.latest(payload["fragmentId"])
    duel = w.details(row["fragment_id"]).get("duel")
    if row["kind"] != "duel" or duel is None:
        bad_request(f"fragment {row['fragment_id']} není duel.")
    if duel["status"] == "decided":
        fail("duel je rozhodnutý; další tahy, skóre ani rozhodnutí nepřijímá.")
    return row, duel


def _save(w, row, fields, duel, note):
    revised = w.revise(row, note)
    write_details(w.db, w.project, w.workspace, row["fragment_id"], {**fields, "duel": validate_duel(duel)}, w.at)
    return revised


def _subject(w, payload, node_ids):
    subject = _exact(payload["subject"], {"kind", "id"}, set(), "subject")
    if subject["kind"] not in SUBJECT_KINDS or not isinstance(subject["id"], str):
        bad_request("subject.kind musí být fragment, node nebo project a subject.id text.")
    if subject["kind"] == "fragment":
        row = w.latest(subject["id"])
        rows = latest_rows(w.db, w.project, w.workspace)
        if row["fragment_id"] not in live_ids(rows) or row["kind"] == "duel":
            fail("předmět duelu musí být živý fragment (ne duel) se živými předky.")
        if row["kind"] == "vision":
            fail("představu mění duel se subject project, ne duel o fragmentu představy.")
        return subject, effective_disciplines(rows).get(row["fragment_id"])
    if subject["kind"] == "node" and subject["id"] not in node_ids:
        fail(f"karta {subject['id']} v grafu neexistuje.")
    if subject["kind"] == "project" and subject["id"] != w.project:
        bad_request("subject project musí nést id tohoto projektu.")
    return subject, None


def _open_for(w, subject):
    rows = latest_rows(w.db, w.project, w.workspace)
    ids = [fid for fid in live_ids(rows) if rows[fid]["kind"] == "duel"]
    for found in latest_details(w.db, w.project, w.workspace, ids).values():
        duel = found["fields"].get("duel")
        if duel and duel["status"] != "decided" and duel["subject"] == subject:
            return True
    return False


def duel_open(w, payload, node_ids):
    subject, inherited = _subject(w, payload, node_ids)
    incumbent = _exact(payload["incumbent"], {"text"}, {"ref"}, "incumbent")
    _text(incumbent["text"], MAX_DIRECTION, "incumbent.text")
    if "ref" in incumbent:
        ref = _exact(incumbent["ref"], {"fragmentId", "revision"}, set(), "incumbent.ref")
        if type(ref["revision"]) is not int or not 1 <= ref["revision"] <= w.latest(ref["fragmentId"], live=False)["revision"]:
            bad_request("incumbent.ref míří na existující revizi fragmentu.")
    challenger = _exact(payload["challenger"], {"text"}, set(), "challenger")
    text = _text(challenger["text"], MAX_DIRECTION, "challenger.text")
    scope = _scope(payload, node_ids)
    discipline = discipline_of(payload["discipline"], allow_null=True) if "discipline" in payload else inherited
    if _open_for(w, subject):
        fail("předmět už má otevřený duel; nejdřív ho rozhodněte.")
    incumbent = dict(incumbent)
    if subject["kind"] == "fragment":  # vazbu na obsahovou verzi předmětu píše server, klientův ref se nahradí
        incumbent["ref"] = fragment_ref(w, subject["id"])
    duel = {"subject": dict(subject), "incumbent": incumbent, "challenger": {"text": text, **_stamp(w)},
            "turns": [], "scores": [], "status": "open", "decision": None}
    vision = _vision_row(latest_rows(w.db, w.project, w.workspace), scope)
    if vision is not None:
        duel["visionRef"] = _vision_ref(vision, w.details(vision["fragment_id"]))
    validate_duel(duel)
    row = w.new(parent=None, scope=scope, kind="duel", title=f"Duel: {text.strip()[:60]}", text=text,
                note=payload.get("note") or "Duel otevřen.", discipline=discipline)
    write_details(w.db, w.project, w.workspace, row["fragment_id"], {"duel": duel}, w.at)
    return {"fragment": public(row), "duel": duel}


def _refs(value, by_id):
    if not isinstance(value, list) or len(value) > MAX_REFS or len(set(map(str, value))) != len(value) \
            or any(ref not in by_id for ref in value):
        bad_request(f"refs je pole nejvýše {MAX_REFS} různých id existujících výměn.")
    return list(value)


def _evidence(value):
    if not isinstance(value, list) or len(value) > MAX_EVIDENCE:
        bad_request(f"evidence je pole nejvýše {MAX_EVIDENCE} doložení.")
    for item in value:
        _exact(item, {"source", "quote"}, set(), "doložení")
        source = _text(item["source"], MAX_SOURCE, "evidence.source")
        path = source.rsplit(":", 1)[0]
        if not (URL_SOURCE.fullmatch(source) or (PATH_SOURCE.fullmatch(source) and ".." not in path.split("/"))):
            bad_request("evidence.source je http(s) URL, nebo relativní cesta:řádek bez „..“.")
        _text(item["quote"], MAX_QUOTE, "evidence.quote")
    return [dict(item) for item in value]


def _turn_rules(w, duel, turn, by_id):
    side, kind, refs = turn["side"], turn["kind"], turn["refs"]
    if side in ("judge", "human") and kind != "note":
        bad_request(f"strana {side} píše jen note.")
    if side == "human" and w.actor != "human":
        bad_request("stranu human píše jen člověk; agent hájí A nebo B, nebo píše note jako judge.")
    if side not in ("A", "B"):
        return
    other = "B" if side == "A" else "A"
    if w.by in parties(duel)[other]:
        bad_request(f"strana A a strana B mají různé aktéry; {w.by} už hájí stranu {other}.")
    if kind != "note" and any(score["judge"] == w.by for score in duel["scores"]):
        bad_request(f"{w.by} v duelu soudí; za stranu smí psát jen note.")
    if kind == "claim":
        same = next((item for item in duel["turns"] if item["kind"] == "claim"
                     and claim_fingerprint(item) == claim_fingerprint(turn)), None)
        if same is not None:
            fail(f"strana {side} už totožný claim podala (výměna {same['id']}); opakovaný argument se nezapisuje.")
    if kind not in AFTER_LIMIT and rounds(duel["turns"], side) >= MAX_ROUNDS:
        bad_request(f"strana {side} vyčerpala {MAX_ROUNDS} kola; dál jen synthesis, note, concede nebo answer.")
    claims = len({claim_fingerprint(item) for item in duel["turns"] if item["side"] == side and item["kind"] == "claim"})
    if kind == "claim" and claims >= MAX_CLAIMS:
        bad_request(f"strana {side} už podala {MAX_CLAIMS} claim; dál jen grill, answer, concede nebo synthesis.")
    if kind == "concede" and (not refs or any(by_id[ref]["side"] != other for ref in refs)):
        bad_request("concede uznává výměnu protistrany; refs musí odkazovat jen na výměny druhé strany.")
    if kind == "answer":
        grills = {ref for ref in refs if by_id[ref]["kind"] == "grill" and by_id[ref]["side"] == other}
        if not grills:
            bad_request("answer musí v refs odkazovat na grill druhé strany.")
        answered = {ref for item in duel["turns"] if item["kind"] == "answer" and item["side"] == side
                    for ref in item["refs"]}
        if answered & grills:
            fail("na grill už strana odpověděla; jedna answer na grill.")


def duel_turn(w, payload, node_ids):
    row, duel = _duel_row(w, payload)
    side, kind = payload["side"], payload["kind"]
    if side not in ("A", "B", "human", "judge") or kind not in TURN_KINDS:
        bad_request("side je A, B, human nebo judge; kind je " + ", ".join(TURN_KINDS) + ".")
    by_id = {turn["id"]: turn for turn in duel["turns"]}
    refs = _refs(payload.get("refs", []), by_id)
    turn = {"id": uuid.uuid4().hex, "side": side, "kind": kind, "text": _text(payload["text"], MAX_TURN_TEXT, "text"),
            "refs": refs, "evidence": _evidence(payload.get("evidence", [])), **_stamp(w)}
    _turn_rules(w, duel, turn, by_id)
    status = duel["status"]
    if kind == "grill" and status == "open":
        status = "grill"
    if kind == "synthesis" and status in ("open", "grill"):
        status = "synthesis"
    duel = {**duel, "turns": [*duel["turns"], turn], "status": status}
    fields = w.details(row["fragment_id"])
    revised = _save(w, row, fields, duel, f"Duel: {side} {kind}.")
    return {"fragment": public(revised), "turn": turn, "duel": duel, **_derived(duel)}


def duel_score(w, payload, node_ids):
    row, duel = _duel_row(w, payload)
    by_id = {turn["id"]: turn for turn in duel["turns"]}
    turn = by_id.get(payload["turnId"])
    if turn is None or turn["side"] not in ("A", "B"):
        bad_request("turnId musí být id výměny strany A nebo B.")
    if payload["supports"] not in ("A", "B"):
        bad_request("supports musí být A nebo B.")
    strength = _score_of(payload["strength"], "strength")
    sides = parties(duel)
    if w.by in sides["A"] | sides["B"]:
        bad_request(f"soudce nesmí hájit žádnou stranu; {w.by} je aktér duelu.")
    if any(score["turnId"] == turn["id"] and score["judge"] == w.by for score in duel["scores"]):
        fail(f"soudce {w.by} už výměnu {turn['id']} ohodnotil.")
    score = {"id": uuid.uuid4().hex, "turnId": turn["id"], "judge": w.by[:MAX_BY], "strength": strength,
             "supports": payload["supports"], "actor": w.actor, "at": w.at}
    if "evidenceOk" in payload:
        if type(payload["evidenceOk"]) is not bool:
            bad_request("evidenceOk musí být true nebo false.")
        score["evidenceOk"] = payload["evidenceOk"]
    if "rebuttedBy" in payload:
        rebuttal = by_id.get(payload["rebuttedBy"]) if isinstance(payload["rebuttedBy"], str) else None
        other = "B" if turn["side"] == "A" else "A"
        if rebuttal is None or rebuttal["side"] != other or turn["id"] not in rebuttal["refs"]:
            bad_request("rebuttedBy musí být výměna protistrany, která v refs odkazuje na hodnocenou výměnu.")
        if any(item["turnId"] == rebuttal["id"] and item.get("rebuttedBy") == turn["id"] for item in duel["scores"]):
            bad_request("rebuttedBy by vytvořilo cyklus vyvrácení.")
        score["rebuttedBy"] = rebuttal["id"]
    duel = {**duel, "scores": [*duel["scores"], score]}
    revised = _save(w, row, w.details(row["fragment_id"]), duel, f"Duel: skóre výměny {turn['id']}.")
    return {"fragment": public(revised), "score": score, "duel": duel, **_derived(duel)}


def _derived(duel):
    state = duel_state(duel)
    return {"probability": state["probability"], "onTurn": state["onTurn"], "rounds": state["rounds"],
            "canDecide": state["canDecide"]}


def _lesson(w, row, duel, decision, reason):
    """Poučení disciplíny duelu (§3.2); bez disciplíny se nezapíše a odpověď to řekne."""
    if row["discipline"] is None:
        return {"lessonSkipped": "duel nemá disciplínu, poučení se nezapsalo."}
    change = duel["challenger"]["text"].strip()[:120]
    text = {"keep": f"Změna „{change}“ neobstála, protože {reason}.",
            "adopt": f"Změna „{change}“ obstála: {reason}.",
            "synthesis": f"Syntéza „{decision['text'].strip()[:120]}“ ze změny „{change}“: {reason}."}[decision["outcome"]]
    lesson, _created = create_lesson(w, row["fragment_id"], row["revision"], row["discipline"],
                                     {"kind": LESSON_KIND[decision["outcome"]], "lesson": text[:MAX_LESSON]})
    return {"lesson": lesson}


def duel_decide(w, payload, node_ids):
    if "override" in payload:
        require_human(w.actor, "Rozhodnutí duelu mimo pravidlo (override) zapisuje jen člověk s důvodem.")
    if "synthesis" in payload:
        bad_request("pole synthesis už neplatí: syntézu podej jako výměnu kind synthesis, nech ji ohodnotit soudcem "
                    "a pošli synthesisTurnId.")
    row, duel = _duel_row(w, payload)
    state = duel_state(duel)
    ruled = state["rule"]
    outcome, reason, override = ruled["outcome"], ruled["reason"], None
    if "override" in payload:
        given = _exact(payload["override"], {"outcome", "reason"}, set(), "override")
        if given["outcome"] not in OUTCOMES:
            bad_request("override.outcome musí být keep, adopt nebo synthesis.")
        override = {"reason": _text(given["reason"], MAX_REASON, "override.reason"), "ruleOutcome": outcome}
        outcome, reason = given["outcome"], given["reason"]
    elif outcome is None:
        fail(f"duel ještě nejde rozhodnout: {reason}.")
    synthesis_id = None
    if outcome == "synthesis":
        defended = defended_syntheses(duel)
        if not defended:
            fail("syntéza zatím nebyla obhájena: chybí výměna synthesis, kterou soudce mimo strany ohodnotil silou ≥ 6.")
        if "synthesisTurnId" not in payload:
            bad_request("výsledek synthesis potřebuje synthesisTurnId obhájené výměny synthesis.")
        synthesis_id = payload["synthesisTurnId"]
        if synthesis_id not in defended:
            fail("syntéza zatím nebyla obhájena: výměna synthesisTurnId nemá od soudců mimo strany průměr ≥ 6.")
        text = next(turn["text"] for turn in duel["turns"] if turn["id"] == synthesis_id)
    else:
        text = duel["challenger" if outcome == "adopt" else "incumbent"]["text"]
    decision = {"outcome": outcome, "text": text, "p": state["probability"]["p"], **_stamp(w)}
    if override:
        decision["override"] = override
    if synthesis_id:
        decision["synthesisTurnId"] = synthesis_id
    vision = _vision_row(latest_rows(w.db, w.project, w.workspace), row["scope_node_id"])
    vision = (vision, w.details(vision["fragment_id"])) if vision is not None else None
    applied, applied_revision, why, target = apply_decision(w, row["fragment_id"], duel, decision, vision, _vision_ref)
    decision.update({"applied": applied, "appliedRevision": applied_revision})
    if why:
        decision["reason"] = why
    duel = {**duel, "status": "decided", "decision": decision}
    note = f"Duel rozhodnut: {outcome}" + (f" (override člověka: {reason[:200]})." if override else ".")
    revised = _save(w, row, w.details(row["fragment_id"]), duel, note)
    extra = {"appliedFragment": public(target, with_text=True)} if applied else {}
    return {"fragment": public(revised), "decision": decision, "duel": duel, "probability": state["probability"],
            "applied": applied, **extra, **_lesson(w, revised, duel, decision, reason)}


def _vision_row(rows, scope):
    return next((row for row in rows.values() if row["kind"] == "vision" and row["parent_id"] is None
                 and not row["deleted"] and row["scope_node_id"] == scope), None)


def _vision_ref(row, fields):
    # Zápis bodu zvýší revizi fragmentu, ale nezmění cíl, proti kterému se duel vede.
    return {"fragmentId": row["fragment_id"],
            "revision": (fields.get("vision") or {}).get("directionRevision", 1)}


def _current_points(row, fields):
    revision = _vision_ref(row, fields)["revision"]
    return [point for point in (fields.get("vision") or {}).get("points", [])
            if point.get("visionRevision") == revision]


def _decided_duel(w, duel_id, scope):
    """Rozhodnutý duel v rozsahu `scope` (řádek, duel); jiný druh = 400, nerozhodnutý nebo jiný rozsah = 409."""
    row = w.latest(duel_id, live=False)
    duel = w.details(row["fragment_id"]).get("duel")
    if row["kind"] != "duel" or duel is None:
        bad_request(f"{duel_id} není duel.")
    if duel["status"] != "decided" or row["scope_node_id"] != scope:
        fail("duel musí být rozhodnutý a ve stejném rozsahu jako představa.")
    return row, duel


def vision_set(w, payload, node_ids):
    """První představu rozsahu zakládá člověk textem. Změnu uplatní sám `duel-decide`; `fromDuel` je jen ruční
    dotažení rozhodnutí proti AKTUÁLNÍ obsahové verzi představy (`visionRef`), jinak 409."""
    scope = _scope(payload, node_ids)
    if ("text" in payload) == ("fromDuel" in payload):
        bad_request("vision-set nese buď text (první představa), nebo fromDuel (změna rozhodnutým duelem).")
    row = _vision_row(latest_rows(w.db, w.project, w.workspace), scope)
    if row is None:
        if "fromDuel" in payload:
            fail("rozsah ještě nemá představu; první založí člověk textem.")
        require_human(w.actor, "První představu rozsahu zakládá jen člověk.")
        text = _text(payload["text"], MAX_DIRECTION, "text")
        row = w.new(parent=None, scope=scope, kind="vision", title="Představa", text=text, note=payload["note"])
        write_details(w.db, w.project, w.workspace, row["fragment_id"], {"vision": {"points": []}}, w.at)
        return {"fragment": public(row, with_text=True)}
    if "fromDuel" not in payload:
        fail("představu mění jen rozhodnutý duel se subject project (vision-set fromDuel).")
    _row, duel = _decided_duel(w, payload["fromDuel"], scope)
    if duel["subject"]["kind"] != "project" or duel["decision"]["outcome"] not in ("adopt", "synthesis"):
        fail("představu mění jen duel se subject project rozhodnutý adopt nebo synthesis.")
    fields = w.details(row["fragment_id"])
    if duel.get("visionRef") != _vision_ref(row, fields):
        fail("duel nevychází z aktuální verze představy; otevřete nový duel.")
    text = duel["decision"]["text"]
    if row["text"] == text:
        fail("vision-set nic nemění; představa už má tento text.")
    row = w.revise(row, f"Představa z duelu {payload['fromDuel']}: {payload['note']}"[:1000], text=text)
    write_details(w.db, w.project, w.workspace, row["fragment_id"],
                  {**fields, "vision": {**fields["vision"], "directionRevision": row["revision"]}}, w.at)
    return {"fragment": public(row, with_text=True)}


def vision_align(w, payload, node_ids):
    scope = _scope(payload, node_ids)
    point = {"score": _score_of(payload["score"], "score"), "note": _text(payload["note"], MAX_POINT_NOTE, "note"), **_stamp(w)}
    row = _vision_row(latest_rows(w.db, w.project, w.workspace), scope)
    if row is None:
        fail("rozsah nemá představu; založí ji člověk (op vision-set).")
    duel_row, duel = _decided_duel(w, payload["duelId"], scope)
    sides = parties(duel)
    if w.by in sides["A"] | sides["B"]:
        bad_request("shodu s představou po duelu nehodnotí strana duelu ani autor jeho challengeru.")
    point["duelId"] = duel_row["fragment_id"]
    fields = w.details(row["fragment_id"])
    point["visionRevision"] = _vision_ref(row, fields)["revision"]
    points = [*(fields.get("vision") or {"points": []})["points"], point]
    if any(item.get("duelId") == point["duelId"] for item in points[:-1]):
        fail("duel už má bod trajektorie; jeden bod na duel.")
    revised = w.revise(row, f"Bod trajektorie: {point['score']}/10.")
    fields = {**fields, "vision": {**fields.get("vision", {}), "points": points}}
    write_details(w.db, w.project, w.workspace, row["fragment_id"], fields, w.at)
    return {"fragment": public(revised), "point": point, "trajectory": vision_trend(_current_points(row, fields))}


HANDLERS = {"duel-open": duel_open, "duel-turn": duel_turn, "duel-score": duel_score, "duel-decide": duel_decide,
            "vision-set": vision_set, "vision-align": vision_align}


def _points(db, project, workspace, rows, scope):
    row = _vision_row(rows, scope)
    if row is None:
        return None, []
    fields = (latest_details(db, project, workspace, [row["fragment_id"]]).get(row["fragment_id"]) or {}).get("fields", {})
    return row, _current_points(row, fields)


def _reading(canvas, project, workspace):
    view = canvas.view(project, workspace)
    if view["readOnly"]:
        fail("main je pouze pro čtení a nemá duely ani představu; čtěte pracovní prostor.")
    db = canvas.db_for(project)
    return db, latest_rows(db, project, workspace)


def duel_view(canvas, project, workspace, duel_id):
    """`GET /api/brief-vault/duel`: stav duelu, P(B > A) s rozpadem, kdo je na tahu, kola a trend představy rozsahu."""
    with canvas.reading(project):
        db, rows = _reading(canvas, project, workspace)
        row = rows.get(duel_id) if isinstance(duel_id, str) else None
        found = (latest_details(db, project, workspace, [duel_id]).get(duel_id) or {}).get("fields", {}) if row else {}
        if row is None or row["kind"] != "duel" or "duel" not in found:
            fail(f"duel {duel_id} v tomto pracovním prostoru neexistuje.")
        duel = found["duel"]
        _vision, points = _points(db, project, workspace, rows, row["scope_node_id"])
        return {"duel": {**duel, "fragment": public(row, with_text=True)}, **_derived(duel),
                "trajectory": vision_trend(points)}


def vision_view(canvas, project, workspace, scope):
    """`GET /api/brief-vault/vision`: představa rozsahu (revize fragmentu s textem a `points`) a trend shody (§3.3);
    bez představy `vision: null`."""
    with canvas.reading(project):
        db, rows = _reading(canvas, project, workspace)
        row, points = _points(db, project, workspace, rows, scope)
        vision = None if row is None else {**public(row, with_text=True), "points": points}
        return {"vision": vision, "trajectory": vision_trend(points)}
