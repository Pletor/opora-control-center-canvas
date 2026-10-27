"""Brána uzavření karty na cestě zákazníka (`docs/brana-cesty.md` §5).

Čistá funkce nad stejným grafem jako `journeys.derive_journeys` a nad posledními doklady přehrání (`journey_runs`),
bez modelu a bez I/O. Karta leží na cestě, když její nejbližší stránka (nebo ona sama, je-li stránkou) je stránkou
některého kroku cesty, která není `broken`. Taková karta se neuzavře, dokud každá její cesta nemá `lastRun`
s `passed && !stale`.

- `journeys_blocking(graph, node_id, runs)` → `[{journeyId, applicationId, name, reason}]` cest, které uzavření
  brání, v pořadí `derive_journeys`. Karta mimo cesty (nebo mimo graf) = prázdný seznam, chování beze změny.
- `reason`, jeden v pořadí jako `journey.unverified` v kontrole mapy (§4): „chybí ověření“ (cesta bez dokladu) →
  „zastaralé“ (`planDigest` dokladu ≠ digest aktuálního plánu) → „neprošel přechod s2 → s3“ (první neúspěšný
  segment dokladu) → „nepokrývá všechny přechody“ (neúplný doklad bez neúspěšného segmentu).
- `blocking_by_node(graph, runs, node_ids)` totéž pro více karet najednou (cesty se odvodí jednou).
- `refusal(blocking)` = text odmítnutí „cesta Kampaň Pěstování: chybí ověření; …“.
- `stale` se počítá nad grafem, který volající předá (u uzavření karty graf jejího pracovního prostoru).
"""

from backend.canvas.site_metadata import nearest_page
from backend.project.architecture.journey_runs import last_runs
from backend.project.architecture.journeys import derive_journeys


def _page_of(by_id, node_id):
    node = by_id.get(node_id)
    if node is None:
        return None
    if (node.get("site") or {}).get("kind") == "page":
        return node_id
    page = nearest_page(by_id, node_id)
    return page["id"] if page is not None else None


def _reason(run):
    if run is None:
        return "chybí ověření"
    if run["stale"]:
        return "zastaralé"
    first = run.get("firstFailure")
    if first:
        return f"neprošel přechod {first['from']} → {first['to']}"
    return None if run["passed"] else "nepokrývá všechny přechody"


def blocking_by_node(graph, runs, node_ids):
    """{nodeId: [blokující cesta, …]} jen pro karty, kterým nějaká cesta uzavření brání."""
    by_id = {node["id"]: node for node in graph.get("nodes") or []}
    pages = {node_id: page for node_id in node_ids if (page := _page_of(by_id, node_id)) is not None}
    if not pages:
        return {}
    journeys = [item for item in derive_journeys(graph) if "broken" not in item]
    if not journeys:
        return {}
    verified = last_runs(graph, runs or {})
    blocking = []
    for journey in journeys:
        reason = _reason(verified.get((journey["applicationId"], journey["id"])))
        if reason is not None:
            blocking.append(({step["page"] for step in journey["steps"]},
                             {"journeyId": journey["id"], "applicationId": journey["applicationId"],
                              "name": journey["name"], "reason": reason}))
    result = {}
    for node_id, page in pages.items():
        found = [dict(item) for steps, item in blocking if page in steps]
        if found:
            result[node_id] = found
    return result


def journeys_blocking(graph, node_id, runs):
    """Cesty, které brání uzavření karty `node_id`; prázdný seznam = brána cesty je splněná nebo se karty netýká."""
    return blocking_by_node(graph, runs, [node_id]).get(node_id, [])


def refusal(blocking):
    """Text důvodu odmítnutí: každá blokující cesta jménem a důvodem."""
    return "; ".join(f"cesta {item['name']}: {item['reason']}" for item in blocking)
