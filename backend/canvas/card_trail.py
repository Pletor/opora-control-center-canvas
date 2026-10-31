"""Stopa práce karty: čistá projekce existujících záznamů do jedné odpovědi (docs/stopa-prace-karty.md).

Vstupem jsou syrová fakta, která posbírá `card_trail_read.gather` (běhy exekucí s výsledky a průběžnými kroky,
úkoly brány, události, záznam činnosti, zprávy na vazbách, PR, `dod.missing`, soubory commitů). Funkce nic
nečte, nic nezapisuje a nevolá model. Každý text nese `source`: `det` (odvozeno kódem), `agent` (napsal
dělník), `heart` (napsalo srdce), `human` (napsal člověk). Stav, kontroly, commity a soubory jsou vždy záznam.
"""
from datetime import UTC, datetime

from backend.canvas.card_trail_judgment import judgment

RECENT = 10
QUIET_KINDS = ("lease.heartbeat",)  # tikání převzetí do logu karty nepatří, `now` ho nese samo
CHECK_STATUS = {"passed": "green", "failed": "red"}


def moment(value):
    """Čas jako aware datetime pro řazení (ISO s `Z` i `+00:00`, epocha); neznámý = nejstarší."""
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, UTC)
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError, OSError, OverflowError):
        return datetime.min.replace(tzinfo=UTC)


def iso(epoch):
    return None if not isinstance(epoch, (int, float)) else (
        datetime.fromtimestamp(epoch, UTC).isoformat(timespec="seconds").replace("+00:00", "Z"))


def author(name):
    """Původ textu podle pisatele: srdce, člověk, jinak dělník."""
    text = str(name or "")
    if text in ("heart", "agent:heart"):
        return "heart"
    return "human" if text == "human" else "agent"


def _checks(names, self_checks):
    status = {item.get("command"): CHECK_STATUS.get(item.get("status"), "unknown")
              for item in (self_checks or {}).get("checks") or [] if isinstance(item, dict)}
    return [{"name": name, "status": status.get(name, "unknown")} for name in names or [] if isinstance(name, str)]


def _files(commits, files):
    if files is None or not commits:
        return None
    found = []
    for sha in commits:
        found += [path for path in files.get(sha) or [] if path not in found]
    return found


def _step(step_id, title, item, self_checks, files, allowed):
    evidence = (item or {}).get("evidence") or {}
    notes = evidence.get("notes") if isinstance(evidence.get("notes"), str) else ""
    commits = [sha for sha in evidence.get("commits") or [] if isinstance(sha, str)]
    value = {"stepId": step_id, "title": title, "status": (item or {}).get("status", "pending"),
             "checks": _checks(evidence.get("checks"), self_checks), "commits": commits,
             "notes": notes, "source": "agent" if notes.strip() else "det"}
    changed = _files(commits, files)
    if changed is not None:
        value["files"] = changed
    if allowed is not None:
        value["allowed"] = allowed
    return value


def execution_run(run, files):
    """Jeden běh exekuce: kroky zadání v pořadí zadání, hlášení z výsledku má přednost před průběžným krokem."""
    record, receipts = run["record"], run.get("receipts") or []
    result = (receipts[-1].get("result") if receipts else None) or {}
    reported = {item.get("stepId"): item for item in run.get("checkpoints") or [] if isinstance(item, dict)}
    for receipt in receipts:  # nejstarší první: novější výsledek přepíše starší i průběžný krok
        for item in (receipt.get("result") or {}).get("stepResults") or []:
            if isinstance(item, dict):
                reported[item.get("stepId")] = item
    pinned = [item for item in (record.get("assignment") or {}).get("steps") or [] if isinstance(item, dict)]
    order = [item["id"] for item in pinned] + [key for key in reported if key not in {s["id"] for s in pinned}]
    by_id = {item["id"]: item for item in pinned}
    steps = [_step(key, by_id.get(key, {}).get("title"), reported.get(key), result.get("selfChecks"), files,
                   by_id.get(key, {}).get("files")) for key in order if isinstance(key, str)]
    summary = result.get("summary") if isinstance(result.get("summary"), str) else ""
    return {"executionId": record.get("executionId"), "taskId": None, "owner": record.get("owner"),
            "createdAt": record.get("createdAt"), "until": iso(record.get("expiresAt")), "state": record.get("state"),
            "summary": summary, "source": author(record.get("owner")) if summary.strip() else "det",
            "attempts": len(receipts), "reported": bool(receipts), "steps": steps}


def task_owner(task, events):
    """Dělník úkolu brány: poslední agent v událostech `gate.task` toho úkolu (nejnovější první)."""
    for event in events:
        actor = event.get("actor") or {}
        if (event.get("kind") == "gate.task" and (event.get("data") or {}).get("taskId") == task.get("taskId")
                and actor.get("kind") == "agent" and actor.get("name") not in (None, "heart")):
            return actor["name"]
    return None


