"""API registru Brainu (`backend/brain/registry.py`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4).

Tenký router: data leží v registry.sqlite, každé volání drží `registry_lock`. Čtení je volné. Kandidáta, eval,
aktivaci a návrat zapisuje člověk (doklad UI) nebo srdce (`X-Opora-Gate-Token` srdce); aktivace bez prošlého evalu
(`force`) jen člověk. Eval gate: `backend/brain/evaluate.py`. Zip pinu (`Store.export`) čte dělník téhož stroje;
přes veřejný tunel ho hranice v `backend/app/factory.py` pustí jen s přístupovým tokenem.
"""

import re
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from backend.brain import evaluate, registry
from backend.brain.store import NAME, Store
from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError

SHORT = re.compile(r"[0-9a-f]{12}")


def _thread(target):
    threading.Thread(target=target, name="opora-brain-eval", daemon=True).start()


def _refused(status, code, message):
    return JSONResponse({"error": message, "code": code}, status_code=status)


def create_brain_registry_router(service, spawn=_thread):
    router = APIRouter(prefix="/api/brain-registry", tags=["brain-registry"])

    @router.get("/artifacts")
    def artifact_list():
        with service.registry_lock:
            return {"artifacts": registry.list_artifacts(service.db)}

    @router.get("/artifacts/{artifact_id}")
    def artifact_detail(artifact_id: str):
        with service.registry_lock:
            artifact = registry.get_artifact(service.db, artifact_id)
        if artifact is None:
            raise HTTPException(404, "Artefakt Brainu neexistuje.")
        return artifact

    @router.get("/pins/{plugin}@{sha12}.zip")
    def pin_zip(plugin: str, sha12: str):
        sha = None
        if NAME.fullmatch(plugin) and SHORT.fullmatch(sha12):
            with service.registry_lock:
                sha = registry.plugin_version(service.db, plugin, sha12)
        if sha is None:
            raise HTTPException(404, "Verze pluginu v registru Brainu není.")
        return FileResponse(Store(service.root).export(plugin, sha), media_type="application/zip",
                            filename=f"{plugin}@{sha12}.zip")

    def writer(request):
        """`human` (doklad UI) nebo `heart` (token srdce); jinak GateError 401/403."""
        if getattr(request.state, "actor", None) == "human":
            return "human"
        gate.authenticate(service, request.headers.get(tokens.HEADER), None, ("heart",))
        return "heart"

    async def body(request):
        try:
            value = await request.json()
        except ValueError:
            value = None
        return value if isinstance(value, dict) else {}

    @router.post("/artifacts/{artifact_id}/candidates", status_code=201)
    async def candidate_create(artifact_id: str, request: Request):
        try:
            writer(request)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        payload = await body(request)
        try:
            with service.registry_lock:
                return evaluate.add_candidate(service.db, service.root, artifact_id, payload.get("files"),
                                              str(payload.get("message") or ""))
        except evaluate.Refused as error:
            return _refused(error.status, error.code, error.message)

    @router.post("/versions/{version_id}/evaluate", status_code=202)
    def version_evaluate(version_id: str, request: Request):
        try:
            writer(request)
            with service.registry_lock:
                run = evaluate.start(service.db, version_id)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        except evaluate.Refused as error:
            return _refused(error.status, error.code, error.message)
        spawn(lambda: evaluate.execute(service, run["id"]))
        return run

    @router.get("/eval-runs/{run_id}")
    def eval_run_detail(run_id: str):
        with service.registry_lock:
            run = evaluate.get_run(service.db, run_id)
        if run is None:
            raise HTTPException(404, "Běh evalu neexistuje.")
        return run

    @router.post("/versions/{version_id}/activate")
    async def version_activate(version_id: str, request: Request):
        try:
            role = writer(request)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        forced = (await body(request)).get("force") is True
        if forced and role != "human":
            return _refused(403, "human_required", "Aktivaci bez evalu (force) potvrzuje jen člověk v UI.")
        with service.registry_lock:
            version = registry.version(service.db, version_id)
            if version is None:
                return _refused(404, "version_not_found", "Verze artefaktu neexistuje.")
            if forced:
                evaluate.force(service.db, version_id)
            elif not evaluate.passed(evaluate.latest(service.db, version_id)):
                return _refused(409, "eval_required", "Aktivace potřebuje prošlý eval (skóre ≥ baseline).")
            registry.activate(service.db, version_id)
            return registry.version(service.db, version_id)

    @router.post("/artifacts/{artifact_id}/rollback")
    def artifact_rollback(artifact_id: str, request: Request):
        try:
            writer(request)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        with service.registry_lock:
            try:
                return registry.version(service.db, registry.rollback(service.db, artifact_id))
            except LookupError as error:
                return _refused(409, "no_previous_version", str(error))

    return router
