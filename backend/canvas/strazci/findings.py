"""Nálezy strážců a jejich diff (`docs/strazci.md` §3).

`Finding = {key, guard, rule, severity: info|warn|block, message, nodeId?, journeyId?, executionId?, data?}`
plus nepovinné `workspaceId` (prostor, do kterého jde událost; výchozí `draft`). Strážce vrací úplný seznam
svých aktuálních nálezů; `apply` ho porovná s otevřenými nálezy v tabulce `guard_findings`:
nový → vloží a vydá `guard.alert`, trvající → jen `last_seen` (a aktuální znění, bez události),
zmizelý → `resolved_at` a `guard.resolved`. Vyřešené nálezy starší 14 dní se při každém zápisu smažou.

Žádná záplava: první běh strážce v projektu (v tabulce o něm není žádný záznam) založí nálezy bez jednotlivých
událostí a vydá jednu souhrnnou `guard.alert` s `data: {guard, rule: "baseline", count, bySeverity, severity,
message}`; stejně jeden běh s víc než `BATCH_LIMIT` novými nálezy vydá jednu souhrnnou událost (`rule: "batch"`).
Vše v jedné transakci pod zámkem projektu, takže řádek a událost vznikají spolu.
"""
from datetime import UTC, datetime

from backend.canvas.opora_events import emit_event, stamp
from database.repositories.guard_findings import GuardFindings

SEVERITIES = ("info", "warn", "block")
RETENTION_DAYS = 14
DEFAULT_WORKSPACE = "draft"
BATCH_LIMIT = 20


def at_of(now):
    """Epoch sekundy → ISO text v UTC (stejný tvar jako `at` událostí)."""
    return stamp(datetime.fromtimestamp(now, UTC))


def validate(guard, findings):
    """Ověří výstup strážce; vrací nálezy podle `key` (poslední vyhrává). Neplatný výstup = `ValueError`."""
    if not isinstance(findings, list):
        raise ValueError(f"Strážce {guard} musí vrátit seznam nálezů nebo None.")
    result = {}
    for item in findings:
        if not isinstance(item, dict):
            raise ValueError(f"Strážce {guard}: nález není objekt.")
        for name in ("key", "rule", "message"):
            if not isinstance(item.get(name), str) or not item[name]:
                raise ValueError(f"Strážce {guard}: nález potřebuje neprázdné {name}.")
        if item.get("severity") not in SEVERITIES:
            raise ValueError(f"Strážce {guard}: závažnost je info, warn nebo block.")
        if item.get("guard", guard) != guard:
            raise ValueError(f"Strážce {guard} vrátil nález jiného strážce.")
        result[item["key"]] = {**item, "guard": guard}
    return result


def diff(open_keys, current_keys):
    """(nové, trvající, zmizelé) klíče; pořadí nových podle výstupu strážce, zmizelých podle abecedy."""
    current = list(current_keys)
    new = [key for key in current if key not in open_keys]
    ongoing = [key for key in current if key in open_keys]
    resolved = sorted(set(open_keys) - set(current))
    return new, ongoing, resolved


def payload_of(finding):
    return {name: finding[name] for name in ("journeyId", "executionId", "data", "workspaceId")
            if finding.get(name) is not None}


def _event(db, project, kind, finding, actor):
    data = {"key": finding["key"], "guard": finding["guard"], "rule": finding["rule"],
            "severity": finding["severity"], "message": finding["message"]}
    if finding.get("journeyId") is not None:
        data["journeyId"] = finding["journeyId"]
    emit_event(db, project_id=project, workspace_id=finding.get("workspaceId") or DEFAULT_WORKSPACE, kind=kind,
               node_id=finding.get("nodeId"), execution_id=finding.get("executionId"), actor=actor, data=data)


def summary(guard, rule, items):
    """Data souhrnné `guard.alert` za dávku nových nálezů (první běh nebo víc než `BATCH_LIMIT`)."""
    by_severity = {severity: sum(item["severity"] == severity for item in items) for severity in reversed(SEVERITIES)}
    highest = next(severity for severity, count in by_severity.items() if count)
    text = "první běh založil" if rule == "baseline" else "jeden běh přinesl"
    return {"guard": guard, "rule": rule, "count": len(items), "bySeverity": by_severity, "severity": highest,
            "message": f"Strážce {guard}: {text} {len(items)} nových nálezů."}


def _summary_event(db, project, guard, rule, items, actor):
    workspaces = {item.get("workspaceId") or DEFAULT_WORKSPACE for item in items}
    workspace = workspaces.pop() if len(workspaces) == 1 else DEFAULT_WORKSPACE
    emit_event(db, project_id=project, workspace_id=workspace, kind="guard.alert", actor=actor,
               data=summary(guard, rule, items))


def apply(service, project, guard, findings, now):
    """Zapíše diff výstupu strážce; vrací `{new, ongoing, resolved}` se seznamy klíčů."""
    current = validate(guard, findings)
    at = at_of(now)
    cutoff = at_of(now - RETENTION_DAYS * 86400)
    actor = {"kind": "system", "name": f"strazce:{guard}"}
    db = service.db_for(project)
    with service.lock_for(project), db:
        db.execute("BEGIN IMMEDIATE")
        store = GuardFindings(db, project)
        baseline = not store.has_any(guard)
        open_keys = store.open_keys(guard)
        new, ongoing, resolved = diff(open_keys, current)
        for key in ongoing:
            store.touch(current[key], payload_of(current[key]), at)
        quiet = baseline or len(new) > BATCH_LIMIT
        for key in new:
            store.upsert_new(current[key], payload_of(current[key]), at)
            if not quiet:
                _event(db, project, "guard.alert", current[key], actor)
        if quiet and new:
            _summary_event(db, project, guard, "baseline" if baseline else "batch", [current[key] for key in new], actor)
        if resolved:
            gone = {item["key"]: item for item in store.list(open_only=True, limit=100_000) if item["key"] in resolved}
            for key in resolved:
                store.resolve(key, at)
                _event(db, project, "guard.resolved", gone[key], actor)
        store.prune(cutoff)
    return {"new": new, "ongoing": ongoing, "resolved": resolved}
