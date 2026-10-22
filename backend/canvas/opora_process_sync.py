"""Read-only process projection over accepted plans, native pipeline and execution facts."""
import time

from backend.canvas.canvas_service import now
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from backend.canvas.opora_process_links import links
from backend.canvas.opora_process_tracking import tracking
from backend.editor.agent_memory.card_pipeline import current_stage, stuck
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from database.repositories.opora_executions import Executions

CARD_LIMIT = 100
LABELS = {"needs-plan": "Doplnit zadání", "needs-acceptance": "Předložit návrh k přijetí",
          "needs-routing": "Sestavit pipeline", "ready": "Převzít kartu", "running": "Sledovat běh",
          "reported": "Zkontrolovat nahlášený výsledek", "stale": "Porovnat s aktuálním zadáním",
          "closed": "Karta uzavřena", "blocked": "Vyřešit blokaci", "unavailable": "Prověřit dostupnost"}


def _latest(repo, node, accepted):
    records = repo.history(node)
    if not records:
        return None
    record = records[0]
    state = record["state"]
    if state not in {"running", "released", "reported", "revoked", "cancelled"}:
        raise ValueError("Unknown persisted execution state.")
    if state == "running":
        lease = repo.db.execute("SELECT token,expires_at FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=?",
                                (*repo.scope, node)).fetchone()
        epoch = repo.db.execute("SELECT epoch FROM opora_execution_epochs WHERE project_id=? AND workspace_id=? AND node_id=?",
                                (*repo.scope, node)).fetchone()
        deadline = record.get("budget", {}).get("runDeadlineAt", record["expiresAt"])
        if (not lease or min(lease["expires_at"], record["expiresAt"], deadline) <= time.time()
                or lease["token"] != record["token"] or not epoch or epoch[0] != record["epoch"]):
            state = "revoked"
    count = repo.db.execute("SELECT COUNT(*) FROM opora_execution_results WHERE project_id=? AND workspace_id=? AND execution_id=?",
                            (*repo.scope, record["executionId"])).fetchone()[0]
    return {"id": record["executionId"], "state": state, "acceptedRevision": record["acceptedRevision"],
            "matchesCurrentRevision": record["acceptedRevision"] == accepted, "results": count}


def _status(document, accepted, matches, stored, execution, availability, read_only, context_valid):
    if stored.get("done", {}).get("confirmed"):
        return "closed", "Dokončení karty je potvrzeno v Canvasu; není to důkaz merge ani nasazení."
    if read_only:
        return "unavailable", "Pracovní prostor je pouze ke čtení."
    if not document or not document["fields"].get("goal", "").strip():
        return "needs-plan", "Karta nemá neprázdný cíl zadání."
    if not accepted or not matches:
        return "needs-acceptance", "Pracovní zadání není shodné s přijatou revizí."
    if execution and not execution["matchesCurrentRevision"]:
        return "stale", "Poslední běh patří jiné přijaté revizi; jeho výsledek zůstává historický."
    if execution and execution["results"]:
        return "reported", "Výsledek je hlášení agenta a vyžaduje samostatnou kontrolu."
    if execution and execution["state"] == "running" and context_valid:
        return "running", "Ledger eviduje běh s platným pronájmem; autoritu znovu ověří heartbeat nebo zápis výsledku."
    if not availability["available"]:
        return "blocked", availability["unavailableReason"] or "Převzetí není dostupné."
    if not stored.get("stages", {}).get("items"):
        return "needs-routing", "Karta zatím nemá sestavenou pipeline práce a kontroly."
    if stuck(stored["stages"]):
        return "blocked", "Pipeline má selhanou etapu bez pokračování; je nutná oprava nebo rozhodnutí člověka."
    if current_stage(stored["stages"]) is None:
        return "blocked", "Pipeline je uzavřena; zkontrolujte důkazy a samostatně potvrďte dokončení karty."
    return "ready", "Přijaté podklady jsou dostupné; claim jejich aktuálnost znovu ověří."


class ProcessSync:
    def __init__(self, canvas):
        self.canvas = canvas

    def read(self, project, workspace, node=None):
        validate({"project": project, "workspace": workspace, **({"nodeId": node} if node is not None else {})},
                 {"nodeId"} if node is not None else set())
        canvas = self.canvas
        with canvas.graph_lock_for(project), canvas.lock_for(project), canvas.steady_reads(project):
            view = canvas.view(project, workspace)
            cards = [item for item in view["graph"]["nodes"] if item["kind"] in {"node", "sector"}]
            selected = [item for item in cards if node is None or item["id"] == node]
            if node is not None and not selected:
                raise ValueError("Card does not exist in this workspace.")
            context = OporaChangesets(canvas).context(project, workspace)
            accepted = context["acceptedHead"]
            live = {item["nodeId"]: item for item in context["documents"]}
            approved = {item["nodeId"]: item for item in context["acceptedDocuments"]}
            state = DesktopV3State(canvas).read(project, workspace)["state"]
            repo = Executions(canvas.db_for(project), project, workspace)
            executions = OporaExecutions(canvas)
            items = []
            for card in selected[:CARD_LIMIT]:
                identifier = card["id"]
                stored = state["nodes"].get(identifier, {})
                execution = _latest(repo, identifier, accepted)
                available = executions.context(project, workspace, identifier)
                availability = {key: available[key] for key in ("available", "unavailableReason")}
                lease = repo.db.execute("SELECT expires_at FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=?",
                                        (*repo.scope, identifier)).fetchone()
                if availability["available"] and lease and lease[0] > time.time():
                    availability = {"available": False, "unavailableReason": "Card already has an active lease."}
                matches = identifier in approved and approved[identifier] == live.get(identifier)
                status, reason = _status(live.get(identifier), accepted, matches, stored, execution, availability,
                                         view["readOnly"], available["acceptedHead"] == accepted and accepted is not None)
                stages = stored.get("stages", {})
                stage = current_stage(stages) if stages.get("items") else None
                items.append({"nodeId": identifier, "name": card["name"], "status": status,
                              "nextAction": {"kind": {"ready": "claim", "reported": "review", "closed": "none", "stale": "reconcile"}.get(status, status),
                                             "label": LABELS[status], "reason": reason},
                              "pipeline": {"stageCount": len(stages.get("items", [])),
                                           "passedCount": sum(item["status"] == "passed" for item in stages.get("items", [])),
                                           "failedCount": sum(item["status"] == "failed" for item in stages.get("items", [])),
                                           "currentStage": stage["title"] if stage else None},
                              "workingMatchesAccepted": matches, "doneConfirmed": bool(stored.get("done", {}).get("confirmed")),
                              "openIdeas": sum(item["status"] == "open" for item in stored.get("ideas", [])),
                              "currentExecution": execution, "executionAvailability": availability,
                              "links": links(project, workspace, identifier, execution["id"] if execution else None)})
            return {"schema": "opora.process-sync/1", "project": project, "workspace": workspace,
                    "acceptedRevision": accepted, "observedAt": now(), "cardLimit": CARD_LIMIT,
                    "totalCards": len(selected), "truncated": len(selected) > CARD_LIMIT, "items": items,
                    "githubTracking": tracking(repo.db, project, workspace, accepted)}
