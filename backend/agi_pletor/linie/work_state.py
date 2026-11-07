"""Stav kuličky Linie ve starém tvaru `{state, label, next}`: tenký alias nad `evaluate` (L7 §2a), bez gitu a modelu.

`state` nese dnešní jména, která čte frontend (`open`, `awaiting_checks`, `accepted_unmerged`, …), dokud L7b nepřejde
na `summary.key`; `label` a `next` jsou z téhož vyhodnocení. `checks_for` a `green` dál používá `merge.py`.
"""
from backend.agi_pletor.linie.evaluate import evaluate

LEGACY = {"blocked": "blocked", "merged": "merged", "deferred": "deferred", "todo": "open", "wip": "open",
          "failed": "awaiting_checks", "nocheck": "awaiting_checks", "checking": "awaiting_checks", "stale": "stale",
          "stale_plan": "stale",
          "pending": "open", "accepted": "accepted_unmerged"}


def checks_for(work, sha):
    """Kontroly k jednomu SHA; starší kontroly k jinému SHA zůstávají jen v historii pole."""
    return [check for check in work.get("checks") or [] if check.get("sha") == sha]


def green(work):
    """Všechny kontroly pro headSha zelené (a aspoň jedna)."""
    found = checks_for(work, work.get("headSha"))
    return bool(found) and all(check.get("status") == "green" for check in found)


def state(work, after_merge=None):
    found = evaluate(work, after_merge)
    return {"state": LEGACY[found["key"]], "label": found["text"], "next": found["next"]}
