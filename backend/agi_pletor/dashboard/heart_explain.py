"""Průhled srdce: co dělá, proč čeká, kde se může zastavit a čím to ovlivnit (docs/navrhy/2026-11-13-pruhled-srdce.md).

`explain` skládá stav srdce v paměti (fronta, stropy, spánek, běžící dávka), průchod tokem srdce z `flow_node_runs`
(zpráva/událost → Jev → snímek → srdce, každý uzel s časem) a rozpad posledních dávek z deníku (`heart_phases`).
Jen čte. Zdroj, který selže, vrátí `{error}` místo dat. `text` je totéž v řádcích pro agenty.
"""
import time

from backend.agi_pletor.dashboard.heart_phases import analyze, headline
from backend.agi_pletor.dashboard.heart_stops import stops
from backend.agi_pletor.dashboard.heart_view import safe
from backend.brain_opora.heart import batch
from backend.brain_opora.heart.steps import redact
from backend.flow.catalogs.heart import caps_settings, model_settings
from backend.flow.catalogs.heart.state import HOUR, iso

NODES = {"udalost": "událost", "zprava": "zpráva člověka", "jev": "Jev (zařazení vstupů)",
         "snimek": "snímek projektu", "srdce": "srdce (claude -p)"}
REF_KEYS = ("ticketId", "requestId", "nodeId", "continuationId", "entryId", "messageId")
BATCHES = 5


def _ref(item):
    found = next((str(item[key]) for key in REF_KEYS if isinstance(item.get(key), str)), "")
    return found or redact(" ".join(str(item.get("text") or "").split()))[:60]  # zpráva člověka: začátek textu


def _open_node(pipeline):
    """Uzel, ve kterém stojí otevřený běh toku srdce (snímek čeká na zámek, srdce běží), nebo None."""
    for run in pipeline if isinstance(pipeline, list) else []:
        if run["status"] in ("queued", "running", "waiting"):
            return next((node for node in run["nodes"] if node["status"] in ("running", "waiting")), None)
    return None


def waiting(heart, project, caps, now, pipeline=None):
    """Stav srdce jednou větou: `{state, sentence, until?}`."""
    status = heart.status(project, now)
    with heart.lock:
        items = list(heart.pending.get(project, []))
        recent = [start for start in heart.starts.get(project, []) if start > now - HOUR]
    if not status["enabled"]:
        return {"state": "off", "sentence": "Srdce je vypnuté (OPORA_HEART=off nebo server neposlouchá jen na loopbacku)."}
    node = _open_node(pipeline)
    if status["running"] and not (status.get("current") or {}).get("startedAt") and node:
        seconds = round((node["ms"] or 0) / 1000)
        stalled = " Uzel nehlásí heartbeat; plánovač ho po 5 min obnoví." if seconds > 300 else ""
        return {"state": "running", "sentence": f"Tok srdce stojí v uzlu „{node['label']}“ {seconds} s; model ještě "
                                                f"neběží.{stalled}"}
    if status["running"]:
        current = status.get("current") or {}
        steps = current.get("steps") or []
        last = steps[-1]["text"][:160] if steps else "zatím bez kroku"
        typical = status.get("typicalMs")
        return {"state": "running", "since": current.get("startedAt"),
                "sentence": f"Pracuje na dávce od {current.get('startedAt') or '?'}; poslední krok: {last}"
                            + (f" (obvykle trvá {round(typical / 1000)} s)" if typical else "")}
    if status["sleeping"]:
        return {"state": "sleeping", "until": status["sleepingUntil"],
                "sentence": f"Spí po limitu předplatného do {status['sleepingUntil']}; pak pokračuje samo."}
    if items:
        due = min(entry[2] for entry in items)
        human = any(entry[1].get("type") == "message" for entry in items)
        if due > now:
            return {"state": "window", "until": iso(due),
                    "sentence": f"{len(items)} vstupů čeká na okno sběru; dávka začne nejdřív v {iso(due)}."}
        if not human and len(recent) >= caps["per_hour"]:
            until = iso(min(recent) + HOUR)
            return {"state": "hour_cap", "until": until,
                    "sentence": f"Strop {caps['per_hour']} automatických dávek za hodinu je vyčerpaný; další smí začít "
                                f"v {until}. Zpráva člověka strop obchází, strop jde zvednout ve Velínu → Srdce."}
        return {"state": "starting", "sentence": f"{len(items)} vstupů je splatných; dávka se spustí při dalším průchodu."}
    reasons = {"frontier_empty": "Nemá co dělat: žádný vstup a přijatý plán nemá další kartu.",
               "waiting_human": "Čeká na člověka: další krok plánu patří člověku."}
    return {"state": "idle", "sentence": reasons.get(status.get("idleReason"),
                                                      "Spí bez vstupu; probudí ho lístek, sloučení, spouštěč karty "
                                                      "nebo zpráva člověka.")}


