"""Routy Dílny (docs/navrhy/2026-11-05-dilna-skillu.md §3, §3a). Logika je v `backend/agi_pletor/pletor_opora_settings/`.

Funkce (`tools/`):
- `GET /tools` → `{tools: [{name, path, cases}]}`; `POST /tools` `{name}` → 201 šablona funkce s jedním případem.
- `GET /tools/{name}` → `{name, code, cases}` (syrový text); `PUT /tools/{name}` `{code, cases}` → `{name, cases: počet}`.
- `POST /tools/generate` `{name, intent}` → `{name, code, cases, measure}`: model napíše funkci a případy, Dílna je uloží a změří
  (D5-lite; existující název 409, nepoužitelná odpověď modelu nebo chyba mozku 422; mozek Pletora, tah drží zámek Pletora).
- `POST /tools/{name}/measure` (tělo `{}`) → `{name, passed, total, failed, durationMs, deterministic, error}`.
Skilly (`skills/<name>/`):
- `GET /skills` → `{skills: [{name, description, files}]}`; `POST /skills` `{name}` → 201 `{name, files}`.
- `GET /skills/{name}/file?path=SKILL.md` → `{path, content}`; `PUT /skills/{name}/file` `{path, content}` → `{path, bytes}`.
Chyby: špatný název, cesta nebo obsah 422, neznámé 404, existující 409. Vše pod `/api/pletor/workshop`, jen pro
člověka v UI a jen z tohoto počítače (prefix `/api/pletor` v `backend/app/remote_access.py`).
"""
import json

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from backend.agi_pletor import brains
from backend.agi_pletor.pletor_opora_settings import generate, skills_store, workshop
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.activity_log import require_human

HUMAN = "Dílnu používá jen člověk v UI."


def _fields(body, *keys):
    """Textová pole z těla JSON; nečitelné tělo nebo chybějící či netextové pole je `ValueError` (422)."""
    try:
        payload = json.loads(body or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Tělo není platný JSON.") from None
    if not isinstance(payload, dict) or not all(isinstance(payload.get(key), str) for key in keys):
        raise ValueError(f"Tělo je objekt JSON s textovými poli {', '.join(keys)}.")
    return [payload[key] for key in keys]


def _answer(call, status=200, hint="Seznam: GET /api/pletor/workshop/tools nebo /skills"):
    try:
        return JSONResponse(call(), status_code=status)
    except FileExistsError as error:
        failure = GateError(409, "already_exists", str(error), hint)
    except ValueError as error:
        failure = invalid(str(error), hint)
    except LookupError as error:
        failure = GateError(404, "not_found", str(error), hint)
    return JSONResponse(failure.body(), status_code=failure.status)


def _pletor_ask(pletor):
    """Jeden tah mozku Pletora bez podkladů a bez streamu → text; chyba mozku je `ValueError` (422 s důvodem)."""
    def ask(prompt):
        try:
            with pletor.lock:
                return brains.turn(pletor.folder, "", prompt, runner=pletor.runner, find=pletor.find, transport=pletor.transport)[0]
        except RuntimeError as error:
            raise ValueError(str(error)) from None
    return ask


def create_workshop_router(service, folder=None, skills=None, ask=None):
    folder, skills = folder or workshop.TOOLS, skills or skills_store.SKILLS  # při volání, aby testy mohly podstrčit složku
    router = APIRouter(prefix="/api/pletor/workshop", tags=["pletor"])

    @router.get("/tools")
    def tools(request: Request):
        require_human(request.state.actor, HUMAN)
        return {"tools": workshop.list_tools(folder)}

    @router.post("/tools")
    async def create_tool(request: Request):
        require_human(request.state.actor, HUMAN)
        body = await request.body()
        return _answer(lambda: workshop.create_tool(folder, *_fields(body, "name")), 201)

    @router.post("/tools/generate")
    async def generate_tool(request: Request):
        require_human(request.state.actor, "Funkce v Dílně generuje jen člověk v UI.")
        name, intent = _fields(await request.body(), "name", "intent")

        def work():
            try:
                workshop.read_tool(folder, name)  # špatný název = ValueError, než se zavolá model
            except LookupError:
                pass
            else:
                raise FileExistsError(f"Funkce {name} už existuje.")
            made = generate.generate_tool(ask or _pletor_ask(request.app.state.pletor), name, intent)
            workshop.create_tool(folder, name)
            workshop.save_tool(folder, name, made["code"], json.dumps(made["cases"], ensure_ascii=False, indent=2) + "\n")
            return {"name": name, **made, "measure": workshop.measure(folder, name)}
        return await run_in_threadpool(_answer, work, 201)

    @router.get("/tools/{name}")
    def read_tool(name: str, request: Request):
        require_human(request.state.actor, HUMAN)
        return _answer(lambda: workshop.read_tool(folder, name))

    @router.put("/tools/{name}")
    async def save_tool(name: str, request: Request):
        require_human(request.state.actor, HUMAN)
        body = await request.body()
        return _answer(lambda: workshop.save_tool(folder, name, *_fields(body, "code", "cases")))

    @router.post("/tools/{name}/measure")
    def measure(name: str, request: Request):
        require_human(request.state.actor, "Funkce v Dílně měří jen člověk v UI.")
        return _answer(lambda: workshop.measure(folder, name))

    @router.get("/skills")
    def list_skills(request: Request):
        require_human(request.state.actor, HUMAN)
        return {"skills": skills_store.list_skills(skills)}

    @router.post("/skills")
    async def create_skill(request: Request):
        require_human(request.state.actor, HUMAN)
        body = await request.body()
        return _answer(lambda: skills_store.create_skill(skills, *_fields(body, "name")), 201)

    @router.get("/skills/{name}/file")
    def read_file(name: str, request: Request, path: str = "SKILL.md"):
        require_human(request.state.actor, HUMAN)
        return _answer(lambda: skills_store.read_file(skills, name, path))

    @router.put("/skills/{name}/file")
    async def write_file(name: str, request: Request):
        require_human(request.state.actor, HUMAN)
        body = await request.body()
        return _answer(lambda: skills_store.write_file(skills, name, *_fields(body, "path", "content")))

    return router
