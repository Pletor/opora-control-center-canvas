"""Fronta práce Schránky a čtení poučení (docs/schranka-neurony.md §3 API, §5, §9 body 8, 9 a 12).

`GET /api/brief-vault/next` je nezávazná fronta bez rezervace: dva agenti mohou dostat totéž, druhý zápis
dostane 409. Vrací živé fragmenty druhu `brief` s živými předky, platnou disciplínou a aspoň jednou nesplněnou
(nebo zneplatněnou) branou; vylučuje slepé uličky (`decided = no`) a větve pokryté `placed` předka. Pořadí:
číslo chybějící brány, hloubka, cesta `ord` od kořene, `fragmentId`. `needs` říká, zda brána čeká na návrh
payloadu (`proposal`), nebo jen na potvrzení (`confirm`, s návrhem v `proposal`). `blocked` = počet fragmentů
fronty, které samotné potvrzení neposune: čekají na návrh payloadu, nebo na bránu `planned`/`placed` (plán a
schválení člověka, K4; do té doby je fronta nevrací).
"""

from backend.editor.brief_vault.brief_vault_disciplines import DISCIPLINE_IDS
from backend.editor.brief_vault.brief_vault_gate_rules import (
    GATES,
    HINTS,
    LATER_GATES,
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
        if gate in LATER_GATES:
            blocked += 1
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


def lessons(canvas, project, workspace, discipline=None):
    """Živá poučení prostoru (volitelně jedné disciplíny) seřazená podle platné váhy."""
    discipline = _discipline(discipline)
    with canvas.reading(project):
        items = [] if canvas.view(project, workspace)["readOnly"] else live_lessons(
            canvas.db_for(project), project, workspace, {discipline} if discipline else None)
        return {"lessons": items, "threshold": THRESHOLD, "halfLifeDays": HALF_LIFE_DAYS}
