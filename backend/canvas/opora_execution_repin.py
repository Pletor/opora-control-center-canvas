"""Re-pin kontextu karty po vlastní dávce plánu (docs/navrhy/2026-10-28-zefektivneni-opory.md §3.3).

Agent drží kartu (běh v2 s živým převzetím) a dávkou `canvas-plan` změní rozsah jejího kontextu
(přidá podkartu, stránku do aplikace…, `specification_scope.select_scope`). Bez re-pinu by další zápis
běhu skončil 409 „SQL context live scope changed during replay“. Server proto po dávce téhož aktéra
přepne kontext jeho živých běhů na novou hlavu: nový snímek SQL řádků, nový `contextVersion`, nová
`specification` v zadání a nový otisk zadání. Přijatá revize, dokumenty, kroky ani rozpočet se nemění.

Přepne se jen běh, jehož kontext byl platný před dávkou (cizí změna mezitím = dál 409 s nápovědou
„spusť start znovu“, `OporaExecutions.active`), a jen když přijatý rozsah a vazba zdroje zůstaly.
Schéma tabulek se nemění: původní pin je neměnný (trigger), re-pin vloží nový neměnný pin s klíčem
`<executionId>:repin<n>` do téže tabulky a záznam běhu (JSON) na něj ukáže polem `contextPinId`.
"""
import json

from backend.canvas.graph import digest
from backend.canvas.opora_execution_context import pin_id, token
from backend.canvas.opora_execution_context_validation import validate_context
from backend.canvas.opora_execution_lineage import validate_accepted_lineage
from backend.canvas.opora_executions import OporaExecutions
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from backend.editor.agent_packet.specification_sql_context import project_sql_context
from backend.library.harness_kit import kit_of_assignment
from database.repositories import opora_context_bindings as bindings
from database.repositories import opora_execution_contexts as private
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_context_snapshot import capture


def owned_running(canvas, project, workspace, owner):
    """ID běžících běhů v2 tohoto vlastníka (levné čtení bez zámku; platnost se ověří pod zámkem)."""
    rows = canvas.db_for(project).execute(
        "SELECT id, record FROM opora_executions WHERE project_id=? AND workspace_id=? AND owner=?",
        (project, workspace, owner)).fetchall()
    found = []
    for identifier, raw in rows:
        record = json.loads(raw)
        if record.get("state") == "running" and record.get("contextProtocolVersion") == 2:
            found.append(identifier)
    return found


def valid(executions, project, workspace, identifier):
    """Běh je živý a jeho kontext sedí na aktuální stav (vlastní transakce)."""
    try:
        with executions.transaction(project, workspace) as repo:
            record = repo.read(identifier)
            if record["state"] != "running":
                return False
            executions.lease_valid(repo, record)
            validate_context(executions.canvas, repo, record)
            return True
    except ValueError:
        return False


def repin(executions, project, workspace, identifier, *, on_success=None):
    """Přepne kontext běhu na aktuální stav; vrací True, když se přepnul, False když nesmí."""
    canvas = executions.canvas
    try:
        with executions.transaction(project, workspace) as repo, canvas.registry_lock:
            record = repo.read(identifier)
            executions.lease_valid(repo, record)
            pin = private.read(repo.db, project, workspace, pin_id(record))
            binding = bindings.checkpoint(canvas.db, project, workspace)
            if binding != pin["binding"] or pin["assignmentDigest"] != record["assignmentDigest"]:
                return False
            node = record["nodeId"]
            # Přijatý rozsah karty se od převzetí nezměnil (jinak nový start, ne re-pin).
            validate_accepted_lineage(repo.db, project, workspace, node, pin["acceptedRevision"],
                                      ChangesetRepository(repo.db, project, workspace).head())
            snapshot = capture(repo.db, project)
            projection = project_sql_context(snapshot["rows"], project, workspace, node, metadata=pin["metadata"])
            from backend.editor.research.execution_evidence import validate_assignment
            validate_assignment(repo.db, project, workspace, record)
            # Re-pin SQL context, never refresh the assignment's research authority.
            authenticated = dict(projection)
            if "researchEvidence" in record["assignment"]:
                authenticated["researchEvidence"] = record["assignment"]["researchEvidence"]
            opaque = token(private.key(repo.db, project), authenticated, pin["acceptedRevision"], binding)
            assignment = {**record["assignment"], "contextVersion": opaque,
                          "specification": {**redact_deep(projection), "schema": "opora.specification-context/2"}}
            kit_of_assignment(assignment, node)
            count = record.get("contextRepins", 0) + 1
            # Pin je neměnný (trigger schématu): re-pin přidá nový pin pod vlastním klíčem, původní zůstává.
            fresh = f"{identifier}:repin{count}"
            private.insert(repo.db, project, workspace, fresh,
                           {**pin, "snapshot": snapshot, "contextVersion": opaque, "assignmentDigest": digest(assignment)})
            record.update(assignment=assignment, assignmentDigest=digest(assignment), contextRepins=count,
                          contextPinId=fresh)
            repo.save(record)
            validate_context(canvas, repo, record)  # nový pin musí projít stejnou kontrolou jako každý zápis
            if on_success is not None:
                on_success(repo.db)
            return True
    except ValueError:
        return False


