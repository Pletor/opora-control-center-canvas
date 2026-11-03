"""Schémata JSON druhů brány (docs/brain-control-api.md §2): vstup a výstup každého druhu a jeden úplný příklad.

Jen data pro tabulku `kinds.py`: z nich vzniká `GET /api/gate/kinds` (a později nástroje MCP). Kontroly samotné
jsou funkce v `gate_payloads.py` a `task_payloads.py`; test `test_kinds.py` hlídá, že příklady projdou kontrolou
i schématem a že výstup obsluhy schématu odpovídá.
"""
from backend.brain_opora.determinism.task_payloads import MODELS

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
TASK_BODY_IN = obj({"why": {"type": "string"}, "do": TEXT, "files": TEXTS, "doneWhen": TEXTS,
                    "dontTouch": {"type": "array", "items": obj({"path": TEXT, "heldBy": TEXT}, ("path", "heldBy"))},
                    "context": obj({"intent": {"type": "string"}, "rules": TEXTS, "pattern": {"type": "string"}}),
                    "commit": {"type": "string"}, "model": {"type": "string", "enum": list(MODELS)}}, ("do",))
TASK_BODY = {**TASK_BODY_IN, "required": ["why", "do", "files", "doneWhen", "dontTouch", "context", "commit", "model"]}
WORKER_TASK = obj({"id": ID, "title": TEXT, "nodeId": nullable(ID), "status": {"type": "string"},
                   "attempts": {"type": "integer"}, "body": TASK_BODY},
                  ("id", "title", "nodeId", "status", "attempts", "body"))
TASK = obj({"taskId": ID, "seq": {"type": "integer"}, "workspaceId": ID, "nodeId": nullable(ID), "title": TEXT,
            "body": TASK_BODY, "status": {"type": "string", "enum": ["ready", "assigned", "done", "failed", "cancelled"]},
            "sessionId": nullable({"type": "string"}), "attempts": {"type": "integer"}, "createdBy": {"type": "string"},
            "report": ANY, "createdAt": {"type": "string"}, "updatedAt": {"type": "string"}, "order": {"type": "integer"}},
           ("taskId", "seq", "workspaceId", "nodeId", "title", "body", "status", "sessionId", "attempts", "createdBy",
            "report", "createdAt", "updatedAt", "order"))
TICKET = obj({"ticketId": ID, "seq": {"type": "integer"}, "sessionId": ID, "kind": {"type": "string"}, "body": ANY,
              "status": {"type": "string", "enum": ["queued", "answered"]}, "answer": ANY,
              "answeredBy": nullable({"type": "string"}), "createdAt": {"type": "string"},
              "answeredAt": nullable({"type": "string"}), "answeredSeq": nullable({"type": "integer"})},
             ("ticketId", "seq", "sessionId", "kind", "body", "status", "answer", "answeredBy", "createdAt",
              "answeredAt", "answeredSeq"))
CARD = obj({"id": ID, "name": {"type": "string"}, "stage": {"type": "string"}}, ("id", "name", "stage"))
PLAN_ITEM = obj({**CARD["properties"], "path": {"type": "string"}, "goal": {"type": "string"}}, ("id", "name", "stage"))
CHECK = obj({"name": TEXT, "status": {"type": "string", "enum": ["green", "red"]}, "output": {"type": "string"}},
            ("name", "status"))
STATES = ["draft", "issued", "claimed", "in_progress", "needs_answer", "delivered", "verified", "closed", "failed",
          "cancelled"]  # kopie ticket_model.STATES (test hlídá shodu), schémata jsou jen data
WORK_BODY_IN = obj({"essence": TEXT, "build": TEXT, "openPaths": TEXTS, "cautions": TEXTS,
                    "skills": {"type": "array", "items": {"type": "string", "pattern": "^/?[A-Za-z0-9][A-Za-z0-9_.:-]*@.+$"}},
                    "doneCriteria": {**TEXTS, "minItems": 1}}, ("essence", "build", "doneCriteria"))
