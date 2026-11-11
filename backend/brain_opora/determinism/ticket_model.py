"""Ticket jako jednotka práce bez databáze (docs/navrhy/2026-11-03-novy-zaklad.md §3.3): stavy, přechody a těla.

Přechody hlídá jediná funkce `advance`; nepovolený přechod je 409 `ticket_state`. Tělo pro dělníka nenese ID
(podstata, co postavit, otevřené cesty, na co si dát pozor, skills s pinem, kritérium hotovo), strojová vrstva
(`cardId`, `executionId`, `cardVersion`, `department`, `profile`, `pins`, volitelně `intent`) jde vedle. Pole jsou v camelCase jako ostatní druhy brány.
"""
import re

from backend.brain_opora.determinism.gate_payloads import GateError, invalid, shaped
from backend.canvas.graph import valid_id

STATES = ("draft", "issued", "claimed", "in_progress", "needs_answer", "delivered", "verified", "closed", "failed",
          "cancelled")
TRANSITIONS = {
    "draft": ("issued", "cancelled"),
    "issued": ("claimed", "cancelled"),
    "claimed": ("in_progress", "issued", "failed", "cancelled"),  # issued = ticket.release (kancelář bez exekuce)
    "in_progress": ("needs_answer", "delivered", "failed", "cancelled"),
    "needs_answer": ("in_progress", "failed", "cancelled"),
    "delivered": ("verified", "in_progress", "failed"),
    "verified": ("closed",),
    "closed": (), "failed": (), "cancelled": (),
}
FEEDBACK_KINDS = ("bug", "idea", "improvement", "question")
SEVERITIES, DIRECT_LIMIT = ("hint", "course", "stop"), 2000  # `ticket.direct`: pokyn srdce běžícímu dělníkovi (F2)
DEFAULT_SKILLS = ("ponytail@5.3.3",)
TEXT_LIMIT, LIST_LIMIT = 4000, 20
PIN = re.compile(r"/?[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}@[A-Za-z0-9][A-Za-z0-9_.+-]{0,39}")
BRAIN_REF = re.compile(r"opora:brain:(?:skill|tool|workflow|subagent|connector):[A-Za-z0-9][A-Za-z0-9_.-]{0,79}"
                       r"(?:@[0-9a-f]{12})?")  # artefakt Brainu do `pins` (bez verze = aktivní)
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")  # oddělení a profil kanceláře (`department`, `profile`)
MACHINE_ID = re.compile(r"\b(?:gt|gs|ht|tk|tf)_[0-9a-f]{8,}")  # ID brány a ticketu do těla pro dělníka nepatří
BODY_KEYS = ("essence", "build", "doneCriteria")
BODY_OPTIONAL = ("openPaths", "cautions", "skills")
ISSUE_HINT = ('Například {"body": {"essence": "Proč a k čemu.", "build": "Co postavit.", '
              '"doneCriteria": ["npm test projde"]}, "cardId": "hero"}.')


def advance(current, target):
    """Povolený přechod vrátí `target`; jiný je 409 `ticket_state` s výčtem povolených cílů."""
    allowed = TRANSITIONS.get(current, ())
    if target not in allowed:
        raise GateError(409, "ticket_state", f"Ticket ve stavu {current} nejde převést na {target}.",
                        "Povolené přechody: " + (", ".join(allowed) or "žádné, ticket je uzavřený") + ".")
    return target


def _text(value, key, hint):
    if not isinstance(value, str) or not value.strip() or len(value) > TEXT_LIMIT or "\0" in value:
        raise invalid(f"{key} je neprázdný text do {TEXT_LIMIT} znaků.", hint)
    if MACHINE_ID.search(value):
        raise invalid(f"{key} nese ID brány nebo ticketu; tělo pro dělníka je bez ID.",
                      "ID patří do strojové vrstvy (cardId, executionId, cardVersion).")
    return value.strip()


