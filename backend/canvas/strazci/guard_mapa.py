"""Strážce `mapa` (`docs/strazci.md` §4): kontrola mapy nad přijatou architekturou, jen při změně hlavy.

Hlava = otisk přijatého grafu (`architecture_graph`) a nejvyšší `seq` dokladů cest (`journey_runs`); doklad
cesty mění `journey.unverified`, proto patří do hlavy. Beze změny strážce přeskočí (`None`). Jinak
`check_map(..., locate=True)` a každý nález kontroly mapy = nález strážce: `severity warn`, `page.no-goal`
a `journey.broken` `block` (pro člověka). `nodeId` nálezu je místo řešení (`solverId`), takže nález hrany
nebo cesty míří na kartu, která ho vyřeší; hrana zůstává v `data.edgeId`.

Klíč: `map:<pravidlo>:<cíl>`; cíl je karta, hrana nebo cesta. Pravidla s více nálezy na stejný cíl dostanou
rozlišení: `section.unrealized` id sekce ze zprávy, `journey.unrealized` a `journey.via-unknown` krátký otisk
zprávy (zpráva jmenuje přechod nebo krok, takže je stabilní, dokud se nález nezmění).
"""
import hashlib
import json
import re

from backend.canvas.graph import digest
from backend.canvas.strazci.registry import Guard
from backend.project.architecture.journey_runs import latest_journey_runs
from backend.project.architecture.map_check import check_map
from backend.project.architecture.work_status import architecture_graph

BLOCK_RULES = frozenset({"page.no-goal", "journey.broken"})
PER_MESSAGE = frozenset({"journey.unrealized", "journey.via-unknown"})
SECTION = re.compile(r"^Sekce (\S+) ")
TARGETS = ("nodeId", "edgeId", "journeyId")


def workspace_of(service, project):
    """Prostor přijaté architektury: `main` u projektu z Gitu, jinak `draft` (jako `architecture_graph`)."""
    if project == "draft":
        return "draft"
    return "main" if service.project_hub.settings(project)["project"]["sourceKind"] == "git" else "draft"


def runs_head(service, project):
    with service.reading(project):
        row = service.db_for(project).execute(
            "SELECT COALESCE(MAX(seq), 0) FROM journey_runs WHERE project_id=?", (project,)).fetchone()
    return row[0]


def finding_key(item):
    rule = item["rule"]
    target = next((item[name] for name in TARGETS if item.get(name) is not None), "-")
    key = f"map:{rule}:{target}"
    if rule == "section.unrealized":
        match = SECTION.match(item["message"])
        key += ":" + (match.group(1) if match else hashlib.sha1(item["message"].encode()).hexdigest()[:10])
    elif rule in PER_MESSAGE:
        key += ":" + hashlib.sha1(item["message"].encode()).hexdigest()[:10]
    return key


def to_findings(report, workspace):
    """Nálezy kontroly mapy → nálezy strážce (čistá funkce)."""
    result = []
    for item in report["findings"]:
        finding = {"key": finding_key(item), "rule": item["rule"], "message": item["message"],
                   "severity": "block" if item["rule"] in BLOCK_RULES else "warn", "workspaceId": workspace}
        node = item.get("nodeId") or item.get("solverId")
        if node is not None:
            finding["nodeId"] = node
        if item.get("journeyId") is not None:
            finding["journeyId"] = item["journeyId"]
        if item.get("edgeId") is not None:
            finding["data"] = {"edgeId": item["edgeId"]}
        result.append(finding)
    return result


def run(ctx):
    graph = architecture_graph(ctx.service, ctx.project)
    head = json.dumps([digest(graph), runs_head(ctx.service, ctx.project)])
    if ctx.memo.get("head") == head:
        return None
    report = check_map(graph, latest_journey_runs(ctx.service, ctx.project), locate=True)
    ctx.memo["head"] = head
    return to_findings(report, workspace_of(ctx.service, ctx.project))


GUARD = Guard(id="mapa", label="Mapa architektury", every_s=60, run=run)