WORK_BODY = {**WORK_BODY_IN, "required": ["essence", "build", "openPaths", "cautions", "skills", "doneCriteria"]}
MACHINE = obj({"cardId": nullable(ID), "executionId": nullable(ID), "cardVersion": nullable({"type": "integer"})},
              ("cardId", "executionId", "cardVersion"))
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
    "next": (EMPTY, obj({"task": nullable(WORKER_TASK), "plan": {"type": "array", "items": CARD}}, ("task",)), {}),
    "report": (obj({"taskId": ID, "sha": {"type": "string", "pattern": "^[0-9a-fA-F]{7,40}$"},
                    "summary": {"type": "string"}, "checks": {"type": "array", "items": CHECK, "minItems": 1}},
                   ("taskId", "sha", "summary", "checks")),
               obj({"task": obj({"id": ID, "status": {"type": "string"}, "attempts": {"type": "integer"}},
                                ("id", "status", "attempts"))}, ("task",)),
               {"taskId": "ht_example", "sha": "abc1234", "summary": "Test modulu X doplněn.",
                "checks": [{"name": "npm test", "status": "green"}]}),
    "release": (obj({"taskId": ID, "reason": {**TEXT, "maxLength": 400}}, ("taskId", "reason")),
                obj({"task": obj({"id": ID, "status": {"type": "string"}, "attempts": {"type": "integer"}},
                                 ("id", "status", "attempts"))}, ("task",)),
                {"taskId": "ht_example", "reason": "Úkol potřebuje změnu souboru z dontTouch."}),
    "ask": (obj({"question": TEXT, "taskId": ID}, ("question",)), LATER,
            {"question": "Smím upravit sdílený soubor src/app.ts?", "taskId": "ht_example"}),
    "change": (obj({"proposal": TEXT, "reason": TEXT, "taskId": ID}, ("proposal", "reason")), LATER,
               {"proposal": "Rozdělit úkol na dvě stránky.", "reason": "Jedna stránka nevejde do 30 minut.",
                "taskId": "ht_example"}),
    "state": (EMPTY, obj({"project": obj({"id": ID, "name": {"type": "string"}, "workspace": ID},
                                         ("id", "name", "workspace")),
                          "intent": {"type": "string"}, "rules": TEXTS, "plan": {"type": "array", "items": PLAN_ITEM},
                          "queue": obj({key: {"type": "integer"} for key in ("ready", "assigned", "done", "failed")},
                                       ("ready", "assigned", "done", "failed")),
                          "myTask": nullable(WORKER_TASK)},
                         ("project", "intent", "rules", "plan", "queue", "myTask")), {}),
    "inbox": (obj({"after": {"type": "integer", "minimum": 0}, "wait": {"type": "integer", "minimum": 0, "maximum": 30}}),
              obj({"tickets": {"type": "array", "items": TICKET}, "last": {"type": "integer"}}, ("tickets", "last")),
              {"after": 0, "wait": 10}),
    "task.create": (obj({"title": TEXT, "body": TASK_BODY_IN, "nodeId": ID,
                         "order": {"type": "integer", "minimum": 0, "maximum": 1_000_000}}, ("title", "body")),
                    obj({"task": TASK}, ("task",)),
                    {"title": "Test modulu X", "order": 1,
                     "body": {"why": "Modul X nemá test.", "do": "Doplňte test pro modul X.", "files": ["src/x.test.ts"],
                              "doneWhen": ["npm test je zelený"], "context": {"rules": ["Komentáře česky."]}}}),
    "task.cancel": (obj({"taskId": ID}, ("taskId",)), obj({"task": TASK}, ("task",)), {"taskId": "ht_example"}),
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
    "ticket.issue": (obj({"body": WORK_BODY_IN, "cardId": ID, "executionId": ID,
                          "cardVersion": {"type": "integer", "minimum": 0}}, ("body",)),
                     obj({"ticket": WORK_TICKET}, ("ticket",)),
                     {"body": {"essence": "Návštěvník musí do pěti vteřin poznat, co produkt dělá.",
                               "build": "Hero sekci úvodní stránky s nadpisem, podnadpisem a jedním tlačítkem.",
                               "openPaths": ["Tlačítko později povede na registraci."],
                               "cautions": ["Neměň sdílenou navigaci."], "skills": ["ponytail@5.3.3"],
                               "doneCriteria": ["npm test projde", "hero je vidět bez posunu"]},
                      "cardId": "hero", "cardVersion": 3}),
    "ticket.answer": (obj({"ticketId": ID, "text": TEXT, "feedbackId": ID}, ("ticketId", "text")),
                      obj({"ticket": {"description": "Bez feedbackId zodpovězený lístek otázky (TICKET), s ním "
                                                     "{ticketId, status} ticketu práce."},
                           "feedback": FEEDBACK_ITEM}, ("ticket",)),
                      {"ticketId": "gt_example", "text": "Ano, pokračujte."}),
    "escalate": (obj({"text": TEXT}, ("text",)), obj({"ticket": TICKET}, ("ticket",)),
                 {"text": "Požadavek chce třetí stránku, záměr mluví o dvou. Rozhodněte prosím."}),
}
