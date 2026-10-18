"""Brány plánu struktury `planned` a `placed` (docs/schranka-neurony.md §4, §9 body 1 a 2).

`planned` (zapnutí): server pro fragment sestaví plán (`brief_vault_plan`), ověří ho přes `/api/canvas-plan`
s `dryRun` a uloží neměnný payload `{planId, generator, sourceRevisions, sourceHashes, scope, digest, scopeDigest,
plan, hash, summary}` (`digest` = celé plátno v okamžiku plánu, jen pro informaci). `sourceHashes` = otisk vstupů (název + text + platná disciplína) každého zdrojového fragmentu: zápis
brány revizi zvedne, ale otisk nezmění, takže plán dál platí.

`placed` (zapnutí) je jediná operace pod zámkem grafu: CAS fragmentu, platné `planned` (zneplatněné = 409),
`planned` novější než poslední vypnutí `placed` (znovu vložit = nové `planned`), shodné otisky zdrojů, stejný
generátor, shodný `scopeDigest` kontejneru plánu a znovu sestavený plán se stejným otiskem (to ověří i jednoznačnost
značek a to, že oblast či sektor mezitím nevznikly jinde). Digest **celého** plátna ani revize celého stavu se
neporovnávají: mění je i souběžné smyčky jiných disciplín (K12). Pak `apply_plan` právě uloženého plánu s digestem
aktuálního pohledu a `expectedRevision` položek `extend` z aktuálního stavu (vše pod týmž zámkem grafu) a v téže transakci (`after_write`) revize fragmentu se zapnutou `placed`. Konflikt = 409
bez vedlejších účinků; selhání zápisu vrátí dávku i bránu. Vypnutí `placed` jde běžnou cestou a karty nemaže.
Zápis na plátno schvaluje člověk v asistentovi stejně jako `/api/canvas-plan` (`approvals.summary_of`).
Pojistka zápisu (§11): po ověření a **před** `apply_plan` se pod týmž zámkem grafu uloží verze plátna se štítkem
(autor verze) „před placed <název fragmentu>“ (`CanvasVersions.checkpoint`); když uložení selže, `placed` nic nezapíše.
"""

import uuid

from backend.canvas.canvas_plan import apply_plan
from backend.editor.brief_vault import brief_vault_gates as gates
from backend.editor.brief_vault.brief_vault_gate_rules import (
    GATES,
    dead_end,
    gate_state,
    input_hash,
)
from backend.editor.brief_vault.brief_vault_model import (
    bad_request,
    effective_disciplines,
    fail,
    latest_rows,
)
from backend.editor.brief_vault.brief_vault_plan import GENERATOR, dry_plan, plan_hash, read_plan
from backend.editor.brief_vault.brief_vault_plan_update import with_revisions
from backend.editor.brief_vault.brief_vault_tree import live_ids
from backend.editor.canvas_versions.canvas_versions import CanvasVersions

CHANGED = "plán se změnil, znovu planned"
BEFORE_PLACED = "před placed "


def wants(payload):
    """Zapnutí brány, jejíž payload skládá server."""
    return payload.get("op") == "gate" and payload.get("gate") in ("planned", "placed") and payload.get("value") is True


def _context(canvas, payload):
    """Poslední revize, řádky, disciplína a brány fragmentu; None, když zapnutí stejně neprojde (chybu dá `gate`)."""
    project, workspace = payload["project"], payload["workspace"]
    with canvas.lock_for(project):
        rows = latest_rows(canvas.db_for(project), project, workspace)
    row = rows.get(payload.get("fragmentId")) if isinstance(payload.get("fragmentId"), str) else None
    if row is None or row["fragment_id"] not in live_ids(rows) or row["kind"] != "brief" \
            or row["revision"] != payload.get("expectedRevision"):
        return None
    discipline = effective_disciplines(rows).get(row["fragment_id"])
    if discipline is None:
        return None
    return rows, row, gate_state(row, discipline)


def _planned(vault, payload, actor):
    """Payload brány `planned` (plán + dryRun), nebo None, když fragment na `planned` není připravený."""
    found = _context(vault.canvas, payload)
    if found is None:
        return None
    _rows, row, state = found
    index = GATES.index("planned")
    if len(state["on"]) != index or dead_end(state):
        return None
    checked = dry_plan(vault.canvas, vault.state, payload["project"], payload["workspace"], [row["fragment_id"]], actor)
    if checked["skipped"]:
        fail(f"plán fragmentu má víc než {len(checked['plan']['nodes'])} uzlů jedné dávky; rozdělte fragment.")
    return {"planId": uuid.uuid4().hex, "generator": GENERATOR, "sourceRevisions": checked["sourceRevisions"],
            "sourceHashes": checked["sourceHashes"], "scope": checked["scopes"][0], "digest": checked["digest"],
            "scopeDigest": checked["scopeDigest"], "plan": checked["plan"], "hash": checked["hash"], "summary": checked["summary"]}


