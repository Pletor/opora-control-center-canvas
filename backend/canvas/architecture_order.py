"""Zápis srdce do architektury projektu (docs/navrhy/2026-10-31-poradi-karty.md §4): jen pořadí stránek.

Pořadí obrazovek platí pro celý projekt, proto ho srdce mění přímo v architektuře
(`POST /api/project-architecture`). Smí to jen při plné autonomii projektu a jen tak, že se u existujících uzlů
změní pole `order`; uzly, jejich pořadí v seznamu, ostatní pole a vazby zůstanou, jak jsou. Člověk zapisuje dál
beze změny. Funkce jsou čisté, rozhodnutí o autonomii dodá routa.
"""
from backend.canvas.payload_errors import NextStep

HINT = ("Srdce v architektuře mění jen pořadí stránek a sektorů (order, opora_heart.py order); ostatní změny "
        "architektury dělá člověk v UI.")


class HeartArchitectureRefused(NextStep):
    """Zápis srdce do architektury mimo povolený rozsah: 403 (bez plné autonomie) nebo 422 (mění víc než `order`)."""

    def __init__(self, message, *, code, status):
        super().__init__(message, code=code, hint=HINT)
        self.status = status


def require_autonomy(full):
    if not full:
        raise HeartArchitectureRefused("Srdce zapisuje do architektury jen v projektu s plnou autonomií.",
                                       code="heart_architecture_autonomy", status=403)


def _without_order(node):
    return {key: value for key, value in node.items() if key != "order"}


def other_changes(old, new):
    """Rozdíly architektury mimo pole `order` existujících uzlů; prázdný seznam = mění se jen pořadí."""
    changes = []
    if [node["id"] for node in old["nodes"]] != [node["id"] for node in new["nodes"]]:
        changes.append("uzly")
    else:
        changes += [node["id"] for node, before in zip(new["nodes"], old["nodes"], strict=True)
                    if _without_order(node) != _without_order(before)]
    if old["edges"] != new["edges"]:
        changes.append("vazby")
    return changes


def require_order_only(old, new):
    changes = other_changes(old, new)
    if changes:
        raise HeartArchitectureRefused("Srdce mění v architektuře jen pole order, ne: " + ", ".join(changes[:10]) + ".",
                                       code="heart_architecture_scope", status=422)
