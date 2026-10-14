"""Poradní externí kontrola brány přes Jev (docs/schranka-neurony.md §7, §9 bod 10).

`POST /api/brief-vault/gate-check` se zeptá poskytovatele Jev (TypeSafe nebo Celeris) jednou otázkou `noul`,
zda kandidátní payload splňuje podmínku brány. Nic nezapisuje a bránu nezapíná; výsledek je jen údaj.

- Revize: `expectedRevision` musí sedět s poslední revizí fragmentu, jinak 409 (agent načte nový stav).
- Povolení: bez výslovného povolení člověka pro (projekt, poskytovatel) v `AppSettings` odpoví
  `{probability: null, reason: "not-allowed"}` a **neodejde žádný síťový požadavek**; samotný klíč nestačí.
- Co odchází: jen název, text (nejvýš 4000 znaků), brána a payload jako `state`. Data fragmentu jsou
  nedůvěryhodná, proto nejsou v otázce; otázka je z pevných textů (`HINTS`) a názvu brány.
- `inputHash` = sha256 kanonického JSON `{state, questions}`, tedy otisk přesně toho, co (by) odešlo.
- Síťové volání běží mimo zámek čtení projektu.
"""

import hashlib
import json

from backend.canvas.graph import valid_id
from backend.editor.brief_vault.brief_vault_gate_rules import HINTS, gate_index, validate_payload
from backend.editor.brief_vault.brief_vault_model import bad_request, fail, latest_rows
from backend.editor.brief_vault.brief_vault_tree import live_ids

KEYS = {"project", "workspace", "fragmentId", "expectedRevision", "gate", "payload"}
MAX_TEXT = 4000
QUESTION_KEY = "satisfied"


def _body(payload):
    if not isinstance(payload, dict) or set(payload) != KEYS:
        bad_request("gate-check vyžaduje přesně pole " + ", ".join(sorted(KEYS)) + ".")
    for key in ("project", "workspace"):
        if not isinstance(payload[key], str) or not payload[key] or len(payload[key]) > 200:
            bad_request(f"{key} musí být neprázdný text do 200 znaků.")
    if not valid_id(payload["fragmentId"]):
        bad_request("fragmentId je neplatné.")
    if type(payload["expectedRevision"]) is not int:
        bad_request("expectedRevision musí být celé číslo.")
    gate_index(payload["gate"])
    validate_payload(payload["gate"], payload["payload"])
    return payload


def _fragment(canvas, body):
    """Název a text poslední revize živého fragmentu `brief`; jiná revize = 409."""
    project, workspace, fragment_id = body["project"], body["workspace"], body["fragmentId"]
    with canvas.reading(project):
        if canvas.view(project, workspace)["readOnly"]:
            fail("pracovní prostor je jen pro čtení.")
        rows = latest_rows(canvas.db_for(project), project, workspace)
        if fragment_id not in rows or fragment_id not in live_ids(rows):
            fail(f"fragment {fragment_id} v tomto pracovním prostoru neexistuje.")
        row = rows[fragment_id]
        if row["revision"] != body["expectedRevision"]:
            fail(f"fragment má revizi {row['revision']}, ne {body['expectedRevision']}; načtěte nový stav.")
        if row["kind"] != "brief":
            bad_request("brány cyklu má jen fragment druhu brief.")
        return row["title"], row["text"]


def question(gate):
    """Otázka jen z pevných textů aplikace; nic z fragmentu."""
    return {QUESTION_KEY: {"type": "noul",
                           "instructions": f"Splňuje payload podmínku brány {gate} ({HINTS[gate]})?"}}


def _probability(answers):
    answer = answers.get(QUESTION_KEY) if isinstance(answers, dict) else None
    value = answer.get("noul") if isinstance(answer, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        return None
    return round(float(value), 3)


def gate_check(canvas, payload, *, settings, provider, evaluate):
    """`{probability, provider, inputHash}`; `probability: null` s `reason` (not-allowed / not-configured / unavailable)."""
    body = _body(payload)
    title, text = _fragment(canvas, body)
    state = {"title": title, "text": text[:MAX_TEXT], "gate": body["gate"], "payload": body["payload"]}
    questions = question(body["gate"])
    digest = hashlib.sha256(json.dumps({"state": state, "questions": questions}, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    result = {"probability": None, "provider": provider, "inputHash": digest}
    if settings is None or not settings.gate_check_allowed(body["project"], provider):
        return {**result, "reason": "not-allowed"}
    key = settings.jev_key(provider)
    if not key:
        return {**result, "reason": "not-configured"}
    probability = _probability(evaluate(state, questions, key=key, provider=provider))
    if probability is None:
        return {**result, "reason": "unavailable"}
    return {**result, "probability": probability}
