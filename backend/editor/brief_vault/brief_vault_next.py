"""Fronta práce Schránky a čtení poučení (docs/schranka-neurony.md §3 API, §5, §9 body 8, 9 a 12).

`GET /api/brief-vault/next` je nezávazná fronta bez rezervace: dva agenti mohou dostat totéž, druhý zápis
dostane 409. Vrací živé fragmenty druhu `brief` s živými předky, platnou disciplínou a aspoň jednou nesplněnou
(nebo zneplatněnou) branou; vylučuje slepé uličky (`decided = no`) a větve pokryté `placed` předka. Pořadí:
číslo chybějící brány, hloubka, cesta `ord` od kořene, `fragmentId`. `needs` říká, zda brána čeká na návrh
payloadu (`proposal`), nebo jen na potvrzení (`confirm`, s návrhem v `proposal`); `planned` je potvrzení bez
návrhu (plán sestaví server). `blocked` = počet fragmentů fronty, které samotné potvrzení agenta neposune, a
`blockedBy` ho rozkládá: `proposal` (čeká na návrh payloadu), `confirm` (čeká na `placed`, uložený plán dál platí:
zápis na plátno schvaluje člověk), `plan` (čeká na `placed`, ale uložený plán je zastaralý: změnilo se plátno nebo
zdroj, je třeba nové `planned`) a `exhausted` (po `MAX_ROUNDS` kolech, §11: čeká na člověka). Brány `placed`
ani vyčerpané fragmenty fronta nevrací; `blocked` = součet `blockedBy` (kompatibilita).
Duel (docs/schranka-duel.md §1, §4): fronta nevrací (`blockedBy.duel`) fragment, který je sám nebo přes předka
předmětem otevřeného duelu (`subject.kind: fragment`), na který odkazuje karta předmětu `node` (`fragmentRefs` ve
stavu Desktop v3), nebo který leží v rozsahu duelu o projektu (kořen se `scopeNodeId` duelu; prázdný rozsah duelu =
celý projekt). Otevřený duel je hlava fronty (`needs: "duel"`, `gate: null`, `onTurn`, `canDecide`) dřív než brány:
s filtrem disciplíny duel té disciplíny a každý duel o projektu, bez filtru kterýkoli.
`lessons(versionId=…)` čte poučení uložené verze plátna (snímek k času verze), ne živou tabulku.
"""

from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.brief_vault.brief_vault_details import latest_details
from backend.editor.brief_vault.brief_vault_disciplines import DISCIPLINE_IDS
from backend.editor.brief_vault.brief_vault_duel_shape import duel_state, open_duels
from backend.editor.brief_vault.brief_vault_gate_rules import (
    GATES,
    HINTS,
    NO_PAYLOAD,
    dead_end,
    gate_state,
    input_hash,
    round_fields,
)
from backend.editor.brief_vault.brief_vault_gates import covered
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
    gate_rounds,
    latest_rows,
)
from backend.editor.brief_vault.brief_vault_proposals import usable_proposal
from backend.editor.brief_vault.brief_vault_tree import live_ids

NEEDS_HINT = {"proposal": "Chybí návrh: pošli op propose {fragmentId, expectedRevision, gate, payload, note}, pak op gate value: true.",
              "confirm": "Potvrď op gate {fragmentId, expectedRevision, gate, value: true, note} (bez payloadu vezme návrh), "
                         "nebo nesouhlas zapiš op reject-proposal {fragmentId, expectedRevision, gate, note} či novým návrhem."}


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


def _plan_current(rows, disciplines, state, digest):
    """Uložený plán brány `planned` by `placed` vložil: shodný digest plátna i otisky zdrojů."""
    stored = state["entries"]["planned"].get("payload") or {}
    if stored.get("digest") != digest:
        return False
    return all(fid in rows and not rows[fid]["deleted"]
               and input_hash(rows[fid]["title"], rows[fid]["text"], disciplines.get(fid)) == expected
               for fid, expected in (stored.get("sourceHashes") or {}).items())


def _idle():
    return {"proposal": 0, "confirm": 0, "exhausted": 0, "plan": 0, "duel": 0}


def _under(rows, fragment_id, subjects):
    """Fragment nebo některý jeho předek je předmětem otevřeného duelu."""
    cursor, seen = fragment_id, set()
    while cursor in rows and cursor not in seen:
        if cursor in subjects:
            return True
        seen.add(cursor)
        cursor = rows[cursor]["parent_id"]
    return False


def _root_scope(rows, fragment_id):
    cursor, seen = fragment_id, set()
    while rows[cursor]["parent_id"] in rows and cursor not in seen:
        seen.add(cursor)
        cursor = rows[cursor]["parent_id"]
    return rows[cursor]["scope_node_id"]


def _duel_blocks(duels, state):
    """Co otevřené duely blokují: id fragmentů (s podstromy) a rozsahy duelů o projektu (None = celý projekt)."""
    subjects, scopes = set(), set()
    nodes = (state or {}).get("nodes", {})
    for row, duel in duels:
        kind, target = duel["subject"]["kind"], duel["subject"]["id"]
        if kind == "fragment":
            subjects.add(target)
        elif kind == "node":
            subjects.update(ref["fragmentId"] for ref in (nodes.get(target) or {}).get("fragmentRefs", []))
        else:
            scopes.add(row["scope_node_id"] or None)
    return subjects, scopes


