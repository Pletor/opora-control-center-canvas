"""Schémata JSON druhů brány (docs/brain-control-api.md §2): vstup a výstup každého druhu a jeden úplný příklad.

Jen data pro tabulku `kinds.py`: z nich vzniká `GET /api/gate/kinds` (a později nástroje MCP). Kontroly samotné
jsou funkce v `gate_payloads.py` a `ticket_model.py`; test `test_kinds.py` hlídá, že příklady projdou kontrolou
i schématem a že výstup obsluhy schématu odpovídá.
"""
TEXT = {"type": "string", "minLength": 1}
ID = {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,80}$"}
TEXTS = {"type": "array", "items": TEXT}
ANY = {}


def obj(properties, required=(), extra=False):
    """Objekt s danými poli; `required` povinná, jiná pole jen s `extra`."""
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": extra}


def nullable(schema):
    return {**schema, "type": [schema["type"], "null"]}


EMPTY = obj({})
TICKET = obj({"ticketId": ID, "seq": {"type": "integer"}, "sessionId": ID, "kind": {"type": "string"}, "body": ANY,
              "status": {"type": "string", "enum": ["queued", "answered"]}, "answer": ANY,
              "answeredBy": nullable({"type": "string"}), "createdAt": {"type": "string"},
              "answeredAt": nullable({"type": "string"}), "answeredSeq": nullable({"type": "integer"})},
             ("ticketId", "seq", "sessionId", "kind", "body", "status", "answer", "answeredBy", "createdAt",
              "answeredAt", "answeredSeq"))
CARD = obj({"id": ID, "name": {"type": "string"}, "stage": {"type": "string"}}, ("id", "name", "stage"))
PLAN_ITEM = obj({**CARD["properties"], "path": {"type": "string"}, "goal": {"type": "string"}}, ("id", "name", "stage"))
STATES = ["draft", "issued", "claimed", "in_progress", "needs_answer", "delivered", "verified", "closed", "failed",
          "cancelled"]  # kopie ticket_model.STATES (test hlídá shodu), schémata jsou jen data
WORK_BODY_IN = obj({"essence": TEXT, "build": TEXT, "openPaths": TEXTS, "cautions": TEXTS,
                    "skills": {"type": "array", "items": {"type": "string", "pattern": "^/?[A-Za-z0-9][A-Za-z0-9_.:-]*@.+$"}},
                    "doneCriteria": {**TEXTS, "minItems": 1}}, ("essence", "build", "doneCriteria"))
