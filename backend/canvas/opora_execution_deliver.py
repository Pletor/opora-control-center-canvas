"""`POST /api/oporahub/executions/{id}/deliver`: odevzdej kartu jedním voláním (zefektivneni-opory.md §3.2).

Server provede za agenta to, co jde odvodit bez modelu, stejnými funkcemi jako jednotlivé cesty:
1. kroky a výsledek (`ExecutionResults.submit`: `stepResults`, `selfChecks` s `headSha`, `decisions`),
2. lokální sloučení v projektu bez GitHubu (`LocalMerge`, výchozí commit = `git rev-parse HEAD`),
3. běh kontrol na `scope = nodeId` a sha (`CheckRuns`; červená zastaví uzavření),
4. deterministické uzavření karty serverem (`opora_card_auto_close`: `save_node` → `closure_gate`,
   `by: "opora"`), když `close`, žádná červená kontrola a karta je uzavíratelná; jinak `missing` a `next`.
   Plná autonomie k tomu potřeba není; co zůstane otevřené, uzavře smyčka vazeb PR po splnění definice hotovo.

Vypršelé převzetí se přijme, když epocha stojí a kartu nikdo jiný nepřevzal (`leaseRenewed`; cesta to
zapíše do záznamu činnosti jako `lease_renewed_on_deliver`). Opakované odevzdání po odevzdaném výsledku
přeskočí krok 1 a pokračuje sloučením, kontrolami a uzavřením (oprava červené kontroly).
"""
import time

from backend.canvas import opora_card_done as card_done
from backend.canvas import opora_execution_deliver_body as body_rules
from backend.canvas import opora_lease_events as lease_events
from backend.canvas.check_runs import CheckRuns
from backend.canvas.graph import digest
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_local_merge import LocalMerge, repository_path
from backend.canvas.payload_errors import NextStep, invalid
from backend.integrations import git_read

RENEW_TTL = 900


def _superseded(node):
    return NextStep("Kartu mezitím převzal jiný běh (epocha se změnila).", code="execution_superseded",
                    hint=f"Spusť start znovu: opora_hub.py start --node {node}")


def authenticate(executions, identifier, project, workspace, token):
    """Záznam běhu po ověření tokenu; vypršelé převzetí obnoví, pokud kartu nikdo nepřevzal."""
    with executions.transaction(project, workspace) as repo:
        record = repo.read(identifier)
        executions.authenticate(record, token)
        if record["state"] != "running":
            return record, False
        try:
            executions.lease_valid(repo, record)
            return record, False
        except ValueError:
            pass
        epoch = repo.db.execute("SELECT epoch FROM opora_execution_epochs WHERE project_id=? AND workspace_id=?"
                                " AND node_id=?", (*repo.scope, record["nodeId"])).fetchone()
        lease = repo.db.execute("SELECT token FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=?",
                                (*repo.scope, record["nodeId"])).fetchone()
        if not epoch or epoch[0] != record["epoch"] or (lease and lease[0] != record["token"]):
            raise _superseded(record["nodeId"])
        stamp, previous = time.time(), record["expiresAt"]
        record["expiresAt"] = stamp + RENEW_TTL
        if record.get("executionProtocolVersion") == 2:
            record["expiresAt"] = min(record["expiresAt"], record["budget"]["runDeadlineAt"])
        owner = repo.db.execute("SELECT owner FROM opora_executions WHERE id=?", (identifier,)).fetchone()[0]
        repo.db.execute("INSERT OR REPLACE INTO card_leases VALUES(?,?,?,?,?,?)",
                        (*repo.scope, record["nodeId"], owner, record["token"], record["expiresAt"]))
        repo.save(record)
        lease_events.heartbeat(repo, record, ttl=RENEW_TTL, previous_expires=previous, stamp=stamp)
        return record, True


def _git_root(service, project):
    try:
        return repository_path(service, project)
    except ValueError:
        return None


def resolve_head(root, commit):
    """Plné SHA: zadaný commit (musí existovat), jinak HEAD pracovní kopie; bez repa None."""
    if not root:
        return commit
    full = git_read.head(root, commit or "HEAD")
    if commit and not full:
        raise invalid("deliver", "commit", "v repozitáři projektu neexistuje.", "SHA commitu karty, nebo null = HEAD",
                      body_rules.EXAMPLE)
    return full


def submit(executions, record, body, commits, head):
    """Krok 1: výsledek se `stepResults`, `selfChecks` a `decisions`; idempotentní podle obsahu."""
    result = {"summary": body["summary"],
              "stepResults": body_rules.step_results(body, commits, record["assignment"].get("steps"))}
    checks = body_rules.self_checks(body["checks"], head)
    if checks:
        result["selfChecks"] = checks
    if body["decisions"]:
        result["decisions"] = body["decisions"]
    if not result["stepResults"]:
        del result["stepResults"]
    return executions.submit(record["executionId"], {
        "project": record["project"], "workspace": record["workspace"], "token": record["token"],
        "epoch": record["epoch"], "requestId": "deliver-" + digest(result)[:40], "result": result})


