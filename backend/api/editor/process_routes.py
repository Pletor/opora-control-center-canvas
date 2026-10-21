"""Rozhraní Editoru: procesy uzlu (návrh → proces → hotovo → oprava) a odpovědi agentů."""

from fastapi import APIRouter, Query, Request

from backend.canvas.opora_execution_process_guard import process_mutation_guard
from backend.canvas.project_folder import ProjectFolder
from backend.editor.process.process_lifecycle import allowed_targets, mark_step, set_fix, transition
from backend.editor.process.process_reports import ProcessReports
from backend.editor.process.process_store import ProcessStore


def create_process_router(service):
    router = APIRouter(prefix="/api/processes", tags=["processes"])
    guard = process_mutation_guard(service)

    def store(project: str) -> ProcessStore:
        return ProcessStore(ProjectFolder(service.root, project).path)

    def find(process_id: str, project: str):
        return store(project), store(project).get(process_id)

    def actor(payload: dict) -> dict:
        by = payload.get("by")
        if not isinstance(by, dict):
            raise ValueError("Chybí aktér (by).")  # noqa: TRY004 — API mapuje ValueError na 409
        return {"kind": by.get("kind"), "name": by.get("name")}

    @router.get("")
    def list_processes(project: str = Query(min_length=1, max_length=64), state: str | None = None, nodeId: str | None = None):
        items = store(project).list(state)
        if nodeId:
            items = [item for item in items if item.get("nodeId") == nodeId]
        return {"processes": [{**item, "allowed": {kind: allowed_targets(item, kind) for kind in ("human", "agent", "system")}} for item in items]}

    @router.post("")
    @guard
    def create_process(payload: dict, request: Request):
        project = payload.get("project")
        if not isinstance(project, str) or not project:
            raise ValueError("Chybí project.")
        by = actor(payload)
        process = store(project).create(
            str(payload.get("title", "")),
            payload.get("owner") or by,
            by=by,
            node_id=payload.get("nodeId"),
            sector_id=payload.get("sectorId"),
            steps=[str(step) for step in payload.get("steps", [])],
            inputs=payload.get("inputs"),
            project_id=project,
        )
        return {"process": process}

    @router.get("/{process_id}")
    def read_process(process_id: str, project: str = Query(min_length=1, max_length=64)):
        current, process = find(process_id, project)
        reports = ProcessReports(current).list(process_id)
        return {"process": process, "reports": reports[-20:], "allowed": {kind: allowed_targets(process, kind) for kind in ("human", "agent", "system")}}

    @router.post("/{process_id}/transition")
    @guard
    def transition_process(process_id: str, payload: dict, request: Request):
        current, process = find(process_id, payload.get("project", ""))
        if payload.get("revision") != process["revision"]:
            raise ValueError("Proces se mezitím změnil; načtěte ho znovu.")
        updated = process
        if payload.get("fix"):
            updated = set_fix(updated, str(payload["fix"]))
        updated = transition(updated, str(payload.get("to")), by=actor(payload), note=str(payload.get("note", "")), failure=payload.get("failure"))
        return {"process": current.save(updated, expected_revision=process["revision"])}

    @router.post("/{process_id}/steps/{step_id}")
    @guard
    def update_step(process_id: str, step_id: str, payload: dict, request: Request):
        current, process = find(process_id, payload.get("project", ""))
        if payload.get("revision") != process["revision"]:
            raise ValueError("Proces se mezitím změnil; načtěte ho znovu.")
        updated = mark_step(process, step_id, str(payload.get("state")), payload.get("evidence"))
        return {"process": current.save(updated, expected_revision=process["revision"])}

    @router.post("/{process_id}/reports")
    @guard
    def submit_report(process_id: str, payload: dict, request: Request):
        current, _ = find(process_id, payload.get("project", ""))
        return ProcessReports(current).submit(process_id, payload)

    return router