def _stored_plan(vault, payload, view):
    """Uložený plán `planned`, který smí `placed` vložit; jinak 409 (nebo 400 pro pořadí), nic se nezapíše."""
    project, workspace = payload["project"], payload["workspace"]
    with vault.canvas.lock_for(project):
        rows = latest_rows(vault.canvas.db_for(project), project, workspace)
    row = rows.get(payload["fragmentId"]) if isinstance(payload["fragmentId"], str) else None
    if row is None or row["fragment_id"] not in live_ids(rows):
        fail(f"fragment {payload['fragmentId']} v tomto pracovním prostoru neexistuje nebo je smazaný.")
    if row["revision"] != payload["expectedRevision"]:
        fail(f"fragment se změnil (revize {row['revision']}, očekávána {payload['expectedRevision']}); načtěte ho znovu.")
    if row["kind"] != "brief":
        bad_request("brány cyklu má jen fragment druhu brief.")
    disciplines = effective_disciplines(rows)
    if disciplines.get(row["fragment_id"]) is None:
        bad_request("fragment nemá disciplínu (ani po předcích); přiřaďte ji op set-discipline.")
    state = gate_state(row, disciplines[row["fragment_id"]])
    planned, placed = state["entries"].get("planned"), state["entries"].get("placed")
    if "placed" in state["on"]:
        fail("brána placed je už zapnutá; plán je vložený.")
    if "planned" not in state["on"]:
        if planned and planned.get("value") is True:
            fail(f"{CHANGED} (zadání fragmentu se od plánu změnilo).")
        bad_request(f"bránu placed jde zapnout až po bráně {GATES[len(state['on'])]} (pořadí §3).")
    if placed and placed.get("value") is False and planned["revision"] <= placed["revision"]:
        fail("plán už byl vložený; opětovné vložení vyžaduje nové planned (vypněte a znovu zapněte planned).")
    stored = planned["payload"]
    for fragment_id, expected in stored["sourceHashes"].items():
        source = rows.get(fragment_id)
        if source is None or fragment_id not in live_ids(rows) or \
                input_hash(source["title"], source["text"], disciplines.get(fragment_id)) != expected:
            fail(f"{CHANGED} (fragment {fragment_id} se od plánu změnil).")
    if stored.get("generator") != GENERATOR or "scopeDigest" not in stored:
        fail(f"{CHANGED} (plán je ze starší verze generátoru).")
    rebuilt = read_plan(vault.canvas, vault.state, project, workspace, view, [row["fragment_id"]])
    if rebuilt["scopeDigest"] != stored["scopeDigest"]:
        fail(f"{CHANGED} (kontejner plánu na plátně se od plánu změnil).")
    if plan_hash(rebuilt["plan"]) != stored["hash"] or plan_hash(stored["plan"]) != stored["hash"]:
        fail(f"{CHANGED} (plán by dnes vypadal jinak).")
    return stored, row["title"], with_revisions(stored["plan"], rebuilt["plan"])


def run(vault, payload, view, node_ids, make_write, actor):
    """Zapnutí `planned` nebo `placed`; volající drží zámek grafu a ověřil, že prostor není jen pro čtení."""
    canvas, project = vault.canvas, payload["project"]
    if payload["gate"] == "planned":
        prepared = _planned(vault, payload, actor)
        db = canvas.db_for(project)
        with canvas.lock_for(project), db:
            db.execute("BEGIN IMMEDIATE")
            w = make_write(db)
            w.prepared = prepared
            return {"ok": True, "op": "gate", **gates.gate(w, payload, node_ids)}
    stored, title, plan = _stored_plan(vault, payload, view)
    # Pojistka zápisu (§11): verze plátna před vložením; výjimka = placed se nezapíše (ValueError 409, jinak 500).
    CanvasVersions(canvas, vault.state).checkpoint(project, payload["workspace"], BEFORE_PLACED + title, actor=actor)
    done = {}

    def after_write(db, refs):
        w = make_write(db)
        w.prepared = {"planId": stored["planId"], "hash": stored["hash"], "refs": dict(refs)}
        done["result"] = gates.gate(w, payload, node_ids)

    applied = apply_plan(canvas, {"project": project, "workspace": payload["workspace"], "digest": view["digest"],
                                  "plan": plan}, actor=actor, after_write=after_write)
    return {"ok": True, "op": "gate", **done["result"],
            "placement": {"planId": stored["planId"], "refs": applied["refs"], "summary": applied["summary"],
                          "digest": applied["digest"], "revision": applied["revision"]}}
