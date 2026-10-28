"""Strážce `prace` (`docs/strazci.md` §4): nároky karet a běhy (executions), jen čte a hlásí.

Pravidla (vše `severity warn`, strážce nic neuvolňuje; propadlý nárok uvolní až příští claim jako dnes):
- `work.lease-expired`: nárok karty (`card_leases`) je po termínu (`expires_at`, u běhu s rozpočtem i konec
  rozpočtu) a pořád leží na kartě, tedy karta se dál tváří, že se staví. Klíč `work:lease-expired:<prostor>:<karta>:<běh|vlastník>`.
- `work.no-heartbeat`: běh s platným nárokem, od jehož poslední zprávy uběhlo víc než 10 min. Zpráva = jakákoli
  událost běhu (claim, krok, výsledek, heartbeat) a odhad posledního heartbeatu `expiresAt − ttl`: tichý
  heartbeat událost nevydává (`opora_lease_events.heartbeat`), ale prodlouží `expiresAt` o známé `ttl` (z poslední
  události `lease.heartbeat`, jinak z claimu). Když termín uřízl rozpočet, odhad neplatí a počítají se jen události.
  Klíč `work:no-heartbeat:<běh>`.
- `work.step-stalled`: běh s platným nárokem, jehož poslední událost kroku je `step.started` starší než 30 min
  (krok běží a nic o něm nepřišlo). Klíč `work:step-stalled:<běh>:<krok>`.
Propadlý nárok hlásí jen `work.lease-expired`, ostatní dvě pravidla platí pro živé běhy.
"""
import json
from datetime import datetime

from backend.canvas.strazci.registry import Guard

NO_HEARTBEAT_S = 10 * 60
STEP_STALLED_S = 30 * 60
STEP_KINDS = ("step.started", "step.done", "step.failed")


def epoch(value):
    """ISO čas události → epoch sekundy; nečitelný = None."""
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


def _event(db, project, workspace, execution, kinds):
    marks = ",".join("?" * len(kinds))
    row = db.execute(f"SELECT kind, at, step_id, data FROM opora_events WHERE project_id=? AND workspace_id=?"
                     f" AND execution_id=? AND kind IN ({marks}) ORDER BY id DESC LIMIT 1",
                     (project, workspace, execution, *kinds)).fetchone()
    return None if row is None else {"kind": row[0], "at": row[1], "stepId": row[2], "data": json.loads(row[3])}


def _last_beat(db, project, workspace, record):
    """Odhad času posledního heartbeatu `expiresAt − ttl`, nebo None, když ttl neznáme nebo termín uřízl rozpočet."""
    deadline = (record.get("budget") or {}).get("runDeadlineAt")
    if deadline is not None and record["expiresAt"] >= deadline:
        return None
    beat = _event(db, project, workspace, record["executionId"], ("lease.heartbeat",))
    if beat is not None and isinstance(beat["data"].get("ttlSeconds"), (int, float)):
        return record["expiresAt"] - beat["data"]["ttlSeconds"]
    claim = _event(db, project, workspace, record["executionId"], ("lease.claimed",))
    claimed_at = epoch(claim["at"]) if claim else None
    expires = claim["data"].get("expiresAt") if claim else None
    if claimed_at is None or not isinstance(expires, (int, float)):
        return None
    return record["expiresAt"] - (expires - claimed_at)


def read_leases(service, project):
    """Nároky projektu s během, který je drží: `[{workspaceId, nodeId, owner, expiresAt, execution|None}]`."""
    items = []
    with service.reading(project):
        db = service.db_for(project)
        leases = db.execute("SELECT workspace_id,node_id,owner,token,expires_at FROM card_leases WHERE project_id=?"
                            " ORDER BY workspace_id,node_id", (project,)).fetchall()
        for workspace, node, owner, token, expires_at in leases:
            row = db.execute("SELECT record FROM opora_executions WHERE project_id=? AND workspace_id=? AND node_id=?"
                             " AND json_extract(record,'$.token')=? ORDER BY rowid DESC LIMIT 1",
                             (project, workspace, node, token)).fetchone()
            execution = None
            if row is not None:
                record = json.loads(row[0])
                identifier = record["executionId"]
                last = db.execute("SELECT MAX(at) FROM opora_events WHERE project_id=? AND workspace_id=?"
                                  " AND execution_id=?", (project, workspace, identifier)).fetchone()[0]
                step = _event(db, project, workspace, identifier, STEP_KINDS)
                execution = {"executionId": identifier, "state": record["state"],
                             "deadline": (record.get("budget") or {}).get("runDeadlineAt"),
                             "messages": [value for value in (epoch(last), _last_beat(db, project, workspace, record),
                                                              epoch(record.get("createdAt"))) if value is not None],
                             "step": step if step and step["kind"] == "step.started" else None}
            items.append({"workspaceId": workspace, "nodeId": node, "owner": owner, "expiresAt": expires_at,
                          "execution": execution})
    return items


def evaluate(leases, now):
    """Čistá pravidla nad přečtenými nároky (viz docstring modulu)."""
    findings = []
    for lease in leases:
        run, base = lease["execution"], {"workspaceId": lease["workspaceId"], "nodeId": lease["nodeId"]}
        deadline = min(value for value in (lease["expiresAt"], (run or {}).get("deadline")) if value is not None)
        if deadline <= now:
            holder = run["executionId"] if run else lease["owner"]
            findings.append({**base, "key": f"work:lease-expired:{lease['workspaceId']}:{lease['nodeId']}:{holder}",
                             "rule": "work.lease-expired", "severity": "warn",
                             "message": f"Nárok karty ({lease['owner']}) je po termínu a karta se dál tváří, že se staví.",
                             **({"executionId": run["executionId"]} if run else {})})
            continue
        if run is None or run["state"] != "running":
            continue
        last = max(run["messages"], default=None)
        if last is not None and now - last > NO_HEARTBEAT_S:
            findings.append({**base, "key": f"work:no-heartbeat:{run['executionId']}", "rule": "work.no-heartbeat",
                             "severity": "warn", "executionId": run["executionId"],
                             "message": f"Běh je bez zprávy déle než 10 min ({lease['owner']}).",
                             "data": {"silentMinutes": int((now - last) // 60)}})
        step, since = run.get("step"), epoch((run.get("step") or {}).get("at"))
        if step and since is not None and now - since > STEP_STALLED_S:
            findings.append({**base, "key": f"work:step-stalled:{run['executionId']}:{step['stepId']}",
                             "rule": "work.step-stalled", "severity": "warn", "executionId": run["executionId"],
                             "message": f"Krok {step['stepId']} běží déle než 30 min bez výsledku."})
    return findings


def run(ctx):
    return evaluate(read_leases(ctx.service, ctx.project), ctx.now)


GUARD = Guard(id="prace", label="Práce na kartách", every_s=30, run=run)
