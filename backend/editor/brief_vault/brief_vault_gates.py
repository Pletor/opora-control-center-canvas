"""Operace bran cyklu Schránky: `propose`, `reject-proposal`, `gate`, `confirm-lesson`, `drop-lesson`
(docs/schranka-neurony.md §3, §5, §9).

Každý handler dostane `_Write` z `brief_vault.py` (transakce, CAS, autor, čas). Změna brány je nová revize
fragmentu se stejným textem a povinnou `note` (append-only, CAS přes `expectedRevision`). Návrh payloadu
(`propose`) revizi nemění: ukládá se append-only do `brief_gate_proposals` k aktuální revizi a otisku vstupů,
aby čistě booleovský agent mohl bránu jen potvrdit (`gate` s `value: true` bez payloadu, §9 bod 9).
`reject-proposal` zamítne poslední čekající návrh brány (append-only záznam, revize nepřibývá, CAS jen kontrola);
smí ho kdokoli včetně autora návrhu (stažení). Návrhy a zamítnutí čte `brief_vault_proposals`.
Návrhy nejsou stav fragmentu, proto nejsou v revizi ani v uložené verzi plátna. Chybný tvar, brána, payload
nebo pořadí = 400 (`BadRequest`); konflikt stavu (CAS, brána už zapnutá/vypnutá) = 409. Payload bran `planned`
a `placed` skládá server (`brief_vault_placement`) a předá ho v `w.prepared`.
"""

import json
import uuid

from backend.canvas.activity_log import require_human
from backend.editor.brief_vault.brief_vault_gate_rules import (
    GATES,
    NO_PAYLOAD,
    PLAN_GATES,
    dead_end,
    encode_gates,
    gate_index,
    gate_state,
    prediction_error,
    summary,
    validate_payload,
)
from backend.editor.brief_vault.brief_vault_lessons import (
    confirm_lesson,
    create_lesson,
    drop_lesson,
)
from backend.editor.brief_vault.brief_vault_model import (
    MAX_BY,
    bad_request,
    effective_disciplines,
    fail,
    latest_rows,
    public,
)
from backend.editor.brief_vault.brief_vault_proposals import (
    public_proposal,
    reject,
    usable_proposal,
)
from backend.editor.brief_vault.brief_vault_tree import live_ids

OPS = {
    "propose": ({"fragmentId", "expectedRevision", "gate", "payload", "note"}, set()),
    "reject-proposal": ({"fragmentId", "expectedRevision", "gate", "note"}, set()),
    "gate": ({"fragmentId", "expectedRevision", "gate", "value", "note"}, {"payload"}),
    "confirm-lesson": ({"lessonId", "note"}, set()),
    "drop-lesson": ({"lessonId", "note"}, set()),
}
HUMAN_OPS = {"drop-lesson": "Poučení vyřazuje jen člověk; agent ho může potvrdit (confirm-lesson)."}
DECIDED = GATES.index("decided")


def covered(rows, fragment_id, states):
    """Některý předek má platně zapnuté `placed` (fragment je pokrytý předkem, §3)."""
    cursor, seen = rows[fragment_id]["parent_id"], set()
    while cursor in rows and cursor not in seen:
        seen.add(cursor)
        if "placed" in (states.get(cursor) or {"on": []})["on"]:
            return True
        cursor = rows[cursor]["parent_id"]
    return False


def _context(w, payload):
    """CAS, živý fragment druhu `brief` s platnou disciplínou a jeho brány."""
    row = w.checked(payload)
    rows = latest_rows(w.db, w.project, w.workspace)
    if row["fragment_id"] not in live_ids(rows):
        fail("předek fragmentu je smazaný; brány jdou jen na živém fragmentu.")
    if row["kind"] != "brief":
        bad_request("brány cyklu má jen fragment druhu brief.")
    disciplines = effective_disciplines(rows)
    discipline = disciplines.get(row["fragment_id"])
    if discipline is None:
        bad_request("fragment nemá disciplínu (ani po předcích); přiřaďte ji op set-discipline.")
    states = {fid: gate_state(rows[fid], disciplines.get(fid)) for fid in rows if disciplines.get(fid)}
    return row, rows, discipline, states


def _kept(state):
    """Záznamy, které nová revize převezme: platně zapnuté brány a značky vypnutí (zneplatněné záznamy odpadnou)."""
    return {gate: entry for gate, entry in state["entries"].items()
            if gate in state["on"] or (isinstance(entry, dict) and entry.get("value") is False)}


def _entry(w, row, state, value, payload=None):
    return {"value": value, "payload": payload, "by": w.by[:MAX_BY], "actor": w.actor, "at": w.at,
            "inputHash": state["hash"], "revision": row["revision"] + 1}


def _off_from(w, row, state, entries, index):
    """Vypne bránu `index` a všechny další (kaskáda §3); payloady zůstanou v historii revizí."""
    for gate in GATES[index:]:
        entries[gate] = _entry(w, row, state, False)
    return entries


