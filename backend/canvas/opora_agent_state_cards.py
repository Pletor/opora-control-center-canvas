"""Per-card loop stage for the agent-state document (docs/oporahub-agent-state.md, "Etapa karty").

The Editor canvas shows one small badge per card node; it reads the same agent-state poll as the
OporaHub overview, so the card's position in the loop is derived here from facts the document
already collected (process cards, latest executions, claims, PR links, review gates). Pure and
deterministic: the same facts and clock give the same list. A card is placed at the furthest stage
it has reached; the first matching rule below wins.
"""
from backend.canvas import opora_agent_state_review_gates as review_gates
from backend.canvas import opora_agent_state_rules as rules

_GATE_HEALTH = {"blocked": "blocking", "pending": "waiting", "ready": "ok"}


def _entry(node, stage, health, reason, execution=None):
    return {"nodeId": node, "stage": stage, "health": health, "reason": reason, "executionId": execution}


def _gate(gate, node, execution):
    status = gate["reviewGate"]["status"]
    fallback = {"blocked": "review_gate_blocked", "pending": "review_gate_pending"}.get(status, "review_gate_ready")
    reason = review_gates.stage_reason([gate], status, fallback) if status in ("blocked", "pending") else fallback
    return _entry(node, "review", _GATE_HEALTH.get(status, "waiting"), reason, execution)


def dead_run(latest, claim, now):
    """A run past its deadline without results whose card already offers a claim again (process sync saw no
    active lease): it is handed back, so the card shows the claim stage, not `lease_past_deadline`."""
    return bool(claim) and latest["deadline"] <= now and not latest["results"]


def historical(latest, claim, accepted):
    """A result whose card slice changed since its claim (`stale_evidence`) on a card that offers a claim again
    (process sync let the card fall through to readiness): it is history, so the card shows the claim stage."""
    return bool(claim) and bool(latest["results"]) and rules.stale_evidence(latest, accepted)


def evidence_results(reported, cards, offered, accepted):
    """Results counted by the `evidence` stage: open cards only, historical results (see `historical`) are left out
    so the stage agrees with the per-card view. `offered` maps nodeId to the claim offer."""
    return [item for item in rules.open_results(reported, cards)
            if not historical(item, offered.get(item["nodeId"]), accepted)]


def card_stage(card, accepted, latest, claim, link, gate, now):
    """Stage of one card; `latest`, `claim`, `link` and `gate` are None when the card has none."""
    node = card["nodeId"]
    execution = latest["id"] if latest else None
    if card.get("doneConfirmed"):
        return _entry(node, "plan_writeback", "ok", "card_closed", execution)
    if link and link.get("state") == "merged":
        if link.get("awaitingHumanClose"):
            return _entry(node, "merge", "waiting", "awaiting_human_close", link["executionId"])
        if link.get("planWrittenBack") is True:
            return _entry(node, "plan_writeback", "ok", "plan_written_back", link["executionId"])
        return _entry(node, "plan_writeback", "waiting", "merged_without_plan_writeback", link["executionId"])
    if link and link.get("state") == "open":
        if gate:
            return _gate(gate, node, link["executionId"])
        return _entry(node, "pull_request", "waiting", "pull_requests_open", link["executionId"])
    if latest and latest["state"] == "running" and not dead_run(latest, claim, now):
        if latest["deadline"] <= now:
            return _entry(node, "work", "blocking", "lease_past_deadline", execution)
        return _entry(node, "work", "ok", "runs_active", execution)
    if latest and latest["results"] and not historical(latest, claim, accepted):
        if rules.stale_evidence(latest, accepted):
            return _entry(node, "evidence", "waiting", "stale_evidence", execution)
        return _entry(node, "review", "waiting", "human_review_required", execution)
    if claim:
        if claim["status"] == "ready":
            return _entry(node, "claim", "ok", "cards_ready")
        return _entry(node, "claim", "blocking", claim["blockReason"])
    if accepted is None:
        return _entry(node, "plan", "blocking", "no_accepted_baseline")
    return _entry(node, "plan", "ok", "card_in_plan")


def pull_request(card, link, latest):
    """`{number, state}` of the card's PR for the badge on the card, or None. A closed card shows none; a PR
    closed without merge only while it belongs to the card's latest run (a new run is a new attempt).
    `number` is None for a local merge without GitHub."""
    if not link or card.get("doneConfirmed"):
        return None
    if link["state"] == "closed" and latest and latest["id"] != link["executionId"]:
        return None
    number = link.get("number")
    return {"number": number if type(number) is int else None, "state": link["state"]}


def project(cards, accepted, latest, claims, linked, reviewing, now):
    """One entry per card of the workspace, sorted by nodeId; `page` then orders and caps them."""
    runs = {item["nodeId"]: item for item in latest}
    offered = {item["nodeId"]: item for item in claims}
    links, gates = {}, {}
    for item in linked or []:
        if item.get("cardId"):
            current = links.get(item["cardId"])
            # An open PR is the live one; a merged one beats a later attempt closed without merge (IDLE-002: a
            # duplicate PR closed after the card's work merged must not pull the card back into review);
            # otherwise keep the newest link reported.
            state, held = item.get("state"), current.get("state") if current else None
            if current is None or state == "open" or (held != "open" and (state == "merged" or held != "merged")):
                links[item["cardId"]] = item
    for gate in (reviewing or {}).get("gates", []):
        gates[gate["executionId"]] = gate
    result = []
    for node in sorted(cards):
        link = links.get(node)
        gate = gates.get(link["executionId"]) if link else None
        entry = card_stage(cards[node], accepted, runs.get(node), offered.get(node), link, gate, now)
        pr = pull_request(cards[node], link, runs.get(node))
        result.append({**entry, "pr": pr} if pr else entry)
    return result


CARD_LIMIT = 100
_CLOSED = {"card_closed", "plan_written_back"}


def relevance(entry):
    """0 in flight (run, evidence, review, PR, merge), 1 ready, 2 blocked claim, 3 in plan, 4 closed."""
    if entry["reason"] in _CLOSED:
        return 4
    if entry["stage"] == "plan":
        return 3
    if entry["stage"] == "claim":
        return 1 if entry["reason"] == "cards_ready" else 2
    return 0


def page(entries, offset=0, limit=CARD_LIMIT):
    """`(cards, total, nextOffset)`: by relevance then nodeId, so a cap drops closed cards first."""
    ordered = sorted(entries, key=lambda entry: (relevance(entry), entry["nodeId"]))
    window = ordered[offset:offset + limit]
    following = offset + len(window)
    return window, len(ordered), following if following < len(ordered) else None
