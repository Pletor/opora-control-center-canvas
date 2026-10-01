"""Rozhraní Editoru: echo a verdikt Oracle nad jedním projektem a zápis běhu kontrol.

`GET /api/sync-report` jen čte. `POST /api/check-run` zapisuje hotový výsledek kontrol
k jednomu commitu — aplikace testy nespouští, jen bere jejich výsledek na vědomí.
"""

from fastapi import APIRouter, Query


def create_sync_router(report, check_runs=None):
    """`check_runs` je vlastník tabulky běhů; bez něj se vezme ten, který drží report."""
    runs = check_runs if check_runs is not None else report.check_runs
    router = APIRouter(prefix="/api", tags=["sync"])

    @router.get("/sync-report")
    def sync_report(
        project: str = Query(min_length=1, max_length=64),
        workspace: str = Query(default="draft", min_length=1, max_length=64),
    ):
        return report.report(project, workspace)

    @router.post("/check-run")
    def record_check_run(payload: dict):
        scope = (payload.get("project"), payload.get("workspace") or "draft", payload.get("scope"))
        return runs.record(scope, payload)

    @router.get("/check-run")
    def read_check_run(
        project: str = Query(min_length=1, max_length=64),
        workspace: str = Query(default="draft", min_length=1, max_length=64),
        scope: str = Query(min_length=1, max_length=80),
    ):
        return runs.latest((project, workspace, scope)) or {"status": None}

    return router
