"""`POST /api/oporahub/executions/start`: vezmi kartu jedním voláním (docs/navrhy/2026-10-28-zefektivneni-opory.md §3.1).

Server sám připne kontext v2 (`prepare`), z čerstvého stavu spočítá očekávané hlavy (přijatá revize,
`contextVersion`, rozpočet) a provede tentýž claim jako `/executions/claim` s deterministickým `requestId`.
Opakovaný start téhož aktéra na téže kartě s živým převzetím vrátí stávající běh (`resumed: true`).
Žádná nová pravidla: připravenost, rozpočet i převzetí hlídá `OporaExecutions.claim`.
"""
from backend.canvas.graph import digest
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_execution_context import prepare
from backend.canvas.opora_execution_steps import assignment_progress
from backend.canvas.payload_errors import NextStep, invalid, keys_problem

REQUIRED, OPTIONAL = {"project", "workspace", "nodeId"}, {"ttlSeconds"}
DEFAULT_TTL = 900
EXAMPLE = {"project": "PROJECT", "workspace": "draft", "nodeId": "n1"}


def validate_body(payload):
    problem = keys_problem(payload, REQUIRED, OPTIONAL)
    if problem:
        raise invalid("start", "body", problem, "{project, workspace, nodeId, ttlSeconds?}", EXAMPLE)
    node, ttl = payload["nodeId"], payload.get("ttlSeconds", DEFAULT_TTL)
    if not isinstance(node, str) or not node.strip():
        raise invalid("start", "nodeId", "chybí ID karty.", "ID karty z agent-state", EXAMPLE)
    if type(ttl) is not int or not 30 <= ttl <= 3600:
        raise invalid("start", "ttlSeconds", "mimo rozsah.", "celé číslo 30–3600", {**EXAMPLE, "ttlSeconds": 900})
    project, workspace = scope(payload)
    return project, workspace, node, ttl


def deliver_command(identifier):
    return (f'opora_hub.py deliver --execution {identifier} --summary "…" --step s1:"…" '
            '--check "npm test=green"')


def shape(executions, record, resumed):
    """Stručná odpověď: běh, token, epocha, zadání a kroky se stavem; `next` = odevzdání."""
    with executions.transaction(record["project"], record["workspace"]) as repo:
        progress = assignment_progress(repo.db, record)
    status = {item["id"]: item["status"] for item in progress.get("steps", [])}
    steps = [{"id": item["id"], "title": item.get("title"), "dod": item.get("acceptance", []),
              "status": status.get(item["id"], "waiting")} for item in record["assignment"].get("steps") or []]
    return {"executionId": record["executionId"], "nodeId": record["nodeId"], "token": record["token"],
            "epoch": record["epoch"], "expiresAt": record["expiresAt"], "acceptedRevision": record["acceptedRevision"],
            "contextVersion": record["assignment"].get("contextVersion"), "resumed": resumed,
            "assignment": record["assignment"], "steps": steps,
            "next": {"verb": "deliver", "targetId": record["executionId"], "command": deliver_command(record["executionId"])}}


def _live(executions, project, workspace, node, owner):
    """Běžící běh tohoto vlastníka na kartě s živým převzetím, nebo None."""
    with executions.transaction(project, workspace) as repo:
        for record in repo.history(node):
            if record.pop("owner", None) != owner or record.get("state") != "running":
                continue
            try:
                executions.lease_valid(repo, record)
            except ValueError:
                continue
            return record
    return None


def _next_epoch(executions, project, workspace, node):
    row = executions.canvas.db_for(project).execute(
        "SELECT epoch FROM opora_execution_epochs WHERE project_id=? AND workspace_id=? AND node_id=?",
        (project, workspace, node)).fetchone()
    return (row[0] if row else 0) + 1


def start(executions, payload, owner):
    project, workspace, node, ttl = validate_body(payload)
    current = _live(executions, project, workspace, node, owner)
    if current is not None:
        return shape(executions, current, True)
    base = {"project": project, "workspace": workspace, "nodeId": node}
    ctx = prepare(executions, {**base, "contextProtocolVersion": 2})
    if not ctx["available"]:
        raise NextStep("Karta teď není k převzetí: " + str(ctx["unavailableReason"]), code="card_unavailable",
                       hint="Načti opora_hub.py state --fresh; rozpočet nebo politika karty blokuje převzetí.")
    claim = {**base, "expectedAcceptedHead": ctx["acceptedHead"], "expectedContextVersion": ctx["contextVersion"],
             "ttlSeconds": ttl, "contextProtocolVersion": 2}
    if ctx["executionProtocolVersion"] == 2:
        budget = ctx.get("budget") or {}
        claim |= {"expectedBudgetPolicyHead": budget.get("policyHead"),
                  "previousExecutionId": budget.get("latestExecutionId")}
    # Deterministické requestId: tytéž hlavy a táž další epocha = týž claim (opakování po výpadku spojení).
    seed = {**claim, "epoch": _next_epoch(executions, project, workspace, node)}
    claim["requestId"] = "start-" + digest(seed)[:40]
    try:
        record = executions.claim(claim, owner)
    except ValueError as exc:
        if str(exc) == "Card already has an active lease.":
            raise NextStep("Kartu drží jiný běh.", code="card_leased",
                           hint="Vyber jinou ready kartu (opora_hub.py pick --verb claim), nebo počkej na vypršení převzetí.") from exc
        raise
    return shape(executions, record, False)
