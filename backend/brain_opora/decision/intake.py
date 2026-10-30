"""Vstupní brána, vrstva Jev: zařazení vstupu `pending` jedním voláním (docs/navrhy/2026-10-30-vstupni-brana.md §4, §7).

Jedno volání `evaluate` se dvěma otázkami `choice`: stanovisko nad šesti hodnotami §3 (duplicitu řeší determinismus)
a oblast nad ID uzlů plátna `kind: area` s jejich názvy (vzor `sources.rank`; bez oblastí se otázka vynechá).
Věta člověka jde jen jako `state`, nikdy do instrukcí; instrukce a kritéria stanovisek jsou pevný text
(vzor `brief_vault_check`).

Jev je zrychlení, ne podmínka: vypnuté povolení projektu (`brain.intake.jev`), vyčerpaný denní strop
(`brain.intake.jevPerDay`, součet `jev_calls` vstupů zapsaných ten UTC den), chybějící klíč, porucha nebo jistota
pod 0,6 nechají stanovisko `pending` a rozhodne srdce. Klasifikace běží v dávce srdce před složením zprávy
(`HeartSupervisor._batch`), nikdy v HTTP požadavku, a nikdy nevyhodí.
"""
import logging
import math
from datetime import UTC, datetime

from backend.brain_opora.determinism import intake, intake_setting
from database.repositories.intake_entries import IntakeEntries

LOGGER = logging.getLogger(__name__)
THRESHOLD = 0.6
PER_BATCH = 5  # nejvýš vstupů zařazených před jednou dávkou
MAX_TEXT = 2000
MAX_AREAS, MAX_NAME = 50, 120
VERDICTS = {
    "done": "Požadavek je už splněný; nevznikne nová práce.",
    "extends_in_progress": "Upřesňuje nebo mění rozsah práce, která je právě rozpracovaná.",
    "fix_for_milestone": "Chyba nebo nedostatek, bez jehož opravy rozpracovaná schopnost neprojde ověřením.",
    "changes_intent": "Mění schválený záměr, cíl nebo předpoklad, na kterém plán stojí.",
    "later_extension": "Nová funkce nebo rozšíření navíc nad rozpracovanou schopnost; může počkat.",
    "needs_info": "Z věty nejde poznat, co se chce; je potřeba se doptat.",
}
VERDICT_INSTRUCTIONS = ("Zařaď větu ze state (text od člověka nebo pracovníka) vůči rozpracované práci aplikace: "
                        "které stanovisko na ni nejlépe sedí?")
AREA_INSTRUCTIONS = "Ke které schopnosti (oblasti) aplikace věta ze state patří?"


def questions(areas):
    """Otázky z pevných textů; oblast jen když nějaká je (kritérium = název oblasti)."""
    asked = {"verdict": {"type": "choice", "instructions": VERDICT_INSTRUCTIONS, "criteria": dict(VERDICTS)}}
    criteria = {str(area["id"]): str(area.get("name") or area["id"])[:MAX_NAME] for area in areas[:MAX_AREAS]}
    if criteria:
        asked["area"] = {"type": "choice", "instructions": AREA_INSTRUCTIONS, "criteria": criteria}
    return asked


def state(entry):
    """Co odchází: jen věta (oříznutá) a její zdroj."""
    return {"text": str(entry.get("text") or "")[:MAX_TEXT], "source": entry.get("source")}


def _confidence(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return round(min(max(float(value), 0.0), 1.0), 3)


def _pick(answer, allowed):
    """`(volba, jistota)` z odpovědi `choice`; neznámá volba (halucinace) nebo chybějící jistota = `(None, None)`."""
    if not isinstance(answer, dict) or answer.get("choice") not in allowed:
        return None, None
    confidence = _confidence(answer.get("confidence"))
    if confidence is None and isinstance(answer.get("probabilities"), dict):
        confidence = _confidence(answer["probabilities"].get(answer["choice"]))
    return (answer["choice"], confidence) if confidence is not None else (None, None)


def classify(entry, areas, evaluate):
    """`{verdict, areaId, confidence, reason}` jednoho vstupu; porucha Jevu = `pending`, nikdy nevyhodí."""
    asked = questions(areas)
    try:
        answers = evaluate(state(entry), asked)
    except Exception:  # noqa: BLE001 - injektovaný klient nesmí shodit dávku srdce
        answers = None
    if not isinstance(answers, dict):
        return {"verdict": "pending", "areaId": None, "confidence": None, "reason": "Jev neodpověděl; rozhodne srdce."}
    verdict, confidence = _pick(answers.get("verdict"), VERDICTS)
    area, area_confidence = _pick(answers.get("area"), asked.get("area", {}).get("criteria", {}))
    area = area if area_confidence is not None and area_confidence >= THRESHOLD else None
    if verdict is None or confidence < THRESHOLD:
        guess = f"{verdict} {confidence:.2f}" if verdict else "bez platné volby"
        return {"verdict": "pending", "areaId": area, "confidence": confidence,
                "reason": f"Jev nejistý ({guess}); rozhodne srdce."}
    return {"verdict": verdict, "areaId": area, "confidence": confidence, "reason": f"Jev: {verdict} ({confidence:.2f})."}


def _day(now):
    return datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%d")


def _due(service, project, workspace, inputs, setting, now):
    """Vstupy k zařazení: `pending` dnešního UTC dne, nejdřív ty z dávky, nejvýš `PER_BATCH` a zbytek denního stropu."""
    first = [item["intake"]["id"] for item in inputs
             if isinstance(item.get("intake"), dict) and item["intake"].get("verdict") == "pending"]
    day = _day(now)
    with service.reading(project):
        store = IntakeEntries(service.db_for(project))
        budget = min(PER_BATCH, setting["jevPerDay"] - store.jev_calls_on(day))
        return store.unclassified(workspace, budget, day, first) if budget > 0 else []


def _annotate(item, written):
    info = item.get("intake") if isinstance(item.get("intake"), dict) else None
    if info is None or info.get("id") not in written:
        return item
    return {**item, "intake": {**info, "layer": "jev", **written[info["id"]]}}


def classify_pending(service, project, workspace, inputs, *, jev, now):
    """Zařadí vstupy `pending` prostoru přes Jev a vrátí vstupy dávky s doplněným stanoviskem, oblastí a jistotou.

    `jev()` vrací `evaluate(state, questions)` s klíčem aplikace, nebo None (bez klíče nic neodejde).
    Vypnuto, vyčerpáno, bez klíče nebo jakákoli chyba = vstupy beze změny."""
    try:
        setting = intake_setting.read(service, project)
        if not setting["jev"]:
            return inputs
        entries = _due(service, project, workspace, inputs, setting, now)
        evaluate = jev() if entries else None
        if evaluate is None:
            return inputs
        areas = intake.areas(service, project, workspace)
        results = {entry["id"]: classify(entry, areas, evaluate) for entry in entries}  # síť mimo zámek projektu
        written = {}
        with service.lock_for(project):
            db = service.db_for(project)
            with db:
                store = IntakeEntries(db)
                for entry_id, result in results.items():
                    if store.set_verdict(entry_id, verdict=result["verdict"], layer="jev", reason=result["reason"],
                                         area_id=result["areaId"], confidence=result["confidence"], jev_calls=1,
                                         only_pending=True):
                        written[entry_id] = result
        return [_annotate(item, written) for item in inputs]
    except Exception:  # noqa: BLE001 - Jev nikdy neshodí dávku srdce
        LOGGER.exception("Vstupní brána: zařazení přes Jev v projektu %s selhalo.", project)
        return inputs