def _texts(value, key, hint, required=False):
    if not isinstance(value, list) or len(value) > LIST_LIMIT or (required and not value):
        raise invalid(f"{key} je seznam textů (nejvýš {LIST_LIMIT}{', aspoň jeden' if required else ''}).", hint)
    return [_text(item, key, hint) for item in value]


def body_payload(body):
    """Tělo pro dělníka s doplněnými výchozími hodnotami (`skills` = ponytail)."""
    shaped(body, BODY_KEYS, BODY_OPTIONAL, hint=ISSUE_HINT)
    skills = body.get("skills", list(DEFAULT_SKILLS))
    if not isinstance(skills, list) or len(skills) > LIST_LIMIT or not all(
            isinstance(pin, str) and PIN.fullmatch(pin) for pin in skills):
        raise invalid("skills je seznam pinů /název@verze.", 'Například "skills": ["ponytail@5.3.3"].')
    return {"essence": _text(body["essence"], "essence", ISSUE_HINT), "build": _text(body["build"], "build", ISSUE_HINT),
            "openPaths": _texts(body.get("openPaths", []), "openPaths", ISSUE_HINT),
            "cautions": _texts(body.get("cautions", []), "cautions", ISSUE_HINT), "skills": skills,
            "doneCriteria": _texts(body["doneCriteria"], "doneCriteria", ISSUE_HINT, required=True)}


def _intent(value):
    """`machine.intent` `{workflowVersionId, nodeIds}`: kritéria `intent.done` schváleného záměru stránky, která ticket
    naplňuje (docs/navrhy/2026-11-03-platno-2-zamer-stranky.md §4). Verzi a uzly ověří obsluha proti registru."""
    hint = 'Například "intent": {"workflowVersionId": "<id aktivní verze>", "nodeIds": ["odeslano"]}.'
    shaped(value, ("workflowVersionId", "nodeIds"), ids=("workflowVersionId",), hint=hint)
    nodes = value["nodeIds"]
    if not isinstance(nodes, list) or not nodes or len(nodes) > LIST_LIMIT or not all(map(valid_id, nodes)):
        raise invalid(f"intent.nodeIds je 1–{LIST_LIMIT} ID uzlů intent.done.", hint)
    return {"workflowVersionId": value["workflowVersionId"], "nodeIds": list(dict.fromkeys(nodes))}


def issue_payload(payload):
    """`ticket.issue` `{body, cardId?, executionId?, cardVersion?, department?, profile?, pins?, intent?, workspace?}` →
    `(tělo, strojová vrstva)`; `department` / `profile` (oddělení a profil kanceláře) jsou krátké slugy nebo null.
    `pins` jsou ID artefaktů Brainu (`opora:brain:skill:<name>[@sha12]`); na piny s verzí a zipem je přeloží obsluha
    (`backend/brain/pins.py`). `intent` (`_intent`) jde do strojové vrstvy jen zadaný. `workspace` (prostor karty, jinak
    prostor tokenu srdce) čte obsluha zvlášť."""
    shaped(payload, ("body",), ("cardId", "executionId", "cardVersion", "department", "profile", "pins", "intent",
                                "workspace"),
           ids=("cardId", "executionId", "workspace"), hint=ISSUE_HINT)
    version = payload.get("cardVersion")
    if version is not None and (type(version) is not int or version < 0):
        raise invalid("cardVersion je celé číslo ≥ 0.", ISSUE_HINT)
    for key in ("department", "profile"):
        value = payload.get(key)
        if value is not None and not (isinstance(value, str) and SLUG.fullmatch(value)):
            raise invalid(f"{key} je krátký slug (a-z, 0-9, -, do 40 znaků) nebo null.", 'Například "department": "design".')
    pins = payload.get("pins", [])
    if not isinstance(pins, list) or len(pins) > LIST_LIMIT or not all(
            isinstance(ref, str) and BRAIN_REF.fullmatch(ref) for ref in pins):
        raise invalid("pins je seznam ID artefaktů Brainu (případně s @sha12).",
                      'Například "pins": ["opora:brain:skill:vyslech"].')
    machine = {key: payload.get(key) for key in ("cardId", "executionId", "cardVersion", "department", "profile")}
    intent = {"intent": _intent(payload["intent"])} if "intent" in payload else {}
    return body_payload(payload["body"]), {**machine, "pins": pins, **intent}