def queue(heart, project, now):
    with heart.lock:
        items = list(heart.pending.get(project, []))
    return [{"type": item.get("type"), "ref": _ref(item), "workspace": workspace, "dueAt": iso(due),
             "dueInS": max(round(due - now), 0)} for workspace, item, due in items]


def pipeline(service, project, limit=3):
    """Poslední běhy toku srdce projektu: uzly v pořadí s trváním (snímek čeká na zámek projektu, srdce je model)."""
    with service.registry_lock:
        runs = service.db.execute(
            "SELECT id, status, created_at FROM flow_runs WHERE json_extract(trigger, '$.payload.project')=? "
            "ORDER BY created_at DESC LIMIT ?", (project, limit)).fetchall()
        nodes = {run["id"]: service.db.execute(
            "SELECT node_id, status, started_at, ended_at, error FROM flow_node_runs WHERE run_id=? "
            "ORDER BY started_at", (run["id"],)).fetchall() for run in runs}
    return [{"run": run["id"], "status": run["status"], "at": run["created_at"],
             "nodes": [{"node": row["node_id"], "label": NODES.get(row["node_id"], row["node_id"]),
                        "status": row["status"], "ms": _ms(row["started_at"], row["ended_at"]),
                        "error": row["error"]} for row in nodes[run["id"]]]} for run in runs]


def _ms(start, end):
    from datetime import datetime
    if not start:
        return None
    finish = datetime.fromisoformat(end) if end else datetime.now(datetime.fromisoformat(start).tzinfo)
    return int((finish - datetime.fromisoformat(start)).total_seconds() * 1000)


def batches(heart, project):
    found = batch.read_journal(heart.brain(project), BATCHES)
    out = []
    for entry in found:
        analysis = analyze(entry)
        out.append({"at": entry.get("at"), "status": entry.get("status"), "summary": entry.get("summary"),
                    "inputs": [f"{item.get('type')} {_ref(item)}".strip() for item in entry.get("inputs") or []],
                    "costUsd": entry.get("costUsd"), "numTurns": entry.get("numTurns"),
                    "headline": headline(analysis), **analysis})
    return out


def explain(service, heart, project, now=None):
    now = time.time() if now is None else now
    with service.registry_lock:  # ensure_active toku srdce smí zapisovat do registru
        caps = safe(lambda: caps_settings.read(service.db))
        model = safe(lambda: model_settings.read(service.db))
    limits = caps if "error" not in caps else {"per_hour": 6}
    runs = safe(lambda: pipeline(service, project))
    view = {"project": project, "at": iso(now), "now": safe(lambda: waiting(heart, project, limits, now, runs)),
            "queue": safe(lambda: queue(heart, project, now)), "pipeline": runs,
            "batches": safe(lambda: batches(heart, project)), "caps": caps,
            "model": model}
    view["stops"] = safe(lambda: stops(service, heart, project, view))
    return view


def text(view):
    """Totéž v řádcích pro agenta (`?format=text`): stav, fronta, zarážky, tok a rozpad dávek."""
    def part(value, render):
        return [f"  (nedostupné: {value['error']})"] if isinstance(value, dict) and "error" in value else render(value)
    lines = [f"SRDCE {view['project']} · {view['at']}", "TEĎ: " + (view["now"].get("sentence") or view["now"].get("error", ""))]
    lines.append("FRONTA:")
    lines += part(view["queue"], lambda items: [f"  {i['type']} {i['ref']} ({i['workspace']}) splatné za {i['dueInS']} s"
                                                 for i in items] or ["  prázdná"])
    lines.append("ZARÁŽKY (! = právě platí):")
    lines += part(view["stops"], lambda items: [f"  {'!' if s['active'] else '·'} {s['label']}: {s['detail']} → {s['lever']}"
                                                 for s in items])
    lines.append("TOK SRDCE (poslední běhy):")
    lines += part(view["pipeline"], lambda runs: [f"  {r['at'][:19]} {r['status']}: " + " → ".join(
        f"{n['label']} {round((n['ms'] or 0) / 1000)} s" for n in r["nodes"]) for r in runs])
    lines.append("DÁVKY (kam šel čas):")
    lines += part(view["batches"], lambda items: [f"  {b['at']} {b['headline']} Shrnutí: {b.get('summary') or '—'}"
                                                   for b in items])
    caps = view["caps"]
    if "error" not in caps:
        lines.append(f"STROPY: {caps['per_hour']} dávek/h, {caps['per_project']} běh na projekt, "
                     f"spánek po limitu {caps['rate_sleep_seconds']} s (mění člověk ve Velínu → Srdce).")
    return "\n".join(lines)
