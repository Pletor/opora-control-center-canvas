"""Deterministický interpret toku: běh nad neměnnou verzí, uzly po hranách `main`, každá změna = událost logu.

- Sub-porty (`model`, `memory`, `tool`, `subagent`, `approval`) se nevykonávají jako kroky; uzel je dostane
  v `ctx["config"]` jako konfiguraci.
- Aktivace uzlu má stálý `idempotency_key` (běh + příčina + uzel); opakovaný pokus zvedne `attempt`.
- `advance` je jediný krok plánovače: uzavře čekání po deadline větví `timeout`, znovu spustí přerušené uzly
  a vykoná frontu. Volá se pod zámkem registru, takže `running` na jeho začátku = přerušený pokus.
  Výjimka: uzel typu `detached` běží mimo zámek; přerušený je, až když mu chybí heartbeat (`stalls.stall_reason`).
  Takový uzel posílá `heartbeat` a končí `finish` / `fail`, které běh zase posunou.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from backend.flow.graph_check import FlowInvalid
from backend.flow.node_types import NODE_TYPES
from backend.flow.run_log import append, now_iso
from backend.flow.stalls import stall_reason
from backend.flow.workflows import FlowConflict, FlowNotFound, get_version, workflow_kind

APPROVAL_DECISIONS = ("approved", "rejected")


def _key(run_id, cause, node_id):
    return hashlib.sha256(f"{run_id}|{cause}|{node_id}".encode()).hexdigest()[:32]


def _queue(db, run_id, node_id, value, cause, now):
    """Zařadí aktivaci uzlu; stejná příčina podruhé nic nepřidá (idempotence)."""
    key = _key(run_id, cause, node_id)
    if db.execute("SELECT 1 FROM flow_node_runs WHERE idempotency_key=?", (key,)).fetchone():
        return
    append(db, run_id, uuid.uuid4().hex, "node.queued",
           {"node_id": node_id, "attempt": 1, "idempotency_key": key, "input": value}, moment=now)


def _complete(db, run_id, row, graph, port, output, now, extra=None):
    """Uzel skončil portem `port`: zapíše výsledek a zařadí cíle hran `main` z tohoto portu."""
    append(db, run_id, row["id"], "node.succeeded", {"port": port, "output": output, **(extra or {})}, moment=now)
    for edge in graph.get("edges", []):
        if edge["source_node"] == row["node_id"] and edge["source_port"] == port and edge.get("kind", "main") == "main":
            _queue(db, run_id, edge["target_node"], output, f"{row['idempotency_key']}|{edge['id']}", now)


def _config(graph, node_id):
    """Sub-porty uzlu: {port: [{node_id, type, params, port}]} ze zdrojů hran jiných než `main`."""
    nodes = {node["id"]: node for node in graph["nodes"]}
    config = {}
    for edge in graph.get("edges", []):
        if edge["target_node"] == node_id and edge.get("kind", "main") != "main":
            source = nodes[edge["source_node"]]
            config.setdefault(edge["target_port"], []).append(
                {"node_id": source["id"], "type": source["type"], "params": source.get("params", {}),
                 "port": edge["source_port"]})
    return config


def _run_row(db, run_id):
    row = db.execute("SELECT * FROM flow_runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise FlowNotFound("Běh neexistuje.")
    return row


def _set_status(db, run_id, status, now):
    if _run_row(db, run_id)["status"] != status:
        append(db, run_id, None, "run.status", {"status": status}, moment=now)


def start_run(db, version_id, trigger=None, registry=NODE_TYPES, now=None, parent_run_id=None):
    """Vytvoří běh z verze a spouštěče `{node_id?, payload?, source?}` a hned ho posune. Záměr stránky se nespouští."""
    trigger = dict(trigger or {})
    version = get_version(db, version_id)
    if workflow_kind(db, version["workflow_id"]) == "page_intent":
        raise FlowConflict("Záměr stránky (page_intent) se nespouští.", "not_runnable")
    graph = version["graph"]
    triggers = [n["id"] for n in graph["nodes"] if registry[n["type"]].trigger]
    node_id = trigger.get("node_id") or (triggers[0] if triggers else None)
    if node_id not in triggers:
        raise FlowInvalid("Spouštěč musí být uzel typu spouštěč v této verzi.")
    trigger["node_id"] = node_id
    run_id = uuid.uuid4().hex
    with db:
        append(db, run_id, None, "run.created",
               {"workflow_version_id": version_id, "trigger": trigger, "parent_run_id": parent_run_id}, moment=now)
        _queue(db, run_id, node_id, trigger.get("payload"), "trigger", now)
    return advance(db, run_id, registry, now)


def _expire_and_resume(db, run_id, graph, registry, now):
    for row in db.execute("SELECT * FROM flow_node_runs WHERE run_id=? AND status='waiting'", (run_id,)).fetchall():
        if row["deadline"] and datetime.fromisoformat(row["deadline"]) <= now:
            _complete(db, run_id, row, graph, "timeout", json.loads(row["input_ref"]), now)
    types = {n["id"]: registry[n["type"]] for n in graph["nodes"]}
    for row in db.execute("SELECT * FROM flow_node_runs WHERE run_id=? AND status='running'", (run_id,)).fetchall():
        if types[row["node_id"]].detached and stall_reason(dict(row), now) is None:
            continue  # běží jinde a hlásí se
        append(db, run_id, row["id"], "node.failed", {"error": "Pokus přerušen, uzel se spustí znovu."}, moment=now)
        append(db, run_id, uuid.uuid4().hex, "node.queued",
               {"node_id": row["node_id"], "attempt": row["attempt"] + 1,
                "idempotency_key": row["idempotency_key"], "input": json.loads(row["input_ref"])}, moment=now)


def _execute(db, run_id, row, graph, registry, now):
    node = next(n for n in graph["nodes"] if n["id"] == row["node_id"])
    with db:
        _set_status(db, run_id, "running", now)
        append(db, run_id, row["id"], "node.started", {"attempt": row["attempt"]}, moment=now)
    ctx = {"run_id": run_id, "node_run_id": row["id"], "node": node, "input": json.loads(row["input_ref"]),
           "config": _config(graph, node["id"]),
           "idempotency_key": row["idempotency_key"], "attempt": row["attempt"], "now": now}
    try:
        if node.get("pinned_output") is not None:
            result = {"port": "main", "output": node["pinned_output"]}
        else:
            result = registry[node["type"]].run(ctx)
    except Exception as error:  # noqa: BLE001 – chyba uzlu = neúspěšný běh, ne pád plánovače
        with db:
            append(db, run_id, row["id"], "node.failed", {"error": str(error) or type(error).__name__}, moment=now)
            _set_status(db, run_id, "failed", now)
        return False
    if result.get("detach"):
        return True  # uzel zůstává `running`, skončí přes finish / fail
    with db:
        if "wait" in result:
            append(db, run_id, row["id"], "node.waiting",
                   {"waiting_for": result["wait"], "deadline": now_iso(result["deadline"])}, moment=now)
        else:
            _complete(db, run_id, row, graph, result["port"], result.get("output"), now)
    return True


def advance(db, run_id, registry=NODE_TYPES, now=None):
    """Jeden krok plánovače; vrací detail běhu. Hotový nebo zrušený běh nechá být."""
    now = now or datetime.now(UTC)
    run = _run_row(db, run_id)
    if run["status"] in ("succeeded", "failed", "cancelled"):
        return get_run(db, run_id)
    graph = get_version(db, run["workflow_version_id"])["graph"]
    with db:
        _expire_and_resume(db, run_id, graph, registry, now)
    while True:
        row = db.execute("SELECT * FROM flow_node_runs WHERE run_id=? AND status='queued' ORDER BY rowid LIMIT 1",
                         (run_id,)).fetchone()
        if row is None:
            break
        if not _execute(db, run_id, row, graph, registry, now):
            return get_run(db, run_id)
    open_ = {row[0] for row in db.execute(
        "SELECT status FROM flow_node_runs WHERE run_id=? AND status IN ('running','waiting')", (run_id,))}
    with db:
        _set_status(db, run_id, "running" if "running" in open_ else "waiting" if open_ else "succeeded", now)
    return get_run(db, run_id)


def _detached_row(db, node_run_id):
    """Řádek uzlu, který běží jinde; None, když mezitím skončil nebo byl prohlášen za přerušený (nic se nemění)."""
    row = db.execute("SELECT * FROM flow_node_runs WHERE id=?", (node_run_id,)).fetchone()
    if row is None:
        raise FlowNotFound("Uzel běhu neexistuje.")
    return row if row["status"] == "running" else None


def heartbeat(db, node_run_id, now=None):
    """Uzel mimo zámek žije: posune `last_heartbeat_at`. Vrací False, když uzel už neběží (práce má skončit)."""
    row = _detached_row(db, node_run_id)
    if row is not None:
        with db:
            append(db, row["run_id"], node_run_id, "node.heartbeat", {}, moment=now)
    return row is not None


def finish(db, node_run_id, port, output, extra=None, registry=NODE_TYPES, now=None):
    """Uzel mimo zámek skončil portem `port`; běh pokračuje. Pozdní hlášení přerušeného pokusu se zahodí (None)."""
    now = now or datetime.now(UTC)
    row = _detached_row(db, node_run_id)
    if row is None:
        return None
    graph = get_version(db, _run_row(db, row["run_id"])["workflow_version_id"])["graph"]
    with db:
        _complete(db, row["run_id"], row, graph, port, output, now, extra)
    return advance(db, row["run_id"], registry, now)


def fail(db, node_run_id, error, now=None):
    """Uzel mimo zámek selhal: běh končí `failed` jako u okamžitého uzlu. Pozdní hlášení se zahodí (None)."""
    row = _detached_row(db, node_run_id)
    if row is None:
        return None
    with db:
        append(db, row["run_id"], node_run_id, "node.failed", {"error": error}, moment=now)
        _set_status(db, row["run_id"], "failed", now)
    return get_run(db, row["run_id"])


def decide(db, node_run_id, decision, actor="human", registry=NODE_TYPES, now=None):
    """Rozhodnutí člověka u `approval.human`: pokračuje portem approved / rejected. Stejné rozhodnutí 2× = nic."""
    if decision not in APPROVAL_DECISIONS:
        raise FlowInvalid("Rozhodnutí je approved nebo rejected.")
    now = now or datetime.now(UTC)
    row = db.execute("SELECT * FROM flow_node_runs WHERE id=?", (node_run_id,)).fetchone()
    if row is None:
        raise FlowNotFound("Uzel běhu neexistuje.")
    if row["status"] == "succeeded" and row["output_port"] == decision:
        return get_run(db, row["run_id"])
    if row["status"] != "waiting":
        raise FlowConflict(f"Uzel nečeká na rozhodnutí, je {row['status']} ({row['output_port']}).")
    graph = get_version(db, _run_row(db, row["run_id"])["workflow_version_id"])["graph"]
    node = next(n for n in graph["nodes"] if n["id"] == row["node_id"])
    if registry[node["type"]].port(decision, "out") is None:
        raise FlowInvalid("Tento uzel nepřijímá rozhodnutí.")
    with db:
        _complete(db, row["run_id"], row, graph, decision, json.loads(row["input_ref"]), now, {"actor": actor})
    return advance(db, row["run_id"], registry, now)


def get_run(db, run_id):
    run = dict(_run_row(db, run_id))
    run["trigger"] = json.loads(run["trigger"])
    rows = db.execute("SELECT * FROM flow_node_runs WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
    run["node_runs"] = [dict(row) for row in rows]
    return run


def list_runs(db, workflow_id=None, limit=100):
    rows = db.execute(
        "SELECT r.* FROM flow_runs r JOIN flow_workflow_versions v ON v.id=r.workflow_version_id "
        "WHERE (? IS NULL OR v.workflow_id=?) ORDER BY r.created_at DESC, r.rowid DESC LIMIT ?",
        (workflow_id, workflow_id, limit),
    ).fetchall()
    return [{**dict(row), "trigger": json.loads(row["trigger"])} for row in rows]
