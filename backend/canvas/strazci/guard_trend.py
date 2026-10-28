"""Strážce `trend` (`docs/strazci.md` §4): každých 900 s vzorek souhrnných čísel projektu do `guard_trend`.

Čísla se nepočítají znovu, berou se z jediných zdrojů:
- `holes`, `holes.agent`: díry mapy jako `mapGaps` v agent-state (`opora_agent_state_map_gaps.all_items`, bez stropu);
  `holes.agent` = díry s `owner: "agent"`.
- `journeys.verified`, `journeys.total`: odvozené cesty přijaté architektury a jejich `lastRun` (`journey_runs`);
  ověřená = poslední doklad prošel a není zastaralý.
- `cards.done`: karty s `done.confirmed` ve stavu plochy (`plan_lens_cards.done_ids`) ve všech prostorech projektu.
- `cards.building`: karty, jejichž poslední vydaná etapa (`opora_event_card_state`) je rozpracovaná (běh, doklad,
  review, PR, merge = `opora_agent_state_cards.relevance` 0) a nejsou uzavřené.
- `work.stalled`: otevřené nálezy strážce `prace` (`guard_findings`).
- `proposals.waiting`: návrhy čekající na člověka jako u strážce `pravda` (`guard_pravda.read_proposals`).
Strážce nehlásí nálezy (vrací prázdný seznam); vzorky starší 90 dní se při zápisu mažou.
"""
import json

from backend.canvas import opora_agent_state_map_gaps as map_gaps
from backend.canvas.opora_agent_state_cards import relevance
from backend.canvas.plan_lens_cards import done_ids
from backend.canvas.strazci import guard_pravda
from backend.canvas.strazci.findings import at_of
from backend.canvas.strazci.guard_mapa import workspaces_of
from backend.canvas.strazci.registry import Guard
from backend.project.architecture.journey_runs import last_runs, latest_journey_runs
from backend.project.architecture.journeys import derive_journeys
from backend.project.architecture.work_status import architecture_graph
from database.repositories.guard_findings import GuardFindings
from database.repositories.guard_trend import GuardTrend

METRICS = ("holes", "holes.agent", "journeys.verified", "journeys.total", "cards.done", "cards.building",
           "work.stalled", "proposals.waiting")
RETENTION_DAYS = 90


def journey_counts(journeys, last):
    """(ověřené, všechny) cesty; ověřená = `lastRun` prošel a není zastaralý (čistá funkce)."""
    verified = 0
    for journey in journeys:
        run = last.get((journey["applicationId"], journey["id"]))
        verified += bool(run and run["passed"] and not run["stale"])
    return verified, len(journeys)


def building_count(stages, closed):
    """Rozpracované karty z `[(nodeId, stage, reason)]` posledních etap, mimo uzavřené (čistá funkce)."""
    return sum(1 for node, stage, reason in stages
               if node not in closed and relevance({"stage": stage, "reason": reason}) == 0)


def card_counts(service, project):
    done = building = 0
    with service.reading(project):
        db = service.db_for(project)
        for workspace in workspaces_of(service, project):
            row = db.execute("SELECT state FROM desktop_v3_state WHERE project_id=? AND workspace_id=?",
                             (project, workspace)).fetchone()
            closed = done_ids(json.loads(row[0])) if row else set()
            stages = db.execute("SELECT node_id, stage, reason FROM opora_event_card_state WHERE project_id=?"
                                " AND workspace_id=?", (project, workspace)).fetchall()
            done += len(closed)
            building += building_count(stages, closed)
    return done, building


def stalled_count(service, project):
    with service.reading(project):
        counts = GuardFindings(service.db_for(project), project).counts()
    return sum(counts.get("prace", {}).values())


def sample(service, project):
    """`{metric: value}` pro všech osm čísel trendu."""
    holes = map_gaps.all_items(service, project)
    graph = architecture_graph(service, project)
    journeys = derive_journeys(graph)
    verified, total = journey_counts(journeys, last_runs(graph, latest_journey_runs(service, project)) if journeys else {})
    done, building = card_counts(service, project)
    return {"holes": len(holes), "holes.agent": sum(item["owner"] == "agent" for item in holes),
            "journeys.verified": verified, "journeys.total": total, "cards.done": done, "cards.building": building,
            "work.stalled": stalled_count(service, project),
            "proposals.waiting": len(guard_pravda.read_proposals(service, project))}


def record(service, project, values, now):
    """Zapíše vzorek a smaže vzorky starší než retence (jedna transakce pod zámkem projektu)."""
    db = service.db_for(project)
    with service.lock_for(project), db:
        db.execute("BEGIN IMMEDIATE")
        store = GuardTrend(db, project)
        store.insert(at_of(now), values)
        store.prune(at_of(now - RETENTION_DAYS * 86400))


def run(ctx):
    record(ctx.service, ctx.project, sample(ctx.service, ctx.project), ctx.now)
    return []


GUARD = Guard(id="trend", label="Trend", every_s=900, run=run)
