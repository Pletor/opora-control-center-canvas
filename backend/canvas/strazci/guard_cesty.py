"""Strážce `cesty` (`docs/strazci.md` §4): `lastRun` cest zákazníka a brána cest u karet čekajících na uzavření.

Jen čte (přijatý graf, poslední doklady `journey_runs`, odkazy běhů na PR) a hlásí; cesty nepřehrává.
Pravidla (cesta bez dokladu tu není: chybějící ověření hlásí kontrola mapy jako `journey.unverified`):
- `journey.stale` (warn): poslední doklad cesty je zastaralý, `planDigest` se liší od aktuálního plánu
  (mapa se od běhu změnila). Klíč `journey:stale:<aplikace>:<cesta>`, `nodeId` = první stránka cesty.
- `journey.failed` (warn): poslední čerstvý doklad neprošel (aspoň jeden segment `ok: false`). Klíč
  `journey:failed:<aplikace>:<cesta>`, `nodeId` = stránka cíle prvního neúspěšného přechodu.
- `journey.blocks-card` (block): karta po merge čeká na uzavření člověkem (`awaitingHumanClose`), ale brání mu brána
  `journeys` jediné definice hotovo (`opora_card_done.journeys_by_card`, stejný výpočet jako agent-state a uzavření).
  Klíč `journey:blocks-card:<prostor>:<karta>`, `nodeId` = karta, `journeyId` = první blokující cesta.
"""
from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas import opora_card_done as card_done
from backend.canvas.site_metadata import JOURNEY_FROM_NAV
from backend.canvas.strazci.guard_mapa import workspace_of, workspaces_of
from backend.canvas.strazci.registry import Guard
from backend.project.architecture.journey_runs import last_runs, latest_journey_runs
from backend.project.architecture.journeys import derive_journeys
from backend.project.architecture.work_status import architecture_graph


def _page(journey, step_id=None):
    """Stránka kroku `step_id`, bez něj první skutečná stránka cesty (menu `nav` stránkou není)."""
    for step in journey["steps"]:
        if (step_id is None or step["id"] == step_id) and step.get("page") not in (None, JOURNEY_FROM_NAV):
            return step["page"]
    return None


def journey_findings(journeys, last, workspace):
    """Čistá pravidla `journey.stale` a `journey.failed` nad odvozenými cestami a jejich `lastRun`."""
    findings = []
    for journey in journeys:
        if "broken" in journey:
            continue
        run = last.get((journey["applicationId"], journey["id"]))
        if run is None:
            continue
        ident = f"{journey['applicationId']}:{journey['id']}"
        base = {"journeyId": journey["id"], "workspaceId": workspace, "data": {"applicationId": journey["applicationId"],
                                                                               "at": run["at"]}}
        if run["stale"]:
            node = _page(journey)
            findings.append({**base, "key": f"journey:stale:{ident}", "rule": "journey.stale", "severity": "warn",
                             "message": f"Doklad cesty {journey['name']} je zastaralý: mapa se od běhu změnila.",
                             **({"nodeId": node} if node else {})})
        elif not run["passed"] and run["failed"]:
            first = run.get("firstFailure") or {}
            node = _page(journey, first.get("to")) or _page(journey)
            reason = f" ({first['reason']})" if first.get("reason") else ""
            findings.append({**base, "key": f"journey:failed:{ident}", "rule": "journey.failed", "severity": "warn",
                             "message": f"Cesta {journey['name']} neprošla přechodem {first.get('from')} → "
                                        f"{first.get('to')}{reason}.",
                             **({"nodeId": node} if node else {})})
    return findings


def blocked_findings(blocked):
    """`journey.blocks-card` z `[{workspaceId, nodeId, journeys: [{journeyId, name, reason}]}]` (čistá funkce)."""
    findings = []
    for item in blocked:
        journeys = item["journeys"]
        names = "; ".join(f"{journey['name']}: {journey['reason']}" for journey in journeys)
        findings.append({"key": f"journey:blocks-card:{item['workspaceId']}:{item['nodeId']}",
                         "rule": "journey.blocks-card", "severity": "block", "nodeId": item["nodeId"],
                         "workspaceId": item["workspaceId"], "journeyId": journeys[0]["journeyId"],
                         "message": f"Karta čeká na uzavření, ale brání jí cesta zákazníka ({names}).",
                         "data": {"journeys": [journey["journeyId"] for journey in journeys]}})
    return findings


def read_blocked(service, project):
    """Karty čekající na uzavření člověkem, kterým brání brána cest, ve všech prostorech projektu."""
    result = []
    for workspace in workspaces_of(service, project):
        linked = pulls.read(service, project, workspace) or []
        waiting = sorted({item["cardId"] for item in linked if item.get("awaitingHumanClose")})
        if not waiting:
            continue
        blocking = card_done.journeys_by_card(service, project, workspace, waiting)
        result += [{"workspaceId": workspace, "nodeId": node, "journeys": blocking[node]}
                   for node in waiting if blocking.get(node)]
    return result


def run(ctx):
    graph = architecture_graph(ctx.service, ctx.project)
    journeys = derive_journeys(graph)
    last = last_runs(graph, latest_journey_runs(ctx.service, ctx.project)) if journeys else {}
    return [*journey_findings(journeys, last, workspace_of(ctx.service, ctx.project)),
            *blocked_findings(read_blocked(ctx.service, ctx.project))]


GUARD = Guard(id="cesty", label="Cesty zákazníka", every_s=120, run=run)
