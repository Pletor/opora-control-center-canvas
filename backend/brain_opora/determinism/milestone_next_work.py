"""Read-only next steps toward active milestones; never creates tasks or executes work."""
import time
from backend.canvas.requirement_readiness import require_inputs
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_executions import Executions
from backend.canvas.opora_executions import OporaExecutions

LIMIT = 20


def collect(canvas, project, workspace, milestones):
    if not milestones:
        return []
    repo = ChangesetRepository(canvas.db_for(project), project, workspace)
    head = repo.head()
    documents = repo.read(head)["documents"] if head else []
    by_node = {doc["nodeId"]: doc for doc in documents}
    graph = canvas.view(project, workspace)["graph"]
    known = {node["id"]: node for node in graph["nodes"]}
    found = []
    for milestone in milestones:
        if milestone.get("done"):
            continue
        incomplete = {}
        for criterion in milestone["criteria"]:
            for card in criterion["cards"]:
                if not card["done"]:
                    incomplete.setdefault(card["id"], []).append(criterion["id"])
        for node, criteria in incomplete.items():
            fields = by_node.get(node, {}).get("fields", {})
            blockers, inputs = [], []
            status = "ready"
            if node not in known:
                status, blockers = "blocked", ["Prvek milníku ve Struktuře chybí."]
            elif not head or not fields.get("goal", "").strip() or not fields.get("acceptance", "").strip():
                status, blockers = "needs_specification", ["Chybí přijatý cíl a podmínky dokončení tohoto prvku."]
            elif not fields.get("steps"):
                status, blockers = "needs_plan", ["Přijatému zadání chybí proveditelné kroky plánu."]
            else:
                try:
                    inputs = require_inputs(canvas, project, workspace, node, head, graph, documents)
                    context = OporaExecutions(canvas).context(project, workspace, node)
                    if not context["available"]:
                        status, blockers = "blocked", [context["unavailableReason"] or "Native execution context is unavailable."]
                except ValueError as error:
                    status, blockers = "blocked", [str(error)]
            lease = repo.db.execute("SELECT expires_at FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=?",
                                    (project, workspace, node)).fetchone()
            if status == "ready" and lease and lease[0] > time.time():
                status, blockers = "in_progress", ["Prvek má aktivní realizaci; sleduj existující běh a nevytvářej duplicitní práci."]
            if status == "ready":
                records = Executions(repo.db, project, workspace).history(node)
                latest = records[0] if records else None
                if latest and latest["state"] == "reported":
                    try:
                        from backend.brain_opora.determinism.milestone_evidence import semantic_compatible
                        from backend.editor.research.execution_evidence import validate_assignment
                        affected = [item["nodeId"] for item in latest["assignment"].get("affectedElements", [])]
                        semantic_compatible(repo.db, project, workspace, latest["acceptedRevision"], [node, *affected])
                        validate_assignment(repo.db, project, workspace, latest)
                        if Executions(repo.db, project, workspace).receipts(latest["executionId"]):
                            status, blockers = "reported", ["Posuď odevzdaný výsledek existujícího běhu před další realizací."]
                    except ValueError:
                        pass  # Stale results cannot displace a new execution of the accepted contract.
            found.append({"milestoneId": milestone["id"], "milestoneTitle": milestone["title"], "nodeId": node,
                          "name": known.get(node, {}).get("name", node), "criterionIds": criteria,
                          "action": "realize" if status == "ready" else "resolve_input" if status == "blocked" else "inspect_run" if status == "in_progress" else "inspect_result" if status == "reported" else "specify",
                          "status": status, "acceptedRevision": head, "requiredInputs": inputs, "blockers": blockers,
                          "source": "active milestone criteria"})
        if not incomplete and not milestone.get("verification", {}).get("verified"):
            missing = [criterion["id"] for criterion in milestone["criteria"] if not criterion.get("verification")]
            pin = next((criterion["verification"] for criterion in milestone["criteria"] if criterion.get("verification")), {})
            found.append({"milestoneId": milestone["id"], "milestoneTitle": milestone["title"],
                          "nodeId": pin.get("nodeId"), "criterionIds": missing or [item["id"] for item in milestone["criteria"]],
                          "action": "define_integration" if missing else "verify_integration", "status": "needs_evidence",
                          "acceptedRevision": head, "pinnedRevision": pin.get("acceptedRevision"), "requiredInputs": [],
                          "blockers": ["Chybí přijatý společný integrační scénář s kladnými i zápornými testy." if missing
                                       else milestone.get("verification", {}).get("detail") or milestone.get("verification", {}).get("reason", "integration_evidence_missing")],
                          "source": "active milestone criteria"})
    rank = {"ready": 0, "reported": 0, "needs_specification": 1, "needs_plan": 1, "blocked": 2, "in_progress": 3, "needs_evidence": 4}
    return sorted(found, key=lambda item: (rank[item["status"]], item["milestoneId"], item.get("nodeId") or ""))[:LIMIT]


def lines(items):
    if not items:
        return []
    rows = ["DALŠÍ PRÁCE MILNÍKU:",
            "- Upřednostni připravený krok aktivního milníku; při blokaci doplň uvedený vstup nebo důkaz. Nerozšiřuj nesouvisející větev místo tohoto výsledku."]
    for item in items:
        rows.append(f"- {item['milestoneId']} · {item.get('nodeId') or 'integrační scénář'} · {item['action']} · {item['status']}"
                    f" · zadání {item['acceptedRevision'] or 'nepřijato'} · kritéria {','.join(item['criterionIds'])}"
                    + (" · blokace: " + "; ".join(item["blockers"]) if item["blockers"] else ""))
    return rows
