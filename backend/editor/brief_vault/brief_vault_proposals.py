"""Návrhy payloadu bran a jejich zamítnutí (docs/schranka-neurony.md §9 bod 9, §11).

Návrh (`brief_gate_proposals`) i zamítnutí (`brief_gate_proposal_rejections`) jen přibývají; nejsou stav fragmentu,
proto nejsou v revizi ani v uložené verzi plátna. **Použitelný** je poslední návrh brány pro aktuální otisk vstupů,
podaný ve stejné nebo pozdější revizi než poslední vypnutí brány a nezamítnutý. Zamítnutý poslední návrh starší
návrh neoživí: brána znovu čeká na nový návrh (`/next` vrací `needs: "proposal"`).

Detail fragmentu nese `proposals`: poslední návrh každé brány s payloadem pro aktuální otisk se stavem
`pending` (čeká na potvrzení), `rejected` (zamítnutý op reject-proposal, nebo brána vypnutá až po návrhu) nebo
`used` (brána z něj vznikla; u `decided: other` i vypnutý záznam s jeho verdiktem).
"""

import json
import uuid

from backend.editor.brief_vault.brief_vault_gate_rules import GATES, NO_PAYLOAD

_LATEST = ("SELECT p.*, r.id AS rejection_id, r.note AS rejection_note, r.by AS rejection_by, r.actor AS rejection_actor,"
           " r.at AS rejection_at FROM brief_gate_proposals AS p LEFT JOIN brief_gate_proposal_rejections AS r"
           " ON r.project_id=p.project_id AND r.workspace_id=p.workspace_id AND r.proposal_id=p.id"
           " WHERE p.project_id=? AND p.workspace_id=? AND p.fragment_id=? AND p.gate=? AND p.input_hash=?"
           " AND p.fragment_revision>=? ORDER BY p.seq DESC LIMIT 1")


def public_proposal(row):
    return {"id": row["id"], "fragmentId": row["fragment_id"], "revision": row["fragment_revision"], "gate": row["gate"],
            "payload": json.loads(row["payload"]), "inputHash": row["input_hash"], "note": row["note"], "by": row["by"],
            "actor": row["actor"], "at": row["at"]}


def _rejection(row):
    if row["rejection_id"] is None:
        return None
    return {"id": row["rejection_id"], "note": row["rejection_note"], "by": row["rejection_by"],
            "actor": row["rejection_actor"], "at": row["rejection_at"]}


def _since(state, gate):
    """Revize posledního vypnutí brány (návrhy před ní neplatí), jinak 0."""
    entry = state["entries"].get(gate)
    return entry["revision"] if isinstance(entry, dict) and entry.get("value") is False else 0


def _latest(db, project, workspace, fragment_id, gate, input_hash, since=0):
    return db.execute(_LATEST, (project, workspace, fragment_id, gate, input_hash, since)).fetchone()


def usable_proposal(db, project, workspace, fragment_id, gate, state):
    """Poslední návrh brány pro aktuální otisk vstupů po posledním vypnutí brány, pokud není zamítnutý; jinak None."""
    row = _latest(db, project, workspace, fragment_id, gate, state["hash"], _since(state, gate))
    return public_proposal(row) if row and row["rejection_id"] is None else None


def reject(db, project, workspace, proposal, note, by, actor, at):
    """Záznam zamítnutí návrhu (append-only, jeden na návrh); vrací zamítnutí."""
    rejection = {"id": uuid.uuid4().hex, "note": note, "by": by, "actor": actor, "at": at}
    db.execute("INSERT INTO brief_gate_proposal_rejections(project_id,workspace_id,id,proposal_id,fragment_id,"
               "fragment_revision,gate,note,by,actor,at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (project, workspace, rejection["id"], proposal["id"], proposal["fragmentId"], proposal["revision"],
                proposal["gate"], note, by, actor, at))
    return rejection


def _without_error(payload):
    return {key: value for key, value in payload.items() if key != "predictionError"} if isinstance(payload, dict) else payload


def _used(proposal, history):
    """Některá pozdější revize zapsala bránu s payloadem tohoto návrhu a jeho otiskem."""
    for row in history:
        if row["revision"] <= proposal["revision"] or not row.get("gates"):
            continue
        try:
            entry = json.loads(row["gates"]).get(proposal["gate"])
        except (TypeError, ValueError, AttributeError):
            continue
        if (isinstance(entry, dict) and entry.get("revision") == row["revision"]
                and entry.get("inputHash") == proposal["inputHash"]
                and _without_error(entry.get("payload")) == proposal["payload"]):
            return True
    return False


def proposals_of(db, project, workspace, fragment_id, state, history):
    """`{brána: návrh + status (+ rejection)}` pro brány s payloadem; chybějící brána = žádný návrh pro tento otisk."""
    result = {}
    for gate in GATES:
        if gate in NO_PAYLOAD:
            continue
        row = _latest(db, project, workspace, fragment_id, gate, state["hash"])
        if row is None:
            continue
        proposal, rejection = public_proposal(row), _rejection(row)
        if rejection is None and _used(proposal, history):
            status = "used"
        elif rejection is None and proposal["revision"] < _since(state, gate):
            entry = state["entries"][gate]
            status, rejection = "rejected", {"id": None, "note": "brána vypnuta po návrhu", "by": entry.get("by", ""),
                                             "actor": entry.get("actor", ""), "at": entry.get("at", ""), "gateOff": True}
        else:
            status = "rejected" if rejection else "pending"
        result[gate] = {**proposal, "status": status, "rejection": rejection}
    return result
