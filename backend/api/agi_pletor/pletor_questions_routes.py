"""Otázky Pletora srdci (docs/navrhy/2026-11-08-pletor-otazky-srdci.md), prefix `/api/pletor/questions`, `?project=`.

`GET /` (člověk) → `{questions, open}` pro panel; `open` je otevřená otázka nebo null.
`POST /{id}/answer` `{text, refs?, unknown?, reason?}` odpovídá jen agent, tedy srdce tokenem (`opora_heart.py
pletor-answer`); člověk 403 `agent_only`, neznámá 404, uzavřená 409, vadná odpověď 422. Stejná odpověď znovu vrátí
otázku beze změny. Nová odpověď zahodí podklady Pletora a na pozadí spustí jeho výklad (`Pletor.present`).
"""
import threading

from fastapi import APIRouter, Request

from backend.agi_pletor import questions
from backend.api.agi_pletor.linie_work_routes import answer, origin
from backend.api.agi_pletor.models import PletorQuestionAnswerIn
from backend.api.agi_pletor.pletor_routes import _check
from backend.brain_opora.determinism import tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.activity_log import require_human


def create_pletor_questions_router(service, pletor):
    router = APIRouter(prefix="/api/pletor/questions", tags=["pletor"])

    @router.get("")
    def question_list(request: Request, project: str = ""):
        require_human(request.state.actor, "Otázky Pletora čte jen člověk v UI.")

        def act():
            _check(service, project, "main")
            found = questions.listing(service, project)
            return {"questions": found, "open": questions.current(found)}
        return answer(act)

    @router.post("/{question_id}/answer")
    def question_answer(request: Request, question_id: str, body: PletorQuestionAnswerIn, project: str = ""):
        def act():
            by = origin(service, request, project)
            if not by.startswith("agent:"):
                raise GateError(403, "agent_only", "Na otázku Pletora odpovídá jen srdce.",
                                "python opora_heart.py pletor-answer --question pq_… --text T")
            question, changed = questions.answer(service, project, question_id, body.text, body.refs, body.unknown,
                                                 body.reason, by, tokens.stamp())
            if changed:
                # OP-FB0522.2: odpověď srdce zneplatní podklady a Pletor ji sám vyloží člověku
                pletor.contexts.clear()
                threading.Thread(target=pletor.present, args=(project, question["workspace"], question),
                                 daemon=True).start()
            return {**question, "changed": changed}
        return answer(act)

    return router