WORK_BODY = {**WORK_BODY_IN, "required": ["essence", "build", "openPaths", "cautions", "skills", "doneCriteria"]}
SLUG = {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{0,39}$"}  # oddělení a profil kanceláře
BRAIN_REF = {"type": "string", "pattern": "^opora:brain:(skill|tool|workflow|subagent|connector):[A-Za-z0-9][A-Za-z0-9_.-]"
                                         "{0,79}(@[0-9a-f]{12})?$"}  # artefakt Brainu (bez verze = aktivní)
PIN = obj({"pin": {"type": "string"}, "plugin": {"type": "string"}, "version": {"type": "string"},
           "zip": {"type": "string"}}, ("pin", "plugin", "version", "zip"))  # jeden plugin = jeden zip
MACHINE = obj({"cardId": nullable(ID), "executionId": nullable(ID), "cardVersion": nullable({"type": "integer"}),
               "department": nullable(SLUG), "profile": nullable(SLUG), "pins": {"type": "array", "items": PIN}},
              ("cardId", "executionId", "cardVersion", "department", "profile", "pins"))
FEEDBACK_KIND = {"type": "string", "enum": ["bug", "idea", "improvement", "question"]}
FEEDBACK_ITEM = obj({"feedbackId": ID, "kind": FEEDBACK_KIND, "text": TEXT, "answer": ANY},
                    ("feedbackId", "kind", "text", "answer"))
WORK_STATUS = obj({"ticketId": ID, "status": {"type": "string", "enum": STATES}}, ("ticketId", "status"))
WORKER_TICKET = obj({**WORK_STATUS["properties"], "body": WORK_BODY, "machine": MACHINE,
                     "feedback": {"type": "array", "items": FEEDBACK_ITEM}},
                    ("ticketId", "status", "body", "machine", "feedback"))
WORK_TICKET = obj({**WORKER_TICKET["properties"], "seq": {"type": "integer"}, "workspaceId": ID,
                   "sessionId": nullable({"type": "string"}), "delivery": ANY, "createdAt": {"type": "string"},
                   "updatedAt": {"type": "string"},
                   "feedback": {"type": "array", "items": obj({**FEEDBACK_ITEM["properties"], "seq": {"type": "integer"},
                                                               "sessionId": {"type": "string"},
                                                               "answeredAt": nullable({"type": "string"}),
                                                               "createdAt": {"type": "string"}})}},
                  ("ticketId", "seq", "workspaceId", "status", "body", "machine", "sessionId", "delivery", "feedback",
                   "createdAt", "updatedAt"))
LATER = {"description":"Odpověď člověka nebo srdce přijde později do schránky (druh inbox), obvykle {text}."}

# Druh → (vstup, výstup, příklad). Příklad je úplné tělo `body` požadavku `{kind, body}`.
SCHEMAS = {
    "ask": (obj({"question": TEXT}, ("question",)), LATER, {"question": "Smím upravit sdílený soubor src/app.ts?"}),
    "change": (obj({"proposal": TEXT, "reason": TEXT}, ("proposal", "reason")), LATER,
               {"proposal": "Rozdělit kartu na dvě stránky.", "reason": "Jedna stránka nevejde do 30 minut."}),
    "state": (EMPTY, obj({"project": obj({"id": ID, "name": {"type": "string"}, "workspace": ID},
                                         ("id", "name", "workspace")),
                          "intent": {"type": "string"}, "rules": TEXTS, "plan": {"type": "array", "items": PLAN_ITEM},
                          "tickets": obj({key: {"type": "integer"} for key in STATES}, STATES),
                          "myTicket": nullable(WORKER_TICKET)},
                         ("project", "intent", "rules", "plan", "tickets", "myTicket")), {}),
    "inbox": (obj({"after": {"type": "integer", "minimum": 0}, "wait": {"type": "integer", "minimum": 0, "maximum": 30}}),
              obj({"tickets": {"type": "array", "items": TICKET}, "last": {"type": "integer"}}, ("tickets", "last")),
              {"after": 0, "wait": 10}),
    "ticket.request": (EMPTY, obj({"ticket": nullable(WORKER_TICKET), "held": {"type": "boolean"}},
                                  ("ticket", "held")), {}),
    "ticket.claim": (obj({"ticketId": ID, "executionId": ID}, ("ticketId",)), obj({"ticket": WORKER_TICKET}, ("ticket",)),
                     {"ticketId": "tk_example"}),
    "ticket.release": (obj({"ticketId": ID}, ("ticketId",)), obj({"ticket": WORK_STATUS}, ("ticket",)),
                       {"ticketId": "tk_example"}),
    "ticket.feedback": (obj({"ticketId": ID, "kind": FEEDBACK_KIND, "text": TEXT}, ("ticketId", "kind", "text")),
                        obj({"feedback": FEEDBACK_ITEM, "ticket": WORK_STATUS}, ("feedback", "ticket")),
                        {"ticketId": "tk_example", "kind": "question", "text": "Smím změnit sdílený styl tlačítka?"}),
    "ticket.deliver": (obj({"ticketId": ID, "summary": TEXT, "sha": {"type": "string", "pattern": "^[0-9a-fA-F]{7,40}$"}},
                           ("ticketId", "summary")), obj({"ticket": WORK_STATUS}, ("ticket",)),
                       {"ticketId": "tk_example", "summary": "Hero je hotový, npm test zelený.", "sha": "abc1234"}),
    "ticket.cancel": (obj({"ticketId": ID}, ("ticketId",)), obj({"ticket": WORK_STATUS}, ("ticket",)),
                      {"ticketId": "tk_example"}),
    "ticket.issue": (obj({"body": WORK_BODY_IN, "cardId": ID, "executionId": ID,
                          "cardVersion": {"type": "integer", "minimum": 0}, "department": nullable(SLUG),
                          "profile": nullable(SLUG), "pins": {"type": "array", "items": BRAIN_REF}, "workspace": ID},
                         ("body",)),
                     obj({"ticket": WORK_TICKET}, ("ticket",)),
                     {"body": {"essence": "Návštěvník musí do pěti vteřin poznat, co produkt dělá.",
                               "build": "Hero sekci úvodní stránky s nadpisem, podnadpisem a jedním tlačítkem.",
                               "openPaths": ["Tlačítko později povede na registraci."],
                               "cautions": ["Neměň sdílenou navigaci."], "skills": ["ponytail@5.3.3"],
                               "doneCriteria": ["npm test projde", "hero je vidět bez posunu"]},
                      "cardId": "hero", "cardVersion": 3, "department": "design", "profile": "frontend"}),
    "ticket.answer": (obj({"ticketId": ID, "text": TEXT, "feedbackId": ID}, ("ticketId", "text")),
                      obj({"ticket": {"description": "Bez feedbackId zodpovězený lístek otázky (TICKET), s ním "
                                                     "{ticketId, status} ticketu práce."},
                           "feedback": FEEDBACK_ITEM}, ("ticket",)),
                      {"ticketId": "gt_example", "text": "Ano, pokračujte."}),
    "escalate": (obj({"text": TEXT}, ("text",)), obj({"ticket": TICKET}, ("ticket",)),
                 {"text": "Požadavek chce třetí stránku, záměr mluví o dvou. Rozhodněte prosím."}),
}
