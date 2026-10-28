"""Připravené příkazy v agent-state (docs/navrhy/2026-10-28-zefektivneni-opory.md §4, §5 „Připravené příkazy“).

Každá `ready` akce nese `command`: hotový řádek klienta skillu, aby agent nehádal tvar volání.
Karta (`claim`) se bere složeným `start --node`; akce, které klient provádí z `method/path/preconditions`,
jdou přes `act --action-id`. Akce, kterou klient sám neprovádí, má `command: null` (tělo viz hub-api.md).
Blokovaná akce `command` nedostane (beze změny tvaru). `--project/--workspace` doplní agent jako u každého volání.
"""

ACT_VERBS = frozenset({"propose_graph", "accept_baseline", "accept", "rebase", "verification.fix", "close_card",
                       "review", "review.claim"})


def command(action):
    """Řádek `opora_hub.py …` pro ready akci, jinak None."""
    if action.get("status") != "ready":
        return None
    if action.get("verb") == "claim" and action.get("targetId"):
        return f"opora_hub.py start --node {action['targetId']}"
    if action.get("verb") in ACT_VERBS:
        return f"opora_hub.py act --action-id {action['id']}"
    return None


def attach(actions):
    """Ke každé ready akci doplní `command`; ostatní akce vrací beze změny."""
    return [{**action, "command": command(action)} if action.get("status") == "ready" else action
            for action in actions]
