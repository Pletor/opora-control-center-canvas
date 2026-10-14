"""Fronta práce Schránky a čtení poučení (docs/schranka-neurony.md §3 API, §5, §9 body 8, 9 a 12).

`GET /api/brief-vault/next` je nezávazná fronta bez rezervace: dva agenti mohou dostat totéž, druhý zápis
dostane 409. Vrací živé fragmenty druhu `brief` s živými předky, platnou disciplínou a aspoň jednou nesplněnou
(nebo zneplatněnou) branou; vylučuje slepé uličky (`decided = no`) a větve pokryté `placed` předka. Pořadí:
číslo chybějící brány, hloubka, cesta `ord` od kořene, `fragmentId`. `needs` říká, zda brána čeká na návrh
payloadu (`proposal`), nebo jen na potvrzení (`confirm`, s návrhem v `proposal`); `planned` je potvrzení bez
návrhu (plán sestaví server). `blocked` = počet fragmentů fronty, které samotné potvrzení agenta neposune: čekají
na návrh payloadu, nebo na bránu `placed` (zápis uloženého plánu na plátno schvaluje člověk; fronta je nevrací).
`lessons(versionId=…)` čte poučení uložené verze plátna (snímek k času verze), ne živou tabulku.
"""

from backend.editor.brief_vault.brief_vault_disciplines import DISCIPLINE_IDS
from backend.editor.brief_vault.brief_vault_gate_rules import (
    GATES,
    HINTS,
    NO_PAYLOAD,
    dead_end,
    gate_state,
)
from backend.editor.brief_vault.brief_vault_gates import covered, usable_proposal
from backend.editor.brief_vault.brief_vault_lessons import (
    HALF_LIFE_DAYS,
    NEXT_LIMIT,
    THRESHOLD,
    live_lessons,
    snapshot_lessons,
)
from backend.editor.brief_vault.brief_vault_model import (
    bad_request,
    effective_disciplines,
    latest_rows,
)
from backend.editor.brief_vault.brief_vault_tree import live_ids

NEEDS_HINT = {"proposal": "Chybí návrh: pošli op propose {fragmentId, expectedRevision, gate, payload, note}, pak op gate value: true.",
              "confirm": "Potvrď op gate {fragmentId, expectedRevision, gate, value: true, note} (bez payloadu vezme návrh), "
                         "nebo nesouhlas zapiš novým návrhem."}


def _discipline(discipline):
    if discipline is not None and discipline not in DISCIPLINE_IDS:
        bad_request("discipline musí být id disciplíny (" + ", ".join(DISCIPLINE_IDS) + ").")
    return discipline


def _ords(rows, fragment_id):
    path, cursor = [], fragment_id
    while cursor is not None:
        path.append(rows[cursor]["ord"])
        cursor = rows[cursor]["parent_id"]
    return tuple(reversed(path))


def _queue(db, project, workspace, discipline):
    rows = latest_rows(db, project, workspace)
    live, disciplines = live_ids(rows), effective_disciplines(rows)
    states = {fid: gate_state(rows[fid], disciplines[fid]) for fid in live if disciplines.get(fid)}
    queue, blocked = [], 0
    for fragment_id, state in states.items():
        if rows[fragment_id]["kind"] != "brief" or (discipline and disciplines[fragment_id] != discipline):
            continue
        if state["next"] is None or dead_end(state) or covered(rows, fragment_id, states):
            continue
        gate = state["next"]
        if gate == "placed":
            blocked += 1  # zápis na plátno: uložený plán vkládá až schválení člověka
            continue
        proposal = None if gate in NO_PAYLOAD else usable_proposal(db, project, workspace, fragment_id, gate, state)
        needs = "confirm" if gate in NO_PAYLOAD or proposal else "proposal"
        blocked += needs == "proposal"
        ords = _ords(rows, fragment_id)
        queue.append(((GATES.index(gate), len(ords), ords, fragment_id), fragment_id, gate, needs, proposal))
    queue.sort(key=lambda item: item[0])
    return rows, disciplines, states, queue, blocked


def next_work(canvas, project, workspace, discipline=None):
    """Další brána k práci (nebo `{fragment: null}`) s poučeními disciplíny a počtem blokovaných."""
    discipline = _discipline(discipline)
    with canvas.reading(project):
        if canvas.view(project, workspace)["readOnly"]:
            return {"fragment": None, "blocked": 0}
        db = canvas.db_for(project)
        rows, disciplines, states, queue, blocked = _queue(db, project, workspace, discipline)
        if not queue:
            return {"fragment": None, "blocked": blocked}
        _key, fragment_id, gate, needs, proposal = queue[0]
        row, found = rows[fragment_id], disciplines[fragment_id]
        result = {"fragment": {"id": fragment_id, "title": row["title"], "effectiveDiscipline": found,
                               "revision": row["revision"], "gatesStale": states[fragment_id]["stale"]},
                  "gate": gate, "needs": needs, "hint": f"{HINTS[gate]} {NEEDS_HINT[needs]}",
                  "lessons": live_lessons(db, project, workspace, {found}, NEXT_LIMIT), "blocked": blocked}
        if proposal:
            result["proposal"] = proposal
        return result


def lessons(canvas, project, workspace, discipline=None, version_id=None):
    """Živá poučení prostoru (volitelně jedné disciplíny) seřazená podle platné váhy.

    `version_id` = uložená verze plátna: poučení se čtou ze snímku (`briefLessons`) a váha k času verze;
    starý snímek bez poučení vrátí prázdný seznam. Main bez verze nemá poučení (je jen pro čtení)."""
    discipline = _discipline(discipline)
    wanted = {discipline} if discipline else None
    if version_id is not None:
        from datetime import datetime

        from backend.editor.canvas_versions.canvas_versions import CanvasVersions
        from backend.editor.canvas_versions.version_content import with_later_stores
        read = CanvasVersions(canvas).read(project, workspace, version_id)
        records = with_later_stores((read["snapshot"] or {}).get("records") or {})["briefLessons"]
        at = datetime.fromisoformat(read["version"]["createdAt"])
        return {"lessons": snapshot_lessons(records, wanted, at), "threshold": THRESHOLD, "halfLifeDays": HALF_LIFE_DAYS,
                "versionId": version_id, "asOf": read["version"]["createdAt"]}
    with canvas.reading(project):
        items = [] if canvas.view(project, workspace)["readOnly"] else live_lessons(
            canvas.db_for(project), project, workspace, wanted)
        return {"lessons": items, "threshold": THRESHOLD, "halfLifeDays": HALF_LIFE_DAYS}
