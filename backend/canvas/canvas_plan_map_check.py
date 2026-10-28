"""Kontrola mapy nad dávkou plánu (`docs/architektura-pro-agenty.md` §5.3).

Dávka díry neodmítá: `map_warnings` porovná kontrolu mapy grafu před dávkou a po ní a vrátí jen nálezy, které dávka
otevřela, jako varování `{rule, message, nodeId?, place?}` (`place` = `solverId`, místo řešení). Identita nálezu je
pravidlo, cíl (`nodeId` / `edgeId` / `journeyId`), místo a zpráva: jedna karta nese víc nálezů téhož pravidla.
Klíč počítá `map_check.finding_key`, tentýž jako kontrola mapy přes worktree.
"""

from backend.project.architecture.map_check import check_map, finding_key

WARNINGS_LIMIT = 20


def _warning(finding):
    return {"rule": finding["rule"], "message": finding["message"],
            **({"nodeId": finding["nodeId"]} if finding.get("nodeId") else {}),
            **({"place": finding["solverId"]} if finding.get("solverId") else {})}


def map_warnings(before, after):
    """Nové nálezy kontroly mapy grafu `after` proti `before` (`{nodes, edges}`), v pořadí kontroly, nejvýš 20."""
    known = {finding_key(finding) for finding in check_map(before, locate=True)["findings"]}
    fresh = [finding for finding in check_map(after, locate=True)["findings"] if finding_key(finding) not in known]
    return [_warning(finding) for finding in fresh[:WARNINGS_LIMIT]]
