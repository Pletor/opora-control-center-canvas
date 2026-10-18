"""Uplatnění vítězného směru duelu při `duel-decide` (docs/schranka-duel.md §3.2), v téže transakci.

- `subject: fragment` + adopt/synthesis: předmět dostane novou revizi s `decision.text` (append-only). Otisk vstupů
  se změní, brány se zneplatní a smyčka jde znovu od scoped. Vazbu `incumbent.ref` = {předmět, revize posledního
  TEXTU} zapisuje server při `duel-open`; změnil-li se text předmětu mezitím, směr se neuplatní (cizí změna zůstane).
  Revize jen s metadaty (brány, MVP) uplatnění neblokují. Nová revize nese u fragmentu `brief` všechny brány vypnuté
  (značky `value: false`, jako kaskáda vypnutí v `brief_vault_gates`): návrat ke staršímu textu tak neoživí brány ani
  návrhy, které k jeho otisku vznikly dřív. Předmět nebo předek smazaný po otevření duelu = nic se nezapíše.
- Totožný text (přesná shoda řetězce) = explicitní no-op: `applied: false` „předmět už má tento text (beze změny)“,
  žádná revize, brány beze změny. Platí pro fragment i představu.
- `subject: project` + adopt/synthesis: představa rozsahu dostane nový text, jen když `duel.visionRef` je pořád
  aktuální obsahová verze představy (`_vision_ref` v `brief_vault_duel`, verze `directionRevision`); jinak
  `applied: false` „představa se mezitím změnila“.
- `subject: node`: plátno se nemění, kartu upraví člověk nebo agent.
- `keep`: předmět beze změny.
"""

from backend.editor.brief_vault.brief_vault_details import write_details
from backend.editor.brief_vault.brief_vault_gate_rules import GATES, encode_gates, input_hash
from backend.editor.brief_vault.brief_vault_model import MAX_BY, effective_disciplines, latest_rows, text_revisions
from backend.editor.brief_vault.brief_vault_tree import live_ids

NODE_REASON = "kartu upraví člověk nebo agent podle decision.text"
KEEP_REASON = "keep: platný směr zůstává, předmět beze změny"
SAME_REASON = "předmět už má tento text (beze změny)"
DELETED_REASON = "předmět nebo jeho předek je smazaný"


def text_revision(w, fragment_id):
    """Revize, ve které se naposledy změnil text fragmentu (obsahová verze předmětu)."""
    return text_revisions(w.db, w.project, w.workspace, [fragment_id]).get(fragment_id)


def fragment_ref(w, fragment_id):
    return {"fragmentId": fragment_id, "revision": text_revision(w, fragment_id)}


def _gates_off(w, row, text, rows):
    """Brány nové revize: všechny vypnuté značkou (smyčka znovu od scoped, starší návrhy neplatí); jiný druh beze změny."""
    if row["kind"] != "brief":
        return row["gates"]
    digest = input_hash(row["title"], text, effective_disciplines(rows).get(row["fragment_id"]))
    entry = {"value": False, "payload": None, "by": w.by[:MAX_BY], "actor": w.actor, "at": w.at,
             "inputHash": digest, "revision": row["revision"] + 1}
    return encode_gates({gate: dict(entry) for gate in GATES})


def _fragment(w, duel_id, duel, decision):
    rows = latest_rows(w.db, w.project, w.workspace)
    row = rows.get(duel["subject"]["id"])
    ref = duel["incumbent"].get("ref")
    if row is None:
        return False, None, "předmět neexistuje", None
    if row["fragment_id"] not in live_ids(rows):
        return False, None, DELETED_REASON, None
    if row["text"] == decision["text"]:
        return False, None, SAME_REASON, None
    if ref is None or ref["fragmentId"] != row["fragment_id"] or text_revision(w, row["fragment_id"]) != ref["revision"]:
        return False, None, "předmět se mezitím změnil", None
    revised = w.revise(row, f"Směr z duelu {duel_id}: {decision['outcome']}", text=decision["text"],
                       gates=_gates_off(w, row, decision["text"], rows))
    return True, revised["revision"], None, revised


def _project(w, duel_id, duel, decision, vision, vision_ref):
    if vision is None:
        return False, None, "rozsah nemá představu", None
    row, fields = vision
    if row["text"] == decision["text"]:
        return False, None, SAME_REASON, None
    if duel.get("visionRef") is None:
        return False, None, "duel nebyl veden proti představě (otevřen před jejím založením)", None
    if duel["visionRef"] != vision_ref(row, fields):
        return False, None, "představa se mezitím změnila", None
    revised = w.revise(row, f"Představa z duelu {duel_id}: {decision['outcome']}", text=decision["text"])
    write_details(w.db, w.project, w.workspace, row["fragment_id"],
                  {**fields, "vision": {**fields["vision"], "directionRevision": revised["revision"]}}, w.at)
    return True, revised["revision"], None, revised


def apply_decision(w, duel_id, duel, decision, vision, vision_ref):
    """Uplatní vítězný směr; vrací (applied, appliedRevision, důvod | None, řádek předmětu | None).
    `vision` = (řádek, fields) představy rozsahu duelu nebo None; `vision_ref` = obsahová verze představy."""
    if decision["outcome"] == "keep":
        return False, None, KEEP_REASON, None
    kind = duel["subject"]["kind"]
    if kind == "node":
        return False, None, NODE_REASON, None
    if kind == "fragment":
        return _fragment(w, duel_id, duel, decision)
    return _project(w, duel_id, duel, decision, vision, vision_ref)