def propose(w, payload, node_ids):
    gate = payload["gate"]
    index = gate_index(gate)
    if gate in NO_PAYLOAD:
        bad_request(f"brána {gate} payload nemá a návrh nepotřebuje; zapněte ji op gate.")
    validate_payload(gate, payload["payload"])
    row, _rows, _discipline, states = _context(w, payload)
    state = states[row["fragment_id"]]
    if dead_end(state) and index > DECIDED:
        bad_request("fragment je slepá ulička (decided = no); brány 5–8 nejdou.")
    if gate in state["on"]:
        fail(f"brána {gate} je zapnutá; změna payloadu = vypnout a znovu zapnout.")
    seq = w.db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM brief_gate_proposals WHERE project_id=? AND workspace_id=?",
                       (w.project, w.workspace)).fetchone()[0]
    proposal_id = uuid.uuid4().hex
    w.db.execute("INSERT INTO brief_gate_proposals(project_id,workspace_id,id,fragment_id,fragment_revision,gate,input_hash,"
                 "payload,note,by,actor,at,seq) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (w.project, w.workspace, proposal_id, row["fragment_id"], row["revision"], gate, state["hash"],
                  json.dumps(payload["payload"], ensure_ascii=False), payload["note"], w.by[:MAX_BY], w.actor, w.at, seq))
    found = w.db.execute("SELECT * FROM brief_gate_proposals WHERE project_id=? AND workspace_id=? AND id=?",
                         (w.project, w.workspace, proposal_id)).fetchone()
    return {"proposal": public_proposal(found)}


def reject_proposal(w, payload, node_ids):
    gate_name = payload["gate"]
    gate_index(gate_name)
    if gate_name in NO_PAYLOAD:
        bad_request(f"brána {gate_name} návrh nemá; není co zamítnout.")
    row, _rows, _discipline, states = _context(w, payload)
    state = states[row["fragment_id"]]
    if gate_name in state["on"]:
        fail(f"brána {gate_name} je zapnutá; návrh už platí. Nesouhlas = vypnout bránu (op gate value: false).")
    proposal = usable_proposal(w.db, w.project, w.workspace, row["fragment_id"], gate_name, state)
    if proposal is None:
        fail(f"brána {gate_name} nemá čekající návrh; není co zamítnout.")
    rejection = reject(w.db, w.project, w.workspace, proposal, payload["note"], w.by[:MAX_BY], w.actor, w.at)
    return {"rejected": {**proposal, "status": "rejected", "rejection": rejection}}


def _gate_payload(w, payload, row, state, gate):
    """Payload zapínané brány: z požadavku, jinak poslední návrh pro aktuální otisk (§9 bod 9)."""
    if gate in NO_PAYLOAD:
        return None
    if "payload" in payload:
        return payload["payload"]
    proposal = usable_proposal(w.db, w.project, w.workspace, row["fragment_id"], gate, state)
    if proposal is None:
        bad_request(f"chybí návrh brány {gate}: pošlete op propose (nebo payload v op gate).")
    return validate_payload(gate, proposal["payload"])


def gate(w, payload, node_ids):
    gate_name, value = payload["gate"], payload["value"]
    index = gate_index(gate_name)
    if type(value) is not bool:
        bad_request("value musí být true nebo false.")
    if "payload" in payload:
        if not value:
            bad_request("vypnutí brány payload nemá.")
        validate_payload(gate_name, payload["payload"])
    row, rows, discipline, states = _context(w, payload)
    state = states[row["fragment_id"]]
    if covered(rows, row["fragment_id"], states):
        require_human(w.actor, "Fragment je pokrytý předkem s bránou placed; jeho brány přepíná jen člověk.")
    entries, result = _kept(state), {}
    if not value:
        if gate_name not in state["on"]:
            fail(f"brána {gate_name} je už vypnutá (nebo zneplatněná); není co vypnout.")
        _off_from(w, row, state, entries, index)
    else:
        if gate_name in state["on"]:
            fail(f"brána {gate_name} je už zapnutá; změna payloadu = vypnout a znovu zapnout.")
        if len(state["on"]) < index:
            bad_request(f"bránu {gate_name} jde zapnout až po bráně {GATES[len(state['on'])]} (pořadí §3).")
        if dead_end(state) and index > DECIDED:
            bad_request("fragment je slepá ulička (decided = no); brány 5–8 nejdou.")
        given = _gate_payload(w, payload, row, state, gate_name)
        if gate_name in PLAN_GATES:
            # Plán a jeho vložení skládá server před transakcí (brief_vault_placement); bez něj se nezapíná.
            given = getattr(w, "prepared", None)
            if given is None:
                fail(f"bránu {gate_name} se nepodařilo připravit (plán); načtěte stav a zkuste to znovu.")
        if gate_name == "verified":
            prediction = state["entries"]["synthesized"]["payload"]["prediction"]
            given = {**given, "predictionError": prediction_error(prediction, given["actual"])}
        if gate_name == "decided" and given["verdict"] == "other":
            # Vrátit k přepracování: synthesized a decided se v téže operaci vypnou, verdikt zůstane v záznamu.
            _off_from(w, row, state, entries, GATES.index("synthesized"))
            entries["decided"] = _entry(w, row, state, False, given)
            result["returnedTo"] = "synthesized"
        else:
            entries[gate_name] = _entry(w, row, state, True, given)
    revised = w.revise(row, payload["note"], gates=encode_gates(entries))
    if gate_name == "learned" and value:
        cycle = state["entries"]["synthesized"]["revision"]
        result["lesson"], result["lessonCreated"] = create_lesson(w, row["fragment_id"], cycle, discipline, given)
    return {"fragment": public(revised), **summary(gate_state(revised, discipline)), **result}


HANDLERS = {"propose": propose, "reject-proposal": reject_proposal, "gate": gate, "confirm-lesson": confirm_lesson,
            "drop-lesson": drop_lesson}