def _fence(record):
    return {"assignmentDigest": record["assignmentDigest"], "pinId": pin_id(record),
            "epoch": record["epoch"], "token": record["token"]}


def freeze_candidates(canvas, project, workspace, owner):
    if owner is None:
        return []
    executions = OporaExecutions(canvas)
    frozen = []
    for identifier in owned_running(canvas, project, workspace, owner):
        if valid(executions, project, workspace, identifier):
            with executions.transaction(project, workspace) as repo:
                record = repo.read(identifier)
                executions.lease_valid(repo, record)
                validate_context(canvas, repo, record)
                frozen.append({"id": identifier, "fence": _fence(record), "outcome": None})
    return frozen


def finish_candidates(canvas, project, workspace, receipt, intent):
    from backend.canvas.canvas_plan_recovery import blocked
    executions = OporaExecutions(canvas)
    for candidate in intent["repins"]:
        if candidate["outcome"] is not None:
            continue  # outcome and re-pin were committed in the same native SQL transaction
        identifier = candidate["id"]
        with executions.transaction(project, workspace) as repo:
            record = repo.read(identifier)
            owner = repo.db.execute('SELECT owner FROM opora_executions WHERE id=? AND project_id=? AND workspace_id=?',
                                   (identifier, project, workspace)).fetchone()[0]
            if owner != intent["repinOwner"] or _fence(record) != candidate["fence"]:
                blocked("Original execution authority changed before operation re-pin.")
            try:
                executions.lease_valid(repo, record)
            except ValueError:
                blocked("Original execution lease is no longer authoritative for re-pin.")
        if valid(executions, project, workspace, identifier):
            with canvas.lock_for(project), canvas.db_for(project) as db:
                candidate["outcome"] = "unchanged"
                receipt.progress(db, intent)
            continue

        def persist(db):
            candidate["outcome"] = "repinned"
            receipt.progress(db, intent)

        if not repin(executions, project, workspace, identifier, on_success=persist):
            blocked("Original execution evidence cannot be safely re-pinned.")
    return [item["id"] for item in intent["repins"] if item["outcome"] == "repinned"]


def plan_with_repin(canvas, payload, owner, apply):
    """`apply()` = dávka plánu; vrací její odpověď a `rePinned` u aktéra, který drží živé běhy v2."""
    project = payload.get("project") if isinstance(payload, dict) else None
    workspace = payload.get("workspace") if isinstance(payload, dict) else None
    try:
        candidates = owned_running(canvas, project, workspace, owner) if payload.get("dryRun") is not True else []
    except (ValueError, TypeError, LookupError):
        candidates = []
    if not candidates:
        return apply()
    executions = OporaExecutions(canvas)
    with canvas.graph_lock_for(project):  # nikdo jiný mezi kontrolou, dávkou a re-pinem graf nezmění
        clean = [item for item in candidates if valid(executions, project, workspace, item)]
        result = apply()
        moved = [item for item in clean
                 if not valid(executions, project, workspace, item) and repin(executions, project, workspace, item)]
    return {**result, "rePinned": moved} if isinstance(result, dict) else result