def task_run(task, events, files):
    """Úkol brány jako běh s jedním krokem (krok = úkol); `attempts` = počet červených hlášení."""
    report = task.get("report") or {}
    checks = [{"name": item.get("name"), "status": item.get("status", "unknown")}
              for item in report.get("checks") or [] if isinstance(item, dict)]
    commits = [report["sha"]] if isinstance(report.get("sha"), str) else []
    status = {"done": "done", "failed": "failed"}.get(task.get("status"), "pending")
    step = {"stepId": task.get("taskId"), "title": task.get("title"), "status": status, "checks": checks,
            "commits": commits, "notes": "", "source": "det"}
    changed = _files(commits, files)
    if changed is not None:
        step["files"] = changed
    allowed = (task.get("body") or {}).get("files")
    if isinstance(allowed, list):
        step["allowed"] = allowed
    summary = report.get("summary") if isinstance(report.get("summary"), str) else ""
    return {"executionId": None, "taskId": task.get("taskId"), "owner": task_owner(task, events),
            "createdAt": task.get("createdAt"), "until": None, "state": task.get("status"), "summary": summary,
            "source": "agent" if summary.strip() else "det", "attempts": task.get("attempts") or 0,
            "reported": task.get("report") is not None, "steps": [step]}


def current(runs):
    """Kdo kartu teď drží: běžící exekuce, jinak úkol brány přidělený relaci."""
    for run in runs:
        if run["state"] in ("running", "assigned"):
            step = next((item["stepId"] for item in run["steps"] if item["status"] != "done"), None)
            return {"owner": run["owner"], "since": run["createdAt"], "until": run["until"], "stepId": step,
                    "source": "det"}
    return None


def recent(events, activity, limit=RECENT):
    """Posledních `limit` změn karty z událostí a záznamu činnosti, nejnovější první."""
    items = []
    for event in events:
        if event.get("kind") in QUIET_KINDS:
            continue
        actor = event.get("actor") or {}
        items.append({"at": event.get("at"), "who": actor.get("name") or actor.get("kind"),
                      "label": event.get("title") or event.get("kind"), "kind": event.get("kind"),
                      "source": "det" if (event.get("source") or "opora") == "opora" else "agent"})
    for entry in activity:
        if not 200 <= int(entry.get("status") or 0) <= 299:
            continue
        items.append({"at": entry.get("at"), "who": entry.get("agent") or entry.get("actor"),
                      "label": entry.get("label"), "kind": "write", "source": "det"})
    items.sort(key=lambda item: moment(item["at"]), reverse=True)
    return items[:limit]


def ports(node, edges, names, reports):
    """Vazby z karty a poslední zpráva na každé (`state.edges[edgeId]`)."""
    found = []
    for edge in sorted((item for item in edges if item.get("source") == node), key=lambda item: item["id"]):
        report = reports.get(edge["id"]) if isinstance(reports.get(edge["id"]), dict) else {}
        by = report.get("agent") or report.get("by")
        written = bool(str(report.get("summary") or "").strip() or str(report.get("handoff") or "").strip())
        found.append({"edgeId": edge["id"], "targetId": edge.get("target"), "targetName": names.get(edge.get("target")),
                      "summary": report.get("summary"), "handoff": report.get("handoff"), "by": by,
                      "updatedAt": report.get("updatedAt"),
                      "source": ("human" if report.get("by") == "human" else author(by)) if written else "det"})
    return found


def after_merge(facts):
    """Záznam „Kroky přibyly po sloučení“ (docs/oporahub-plan-steps.md): co uznalo sloučení mimo standardní proces,
    s PR, sha a kroky, aby šel pozdější problém dohledat k místu vzniku; None u karty ve standardním procesu."""
    from backend.canvas.opora_card_done import after_merge_note

    found = facts.get("afterMerge")
    if not isinstance(found, dict) or not found.get("afterMerge"):
        return None
    evidence = found.get("afterMergeEvidence") or {}
    return {"requirements": list(found["afterMerge"]), "number": evidence.get("number"), "mergeSha": evidence.get("mergeSha"),
            "executionId": evidence.get("executionId"), "steps": list(evidence.get("steps") or []),
            "label": after_merge_note(found), "source": "det"}


def project_trail(facts):
    """Celá stopa jedné karty z `facts` (tvar viz `card_trail_read.gather`)."""
    files, events = facts.get("files"), facts.get("events") or []
    runs = [execution_run(run, files) for run in facts.get("runs") or []]
    runs += [task_run(task, events, files) for task in facts.get("tasks") or []]
    runs.sort(key=lambda run: moment(run["createdAt"]), reverse=True)
    return {"nodeId": facts["nodeId"], "now": current(runs), "runs": runs, "pr": facts.get("pr"),
            "missing": list(facts.get("missing") or []), "recent": recent(events, facts.get("activity") or []),
            "ports": ports(facts["nodeId"], facts.get("edges") or [], facts.get("names") or {},
                           facts.get("reports") or {}),
            "judgment": judgment(runs), "filesKnown": files is not None, "afterMerge": after_merge(facts)}
