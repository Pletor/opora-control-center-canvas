"""Lease of each card for the agent-state document (docs/oporahub-agent-state.md, "Etapa karty").

`cards[].lease` is `{holder, expiresAt, epoch}` of the card's latest execution while it is
`running` and its deadline (lease or fixed budget end) is still in the future; otherwise `null`.
The Editor card face shows the holder and a countdown; it never guesses a lease from events.
Pure over the latest executions the document already collected under the project locks.
"""
from datetime import UTC, datetime


def _iso(stamp):
    return datetime.fromtimestamp(stamp, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def leases(latest, now):
    """`{nodeId: lease}` for latest executions that still hold a live lease."""
    result = {}
    for item in latest:
        if item["state"] == "running" and item.get("deadline") is not None and item["deadline"] > now:
            result[item["nodeId"]] = {"holder": item.get("owner") or None, "expiresAt": _iso(item["deadline"]),
                                      "epoch": item.get("epoch")}
    return result


def attach(cards, latest, now):
    """Every `cards[]` entry gains `lease` (or `null`)."""
    live = leases(latest, now)
    return [{**entry, "lease": live.get(entry["nodeId"])} for entry in cards]
