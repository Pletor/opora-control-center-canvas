"""Board podle plánu a fronty odpovědnosti (docs/navrhy/2026-11-06-linie-rebrand.md §6, §7 bod 4 L7d).

Seskupení je jiný pohled na týž snímek: `group(found)` přeskládá hotový výsledek `board()` bez nového čtení gitu
i ticketů – stejný `snapshot.id`, stejné kuličky (`id`, `mark`, pole), jen jiné `rowId`. Řádky: směr (plátno 2,
`type: dir`), pod ním plán (plátno 3, `type: plan`, `parent` = směr); neověřená vazba (`card_missing`,
`source_unavailable`) leží na `plan:unverified` „vazba neověřena“, jen `none` na `plan:none` „bez plánu“.
`remember` / `recall` drží posledních `KEEP` snímků v paměti, aby přepnutí seskupení (`?snapshot=<id>`) nečetlo znovu.

Fronty (`queues`) počítá `queues()` nad týmiž kuličkami a týmž grafem jako board.
"""
from collections import OrderedDict

KEEP = 8  # snímků v paměti; přepnutí seskupení přichází hned po načtení boardu
SNAPSHOTS = OrderedDict()  # snapshot.id → (project, workspace, výsledek board, jména uzlů grafu)
QUEUES = {"ticketsTodo": {"todo"}, "humanDecisions": {"pending", "stale", "stale_plan", "accepted", "blocked"},
          "officeTasks": {"wip", "failed", "nocheck"}, "gitQueue": {"checking", "accepted"}}


def ball_queues(ball):
    """Fronty, ve kterých kulička je (může být ve více); otevřený PR = fronta Git."""
    key = ball["summary"]["key"]
    found = [name for name, keys in QUEUES.items() if key in keys]
    if "gitQueue" not in found and (ball.get("pr") or {}).get("state") == "OPEN":
        found.append("gitQueue")
    return found


def queues(balls, graph, cards_with_ticket):
    """Počty front; `plansWaiting` = karty plánu (`kind: node`) bez vydaného ticketu, None když graf nejde přečíst."""
    counts = {name: sum(name in ball["queues"] for ball in balls) for name in QUEUES}
    waiting = None if graph is None else sum(
        1 for node in graph.values() if node.get("kind") == "node" and node["id"] not in cards_with_ticket)
    return {"plansWaiting": waiting, **counts}


def remember(project, workspace, found, graph):
    SNAPSHOTS[found["snapshot"]["id"]] = (project, workspace, found, {
        key: node.get("name") or key for key, node in (graph or {}).items()})
    while len(SNAPSHOTS) > KEEP:
        SNAPSHOTS.popitem(last=False)


def recall(project, workspace, snapshot_id):
    """`(výsledek, jména)` uloženého snímku téhož projektu a prostoru, jinak None."""
    kept = SNAPSHOTS.get(snapshot_id)
    return kept[2:] if kept and kept[:2] == (project, workspace) else None


def _row_of(plan):
    if plan["state"] in ("linked", "ambiguous"):
        return "plan:" + plan["planCardId"]
    return "plan:none" if plan["state"] == "none" else "plan:unverified"


def group(found, names):
    """Výsledek `board()` seskupený podle plánu; vstup se nemění."""
    rows, parents = {}, {}
    for ball in found["balls"]:
        plan = ball["plan"]
        if plan["state"] in ("linked", "ambiguous"):
            parents.setdefault(plan["planCardId"], plan["directionCardId"])
    for direction in dict.fromkeys(d for d in parents.values() if d):
        rows["dir:" + direction] = {"id": "dir:" + direction, "type": "dir", "name": names.get(direction, direction),
                                    "cardId": direction, "parent": None, "depth": 0}
        for card, above in parents.items():
            if above == direction:
                rows["plan:" + card] = {"id": "plan:" + card, "type": "plan", "name": names.get(card, card),
                                        "cardId": card, "parent": "dir:" + direction, "depth": 1}
    for card, above in parents.items():
        if not above:
            rows["plan:" + card] = {"id": "plan:" + card, "type": "plan", "name": names.get(card, card), "cardId": card,
                                    "parent": None, "depth": 0}
    balls = [{**ball, "rowId": _row_of(ball["plan"])} for ball in found["balls"]]
    for row_id, name in (("plan:unverified", "vazba neověřena"), ("plan:none", "bez plánu")):
        if any(ball["rowId"] == row_id for ball in balls):
            rows[row_id] = {"id": row_id, "type": "plan", "name": name, "cardId": None, "parent": None, "depth": 0}
    return {**found, "group": "plan", "rows": list(rows.values()), "balls": balls}
