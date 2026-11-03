"""Ticket jako jednotka práce bez databáze (docs/navrhy/2026-11-03-novy-zaklad.md §3.3): stavy, přechody a těla.

Přechody hlídá jediná funkce `advance`; nepovolený přechod je 409 `ticket_state`. Tělo pro dělníka nenese ID
(podstata, co postavit, otevřené cesty, na co si dát pozor, skills s pinem, kritérium hotovo), strojová vrstva
(`cardId`, `executionId`, `cardVersion`) jde vedle. Pole jsou v camelCase jako ostatní druhy brány.
"""
import re

from backend.brain_opora.determinism.gate_payloads import GateError, invalid, shaped

STATES = ("draft", "issued", "claimed", "in_progress", "needs_answer", "delivered", "verified", "closed", "failed",
          "cancelled")
TRANSITIONS = {
    "draft": ("issued", "cancelled"),
    "issued": ("claimed", "cancelled"),
    "claimed": ("in_progress", "failed", "cancelled"),
    "in_progress": ("needs_answer", "delivered", "failed", "cancelled"),
    "needs_answer": ("in_progress", "failed", "cancelled"),
    "delivered": ("verified", "in_progress", "failed"),
    "verified": ("closed",),
    "closed": (), "failed": (), "cancelled": (),
}
FEEDBACK_KINDS = ("bug", "idea", "improvement", "question")
DEFAULT_SKILLS = ("ponytail@5.3.3",)
TEXT_LIMIT, LIST_LIMIT = 4000, 20
PIN = re.compile(r"/?[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}@[A-Za-z0-9][A-Za-z0-9_.+-]{0,39}")
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


def issue_payload(payload):
    """`ticket.issue` `{body, cardId?, executionId?, cardVersion?}` → `(tělo, strojová vrstva)`."""
    shaped(payload, ("body",), ("cardId", "executionId", "cardVersion"), ids=("cardId", "executionId"),
           hint=ISSUE_HINT)
    version = payload.get("cardVersion")
    if version is not None and (type(version) is not int or version < 0):
        raise invalid("cardVersion je celé číslo ≥ 0.", ISSUE_HINT)
    machine = {key: payload.get(key) for key in ("cardId", "executionId", "cardVersion")}
    return body_payload(payload["body"]), machine


def ticket_id(body, hint):
    return shaped(body, ("ticketId",), ids=("ticketId",), hint=hint)["ticketId"]


def feedback_payload(body):
    """`ticket.feedback` `{ticketId, kind, text}` → `(ticketId, kind, text)`."""
    hint = 'Například {"ticketId": "tk_…", "kind": "question", "text": "Smím změnit sdílený styl?"}.'
    shaped(body, ("ticketId", "kind", "text"), ids=("ticketId",), texts=("text",), hint=hint)
    if body["kind"] not in FEEDBACK_KINDS:
        raise invalid("kind je " + ", ".join(FEEDBACK_KINDS) + ".", hint)
    return body["ticketId"], body["kind"], body["text"].strip()


def deliver_payload(body):
    """`ticket.deliver` `{ticketId, summary, sha?}` → `(ticketId, {summary, sha?})`."""
    hint = 'Například {"ticketId": "tk_…", "summary": "Hero je hotový, testy zelené.", "sha": "abc1234"}.'
    shaped(body, ("ticketId", "summary"), ("sha",), ids=("ticketId",), texts=("summary",), hint=hint)
    if "sha" in body and not (isinstance(body["sha"], str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", body["sha"])):
        raise invalid("sha je výstup git rev-parse HEAD.", hint)
    return body["ticketId"], {key: body[key].strip() for key in ("summary", "sha") if key in body}
