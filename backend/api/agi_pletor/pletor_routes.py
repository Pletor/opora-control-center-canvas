"""Routy Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md, P1). Logika je v `backend/agi_pletor/`.

- `POST /api/pletor/messages {project, workspace, text, voice?}` → `{reply, actions: [{type, text, ok, detail?}]}`.
- `POST /api/pletor/messages/stream` (stejné tělo a kontroly) → `application/x-ndjson`: `{"type": "delta", "text"}`
  nula a víckrát (složené = `reply`), nakonec vždy `{"type": "done", reply, actions}`.
- `GET /api/pletor/state?project&workspace` → `{messages, heart, escalations, brain: {brain, model, available}}`.
- `POST /api/pletor/brain {brain: claude | ollama, model?}` → `{ok, reply, brain}` (P2; selhání = `ok: false`).
- `GET /api/pletor/voices?warm=<id>` → `{voices: [{id, label, gender, engine, available, reason, quota}]}`: XTTS,
  ElevenLabs, Edge, Piper v pořadí výchozí volby; `quota` `{tier, character_count, character_limit}` jen u ElevenLabs;
  `warm` (jinak nejlepší dostupný) se načte dopředu.
- `GET /api/pletor/llm` → `{claude, codex, ollama, cswap}` jen ke čtení (docs/navrhy/2026-11-04-pletor-nastaveni-llm.md,
  M1); každá sekce selže zvlášť jako `{available: false, reason}`, cesty od klienta se nepřijímají.
- `POST /api/pletor/tts {text, voice?}` → zvuk podle enginu v id hlasu: `audio/wav` (Piper), `audio/mpeg` (Edge,
  ElevenLabs, cloud), `audio/pcm;rate=24000` (XTTS), streamovaně; nestažený hlas 404, nedostupný engine 503.
Všechny jen pro člověka v UI a jen z tohoto počítače (`/api/pletor` v `backend/app/remote_access.py`).
"""
import json
import queue
import threading

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from backend.api.agi_pletor import models
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.activity_log import require_human
from backend.canvas.graph import valid_id
from backend.agi_pletor import brains, llm_settings, speech, tts


def _check(service, project, workspace):
    if not (project == "draft" or valid_id(project)) or not valid_id(workspace):
        raise invalid("Neplatné ID projektu nebo pracovního prostoru.", "Přidejte project=<id>&workspace=<id>.")
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")


def create_pletor_router(service, pletor):
    router = APIRouter(prefix="/api/pletor", tags=["pletor"])

    def refused(body, request):
        require_human(request.state.actor, "S Pletorem mluví jen člověk v UI.")
        try:
            _check(service, body.project, body.workspace)
            if not body.text.strip() or "\0" in body.text:
                raise invalid("text je neprázdný text.", 'Příklad: {"project": "<id>", "workspace": "main", "text": "…"}')
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        return None

    @router.post("/messages", response_model=models.PletorReplyOut)
    async def message(body: models.PletorMessageIn, request: Request):
        if answer := refused(body, request):
            return answer
        return await run_in_threadpool(pletor.message, body.project, body.workspace, body.text.strip(),
                                     body.voice)

    @router.post("/messages/stream")
    def message_stream(body: models.PletorMessageIn, request: Request):
        if answer := refused(body, request):
            return answer
        chunks = queue.Queue()  # tah ve vlákně → řádky odpovědi; odpojený klient tah nezastaví, zpráva se uloží

        def work():
            try:
                done = pletor.message(body.project, body.workspace, body.text.strip(), body.voice,
                                      on_delta=lambda text: chunks.put({"type": "delta", "text": text}))
            except Exception as error:  # noqa: BLE001 – proud musí vždy skončit řádkem done
                done = {"reply": f"Pletor selhal: {error}", "actions": []}
            chunks.put({"type": "done", **done})

        threading.Thread(target=work, daemon=True).start()

        def lines():
            while True:
                item = chunks.get()
                yield json.dumps(item, ensure_ascii=False) + "\n"
                if item["type"] == "done":
                    return

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @router.get("/state", response_model=models.PletorStateOut)
    def state(request: Request, project: str = "", workspace: str = ""):
        require_human(request.state.actor, "Rozhovor s Pletorem čte jen člověk v UI.")
        try:
            _check(service, project, workspace)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        return {**pletor.state(project, workspace), "brain": brains.status(pletor.folder, pletor.transport)}

    @router.post("/brain", response_model=models.PletorBrainOut)
    def brain(body: models.PletorBrainIn, request: Request):
        require_human(request.state.actor, "Mozek Pletora přepíná jen člověk v UI.")
        ok, reply = brains.switch(pletor.folder, body.brain, body.model, pletor.transport)
        return {"ok": ok, "reply": reply, "brain": brains.status(pletor.folder, pletor.transport)}

    @router.get("/voices", response_model=models.PletorVoicesOut)
    def voices(request: Request, warm: str = ""):
        require_human(request.state.actor, "Hlasy Pletora čte jen člověk v UI.")
        found = speech.voices(pletor.folder)
        # Okno se ptá při otevření: zvolený hlas se načte dřív, než přijde první odpověď (XTTS ~20 s do GPU).
        target = warm or speech.default(found)
        if any(voice["id"] == target and voice["available"] for voice in found):
            threading.Thread(target=speech.warm, args=(pletor.folder, target), daemon=True).start()
        return {"voices": found}

    @router.get("/llm", response_model=models.PletorLlmOut)
    def llm(request: Request):
        require_human(request.state.actor, "Nastavení LLM na tomto počítači čte jen člověk v UI.")
        return llm_settings.read_all()

    @router.post("/tts")
    async def say(body: models.PletorSpeechIn, request: Request):
        require_human(request.state.actor, "Hlas Pletora pouští jen člověk v UI.")
        text = body.text.strip()
        try:
            if not text or "\0" in text:
                raise invalid("text je neprázdný text.", 'Příklad: {"text": "Dobrý den."}')
            try:
                media, audio = await speech.speak(pletor.folder, text, body.voice or tts.DEFAULT)
            except tts.VoiceMissing as error:
                raise GateError(404, "voice_missing", "Hlas není stažen.", str(error)) from error
            except tts.EngineMissing as error:
                raise GateError(503, "tts_missing", str(error), "Okno samo zkusí další engine.") from error
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        if isinstance(audio, bytes):
            return Response(audio, media_type=media)
        return StreamingResponse(audio, media_type=media)

    return router