WORK_PORTS = ("next", "block")  # vazby práce: pořadí (`next`) a výsledek bloku karty (`block`, docs/karta-pro-agenty.md)


def neighbors(graph, card_id):
    """Následníci a předchůdci karty z grafu jejího prostoru (bez modelu): `{successors, predecessors}`, každý
    `[{cardId, name, essence?}]` v pořadí vazeb. Následník je cíl vazby `next` z karty i vazby `block` z portu jejího
    bloku, předchůdce zdroj takové vazby do karty; `essence` je účel karty, když ho má. Karta mimo graf nemá nikoho."""
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    found = {"successors": [], "predecessors": []}
    if card_id not in nodes:
        return found
    for edge in graph.get("edges", []):
        if "relation" in edge or edge.get("port", "next") not in WORK_PORTS:
            continue
        for key, mine, other in (("successors", "source", "target"), ("predecessors", "target", "source")):
            node = nodes.get(edge[other])
            if edge[mine] != card_id or node is None or any(item["cardId"] == node["id"] for item in found[key]):
                continue
            purpose = (node.get("purpose") or "").strip()
            found[key].append({"cardId": node["id"], "name": node["name"], **({"essence": purpose} if purpose else {})})
    return found


def ticket_id(body, hint):
    return shaped(body, ("ticketId",), ids=("ticketId",), hint=hint)["ticketId"]


def claim_payload(body):
    """`ticket.claim` `{ticketId, executionId?}` → `(ticketId, executionId nebo None)`."""
    hint = 'Například {"ticketId": "tk_…", "executionId": "…"}; executionId vrací start exekuce karty ticketu.'
    shaped(body, ("ticketId",), ("executionId",), ids=("ticketId", "executionId"), hint=hint)
    return body["ticketId"], body.get("executionId")


def feedback_payload(body):
    """`ticket.feedback` `{ticketId, kind, text}` → `(ticketId, kind, text)`."""
    hint = 'Například {"ticketId": "tk_…", "kind": "question", "text": "Smím změnit sdílený styl?"}.'
    shaped(body, ("ticketId", "kind", "text"), ids=("ticketId",), texts=("text",), hint=hint)
    if body["kind"] not in FEEDBACK_KINDS:
        raise invalid("kind je " + ", ".join(FEEDBACK_KINDS) + ".", hint)
    return body["ticketId"], body["kind"], body["text"].strip()


def direct_payload(body):
    """`ticket.direct` `{ticketId, severity, text ≤ 2000}` → `(ticketId, severity, text)`."""
    hint = 'Například {"ticketId": "tk_…", "severity": "course", "text": "Drž se souborů karty, sdílený styl neměň."}.'
    shaped(body, ("ticketId", "severity", "text"), ids=("ticketId",), texts=("text",), limit=DIRECT_LIMIT, hint=hint)
    if body["severity"] not in SEVERITIES:
        raise invalid("severity je " + ", ".join(SEVERITIES) + ".", hint)
    return body["ticketId"], body["severity"], body["text"].strip()


def deliver_payload(body):
    """`ticket.deliver` `{ticketId, summary, sha?, tryout?}` → `(ticketId, {summary, sha?, tryout?})`; `tryout`
    jen projde do `work.apply_report`, které ho ověří."""
    hint = 'Například {"ticketId": "tk_…", "summary": "Hero je hotový, testy zelené.", "sha": "abc1234"}.'
    shaped(body, ("ticketId", "summary"), ("sha", "tryout"), ids=("ticketId",), texts=("summary",), hint=hint)
    if "sha" in body and not (isinstance(body["sha"], str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", body["sha"])):
        raise invalid("sha je výstup git rev-parse HEAD.", hint)
    return body["ticketId"], {**{key: body[key].strip() for key in ("summary", "sha") if key in body},
                              **({"tryout": body["tryout"]} if "tryout" in body else {})}
