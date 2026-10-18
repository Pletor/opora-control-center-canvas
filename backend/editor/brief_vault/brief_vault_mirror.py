"""Zrcadlo u bran cyklu: volání po potvrzení brány a přehled pro Schránku (docs/zrcadlo.md, schranka-neurony.md §9 bod 11).

Volá se **po** potvrzení transakce brány, mimo zámek grafu i transakci schránky, a nikdy nemění výsledek brány:
porucha, vypnuté Zrcadlo nebo projekt mimo `[mirror] projects` = nic se nestane. Výsledky jdou append-only do
`brief_mirror_events` (provozní log, ne stav fragmentu, proto nejsou v revizi ani v uložené verzi plátna).
`event_id` = sha256(projekt, workspace, fragment, cyklus, druh), cyklus = revize, ve které vzniklo `synthesized`;
opakování stejného cyklu se proto nezavolá ani nezapíše dvakrát.

- `synthesized` → `predict` (text fragmentu, platná disciplína, mikrokrok `typ: hotovo`), událost `predict`.
- `verified` → `observe` jen s `predictionId` události `predict` stejného cyklu (jinak přeskočí), událost `observe`.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime

from backend.editor.brief_vault.brief_vault_gate_rules import parse_gates
from backend.editor.brief_vault.brief_vault_model import effective_disciplines, latest_rows

MIRROR_GATES = {"synthesized": "predict", "verified": "observe"}
# Stejný práh jako MIRROR_ERROR_THRESHOLD_LOW služby: chyba pod ním = dobrá předpověď (přesnost po disciplínách).
GOOD_BELOW = 0.25
UNASSIGNED = "nezarazeno"
LOGGER = logging.getLogger(__name__)


def event_id(project, workspace, fragment_id, cycle, kind):
    return hashlib.sha256(json.dumps([project, workspace, fragment_id, cycle, kind]).encode("utf-8")).hexdigest()


def _event(db, key):
    row = db.execute("SELECT * FROM brief_mirror_events WHERE event_id=?", (key,)).fetchone()
    return dict(row) if row else None


def _store(canvas, project, db, key, scope, kind, request, result):
    workspace, fragment_id, revision, cycle = scope
    with canvas.lock_for(project), db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO brief_mirror_events(event_id,project_id,workspace_id,fragment_id,revision,cycle,kind,"
                   "request,result,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (key, project, workspace, fragment_id, revision, cycle, kind, json.dumps(request, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False), datetime.now(UTC).isoformat()))
    return kind


def after_gate(canvas, payload, result, client_for):
    """Hook po potvrzené bráně. Vrací druh zapsané události (`predict`/`observe`) nebo None. Nikdy nevyhodí."""
    try:
        return _after_gate(canvas, payload, result, client_for)
    except Exception:  # Zrcadlo je orientační; brána už platí a její výsledek se nemění
        LOGGER.warning("Zrcadlo po bráně selhalo; brána platí beze změny.", exc_info=True)
        return None


def _after_gate(canvas, payload, result, client_for):
    if not isinstance(payload, dict) or payload.get("op") != "gate" or payload.get("value") is not True:
        return None
    kind = MIRROR_GATES.get(payload.get("gate"))
    fragment = (result or {}).get("fragment") or {}
    if kind is None or not fragment.get("id"):
        return None
    project, workspace = payload["project"], payload["workspace"]
    client = client_for(project)
    if client is None:
        return None
    db = canvas.db_for(project)
    row = db.execute("SELECT * FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? AND fragment_id=?"
                     " AND revision=?", (project, workspace, fragment["id"], fragment["revision"])).fetchone()
    entries = parse_gates(row["gates"]) if row else {}
    synthesized, gate_entry = entries.get("synthesized") or {}, entries.get(payload["gate"]) or {}
    if synthesized.get("value") is not True or gate_entry.get("value") is not True:
        return None
    cycle = synthesized["revision"]
    scope = (workspace, row["fragment_id"], row["revision"], cycle)
    key = event_id(project, workspace, row["fragment_id"], cycle, kind)
    if _event(db, key):
        return None
    if kind == "predict":
        discipline = effective_disciplines(latest_rows(db, project, workspace)).get(row["fragment_id"]) or UNASSIGNED
        step = synthesized.get("payload") or {}
        microstep = f"{step.get('type', '')}: {step.get('done', '')}"
        found = client.predict(fragment_id=row["fragment_id"], discipline=discipline, title=row["title"], text=row["text"],
                               microstep=microstep)
        request = {"fragmentId": row["fragment_id"], "discipline": discipline, "title": row["title"],
                   "textChars": len(row["text"]), "microstep": microstep,
                   "prediction": step.get("prediction")}
    else:
        predicted = _event(db, event_id(project, workspace, row["fragment_id"], cycle, "predict"))
        if predicted is None:
            return None
        prediction_id = json.loads(predicted["result"]).get("predictionId")
        actual = (gate_entry.get("payload") or {}).get("actual")
        found = client.observe(prediction_id=prediction_id, actual=actual)
        request = {"predictionId": prediction_id, "actual": actual}
    if found is None:
        return None
    return _store(canvas, project, db, key, scope, kind, request, found)


def overview(canvas, project, workspace, client):
    """`GET /api/brief-vault/mirror`: `{enabled, health?, byDiscipline: {disc: {predictions, accuracy, lastError}}, hormones?}`.

    `accuracy` = podíl pozorování s chybou pod `GOOD_BELOW` (None bez pozorování), `lastError` = predikční chyba
    posledního pozorování disciplíny. `hormones` jsou z posledního pozorování v prostoru."""
    db = canvas.db_for(project)
    rows = db.execute("SELECT * FROM brief_mirror_events WHERE project_id=? AND workspace_id=? ORDER BY created_at, event_id",
                      (project, workspace)).fetchall()
    disciplines, by_discipline, hormones = {}, {}, None
    for row in rows:
        request, result = json.loads(row["request"]), json.loads(row["result"])
        if row["kind"] == "predict":
            name = request.get("discipline") or UNASSIGNED
            disciplines[(row["fragment_id"], row["cycle"])] = name
            by_discipline.setdefault(name, {"predictions": 0, "observed": 0, "good": 0, "lastError": None})["predictions"] += 1
        elif row["kind"] == "observe":
            name = disciplines.get((row["fragment_id"], row["cycle"]), UNASSIGNED)
            item = by_discipline.setdefault(name, {"predictions": 0, "observed": 0, "good": 0, "lastError": None})
            item["observed"] += 1
            item["good"] += result["predictionError"] < GOOD_BELOW
            item["lastError"] = result["predictionError"]
            hormones = result.get("hormones")
    found = {"enabled": client is not None, "byDiscipline": {
        name: {"predictions": item["predictions"], "observed": item["observed"],
               "accuracy": round(item["good"] / item["observed"], 4) if item["observed"] else None,
               "lastError": item["lastError"]}
        for name, item in sorted(by_discipline.items())}}
    if hormones is not None:
        found["hormones"] = hormones
    if client is not None:
        found["health"] = client.health()
    return found