def done_state(service, project, workspace, node, closed=False):
    """Stav jediné definice hotovo karty ze stejných dílů jako `closure_gate` (jen čtení); None = karta bez kroků."""
    from backend.canvas import opora_agent_state_pulls as pulls
    from backend.canvas.opora_plan_steps import steps_of
    from backend.canvas.opora_step_results import progress
    from database.repositories.opora_changesets import ChangesetRepository

    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        repo = ChangesetRepository(db, project, workspace)
        head = repo.head()
        document = next((item for item in (repo.read(head)["documents"] if head else []) if item["nodeId"] == node), None)
        if not document or not steps_of(document["fields"]):
            return None
        summary, evidence = progress(db, project, workspace, node, document)
        link = card_done.link_for(pulls.read(service, project, workspace), node)
        gates = card_done.gates_by_execution(db, project, workspace)
        gate = (gates or {}).get(link["executionId"]) if link else None
        blocking = card_done.journeys_blocking(service, project, workspace, node)
        local = None
        if card_done.local_mode(service, project):
            graph = service.view(project, workspace)["graph"]
            local = card_done.local_checks_by_card(service, project, workspace, graph, [link] if link else [], [node])[node]
        return card_done.card_done_state(card_done.facts(
            {"steps": summary, "acceptanceEvidence": evidence, "journeys": blocking}, link, gate,
            closed=closed, external=gates is None, local_checks=local))


def next_step(record, missing, red, closed, autonomy):
    """`autonomy` zůstává v podpisu kvůli volajícím; uzavření dělá server, ne člověk ani agent."""
    node, identifier = record["nodeId"], record["executionId"]
    if closed or missing == ["human_close"]:  # uzavíratelnou kartu uzavře server sám
        return {"verb": "pick", "targetId": None, "command": "opora_hub.py pick --verb claim"}
    if red:
        return {"verb": "deliver", "targetId": identifier, "command":
                f'opora_hub.py deliver --execution {identifier} --summary "…" --check "{red[0]}=green"'}
    first = next((name for name in missing if name != "human_close"), None)
    if first in ("steps", "card_acceptance"):
        return {"verb": "start", "targetId": node, "command": f"opora_hub.py start --node {node}"}
    if first == "journeys":
        return {"verb": "journey_run", "targetId": node, "command": "uv run python tools/journey_run.py --journey <id>"}
    if first in ("gate_ready", "merged", "plan_written_back"):
        return {"verb": "merge", "targetId": identifier, "command":
                f'opora_hub.py deliver --execution {identifier} --summary "…" --commit <sha> --check "npm test=green"'}
    return {"verb": "deliver", "targetId": identifier, "command": f'opora_hub.py deliver --execution {identifier} --summary "…"'}


def deliver(service, identifier, payload, token, actor):
    body = body_rules.validate_body(payload)
    project, workspace = body["project"], body["workspace"]
    if not isinstance(token, str) or not token:
        raise invalid("deliver", "X-Opora-Execution-Token", "chybí hlavička s tokenem běhu.",
                      "token ze start (opora_hub.py ho drží sám)")
    executions = ExecutionResults(service)
    record, renewed = authenticate(executions, identifier, project, workspace, token)
    node = record["nodeId"]
    root = _git_root(service, project)
    head = resolve_head(root, body["commit"])
    if record["state"] == "running":
        graph = service.view(project, workspace)["graph"]
        receipt = submit(executions, record, body, body_rules.card_commits(root, node, graph["nodes"]), head)
    else:  # výsledek už odevzdaný: pokračuje sloučení, kontroly a uzavření
        receipts = executions.receipts(identifier, project, workspace)["results"]
        if not receipts:
            raise _superseded(node)
        receipt = receipts[-1]
    merged = None
    if head and card_done.local_mode(service, project):
        link = LocalMerge(service).merge(identifier, {"project": project, "workspace": workspace, "commit": head}, actor)
        merged = link["commit"]
    sha = merged or head
    runs = CheckRuns(service)
    written = 0
    for item in body_rules.check_runs(body["checks"]) if sha else []:
        detail = (item["name"] + (": " + item["output"] if item["output"] else ""))[:2000]
        runs.record((project, workspace, node), {"status": item["status"], "sha": sha, "detail": detail})
        written += 1
    red = [item["name"] for item in body["checks"] if item["status"] == "red"]
    autonomy = actor == "human" or service.project_hub.agent_autonomy(project)["full"]
    state = done_state(service, project, workspace, node)
    closed = False
    if state is not None and body["close"] and not red and card_done.closable(state):
        from backend.canvas.opora_card_auto_close import close_card
        closed = close_card(service, project, workspace, node, body["summary"])
        if closed:
            state = done_state(service, project, workspace, node, closed=True)
    missing = state["missing"] if state is not None else ["steps"]
    return {"executionId": identifier, "nodeId": node,
            "delivered": {"receiptId": receipt["receiptId"], "steps": [
                {"stepId": item["stepId"], "status": item["status"]}
                for item in (receipt.get("result") or {}).get("stepResults", [])]},
            "merged": merged, "checks": written, "closed": closed, "missing": missing,
            "leaseRenewed": renewed, "next": next_step(record, missing, red, closed, autonomy)}
