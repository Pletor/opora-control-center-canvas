"""Vstup logu pláten 2–4 (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §6): událost jde do `flow_log_events`.

Plátna 2–4 nemají běhy, událost je jen v logu (`run_id` NULL) a nese `project`. Chyba plátna (`kind` končí
`.failed`, třeba `intent.failed`) navíc zapíše do outboxu projektu událost `canvas.failed`, kterou srdce čte jako
ostatní chyby (`catalogs/heart/inputs.wake_input` → vstup `canvasFailed`), takže ho probudí s oknem 20 s.
"""

import json

from backend.canvas.opora_events import emit_event
from backend.flow.graph_check import FlowInvalid
from backend.flow.run_log import append
from backend.flow.workflows import FlowNotFound
from backend.project.architecture.work_status import accepted_workspace

CANVASES = (2, 3, 4)
PAYLOAD_LIMIT = 4000  # znaků JSON payloadu


def log_canvas(service, project, canvas, kind, payload, author):
    """Zapíše událost plátna; vrací `{seq, canvas, kind}`. Neznámý projekt `FlowNotFound`, špatný vstup `FlowInvalid`."""
    if canvas not in CANVASES:
        raise FlowInvalid("Log pláten přijímá jen plátna 2–4.")
    if not isinstance(payload, dict) or len(json.dumps(payload, ensure_ascii=False)) > PAYLOAD_LIMIT:
        raise FlowInvalid(f"payload musí být objekt do {PAYLOAD_LIMIT} znaků JSON.")
    with service.registry_lock:
        db = service.db
        if not db.execute("SELECT 1 FROM projects WHERE id=?", (project,)).fetchone():
            raise FlowNotFound("Projekt neexistuje.")
        with db:
            seq = append(db, None, None, kind, {**payload, "project": project, "author": author}, canvas=canvas)
    if kind.endswith(".failed"):
        with service.lock_for(project):
            pdb = service.db_for(project)
            with pdb:
                emit_event(pdb, project_id=project, workspace_id=accepted_workspace(service, project),
                           kind="canvas.failed", actor=author,
                           data={"seq": seq, "canvas": canvas, "kind": kind, "payload": payload})
    return {"seq": seq, "canvas": canvas, "kind": kind}