def _queue(db, project, workspace, discipline, digest, desktop=None):
    rows = latest_rows(db, project, workspace)
    live, disciplines, rounds = live_ids(rows), effective_disciplines(rows), gate_rounds(db, project, workspace)
    states = {fid: gate_state(rows[fid], disciplines[fid]) for fid in live if disciplines.get(fid)}
    duels = open_duels(rows, {fid: found["fields"] for fid, found in latest_details(
        db, project, workspace, [fid for fid in live if rows[fid]["kind"] == "duel"]).items()}, live)
    subjects, scopes = _duel_blocks(duels, desktop)
    queue, blocked = [], _idle()
    for fragment_id, state in states.items():
        if rows[fragment_id]["kind"] != "brief" or (discipline and disciplines[fragment_id] != discipline):
            continue
        if state["next"] is None or dead_end(state) or covered(rows, fragment_id, states):
            continue
        if _under(rows, fragment_id, subjects) or None in scopes or (scopes and _root_scope(rows, fragment_id) in scopes):
            blocked["duel"] += 1  # směr se vyjasňuje v duelu (docs/schranka-duel.md §1)
            continue
        if round_fields(rounds, fragment_id)["exhausted"]:
            blocked["exhausted"] += 1  # po MAX_ROUNDS kolech čeká na člověka (§11)
            continue
        gate = state["next"]
        if gate == "placed":
            # Zápis na plátno: uložený plán vkládá až schválení člověka; zastaralý plán chce nové planned.
            blocked["confirm" if _plan_current(rows, disciplines, state, digest) else "plan"] += 1
            continue
        proposal = None if gate in NO_PAYLOAD else usable_proposal(db, project, workspace, fragment_id, gate, state)
        needs = "confirm" if gate in NO_PAYLOAD or proposal else "proposal"
        blocked["proposal"] += needs == "proposal"
        ords = _ords(rows, fragment_id)
        queue.append(((GATES.index(gate), len(ords), ords, fragment_id), fragment_id, gate, needs, proposal))
    queue.sort(key=lambda item: item[0])
    duels = [(row, duel) for row, duel in duels
             if not discipline or row["discipline"] == discipline or duel["subject"]["kind"] == "project"]
    return rows, disciplines, states, rounds, queue, blocked, duels


def _blocked(counts):
    return {"blocked": sum(counts.values()), "blockedBy": counts}


def next_work(canvas, project, workspace, discipline=None):
    """Další brána k práci (nebo `{fragment: null}`) s poučeními disciplíny a počtem blokovaných."""
    discipline = _discipline(discipline)
    with canvas.reading(project):
        view = canvas.view(project, workspace)
        if view["readOnly"]:
            return {"fragment": None, **_blocked(_idle())}
        db = canvas.db_for(project)
        store = getattr(canvas, "desktop_v3_state", None) or DesktopV3State(canvas)
        rows, disciplines, states, rounds, queue, blocked, duels = _queue(
            db, project, workspace, discipline, view["digest"], store.current(project, workspace)["state"])
        if duels:
            return _duel_head(db, project, workspace, *duels[0], blocked)
        if not queue:
            return {"fragment": None, **_blocked(blocked)}
        _key, fragment_id, gate, needs, proposal = queue[0]
        row, found = rows[fragment_id], disciplines[fragment_id]
        result = {"fragment": {"id": fragment_id, "title": row["title"], "effectiveDiscipline": found,
                               "revision": row["revision"], "gatesStale": states[fragment_id]["stale"],
                               **round_fields(rounds, fragment_id)},
                  "gate": gate, "needs": needs, "hint": f"{HINTS[gate]} {NEEDS_HINT[needs]}",
                  "lessons": live_lessons(db, project, workspace, {found}, NEXT_LIMIT), **_blocked(blocked)}
        if proposal:
            result["proposal"] = proposal
        return result


def _duel_hint(state):
    if state["onTurn"]:
        waiting = ", ".join(f"strana {item['side']} (odpověď na grill {item['grillId']})" for item in state["onTurn"])
        return (f"Duel: na tahu {waiting}. Odpověz op duel-turn {{fragmentId, expectedRevision, side, kind: answer, text, "
                "refs: [grillId]}.")
    if state["canDecide"]:
        return "Duel: žádná otevřená grill a pravidlo už rozhoduje; soudci mohou dál hodnotit (op duel-score), nebo rozhodni op duel-decide."
    return ("Duel: na tahu jsou strany (op duel-turn claim, grill, synthesis) a soudci mimo strany (op duel-score); "
            "rozhodne op duel-decide, až to pravidlo dovolí.")


def _duel_head(db, project, workspace, row, duel, blocked):
    """Otevřený duel jako hlava fronty: `needs: duel`, kdo je na tahu a zda už jde rozhodnout."""
    state = duel_state(duel)
    found = row["discipline"]
    return {"fragment": {"id": row["fragment_id"], "title": row["title"], "effectiveDiscipline": found,
                         "revision": row["revision"], "kind": "duel"},
            "gate": None, "needs": "duel", "hint": _duel_hint(state), "onTurn": state["onTurn"],
            "canDecide": state["canDecide"], "subject": dict(duel["subject"]),
            "lessons": live_lessons(db, project, workspace, {found}, NEXT_LIMIT) if found else [], **_blocked(blocked)}


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
