"""The single definition of done of an OporaHub card (night contract §3).

done = every accepted plan step reported `done` + card acceptance evidenced against the
current accepted spec + review gate `ready` + PR merged + plan written back + a human
`close_card`. `card_done_state` is pure; `closure_gate` loads the facts for the human close
precondition and replaces the legacy evidence/checks/pipeline closure gate for every card
whose accepted spec has plan steps (cards without steps keep the legacy path readable).
docs/oporahub-plan-steps.md.
"""
REQUIREMENTS = ("steps", "card_acceptance", "gate_ready", "merged", "plan_written_back", "human_close")


def card_done_state(card):
    """`card` = {steps: {total, done}, acceptanceEvidence, gate: {status}|None, gateMode, merged,
    planWrittenBack, closed} → {done, missing: [requirement, ...] in contract order, gate}.

    `gateMode` "review" (default): gate_ready = the OporaHub review gate is `ready`. "external"
    (automated review jobs disabled): GitHub branch protection is the gate, so gate_ready = merged."""
    steps = card.get("steps") or {}
    gate = card.get("gate") or {}
    mode = "external" if card.get("gateMode") == "external" else "review"
    gate_ready = card.get("merged") is True if mode == "external" else gate.get("status") == "ready"
    met = {"steps": steps.get("total", 0) >= 1 and steps.get("done", 0) >= steps.get("total", 0),
           "card_acceptance": card.get("acceptanceEvidence") is True,
           "gate_ready": gate_ready,
           "merged": card.get("merged") is True,
           "plan_written_back": card.get("planWrittenBack") is True,
           "human_close": card.get("closed") is True}
    missing = [name for name in REQUIREMENTS if not met[name]]
    return {"done": not missing, "missing": missing, "gate": mode}


def closable(state):
    """The close_card precondition: everything except the human close itself is met."""
    return state["missing"] == ["human_close"]


def link_for(links, node):
    """The card's PR link that counts for done: a merged one wins, else the newest reported."""
    own = [item for item in links or [] if item.get("cardId") == node]
    return next((item for item in own if item.get("state") == "merged"), own[-1] if own else None)


def facts(card, link, gate, closed=False, external=False):
    """Done-state input from a process card (`steps`, `acceptanceEvidence`), its link and gate;
    `external` = automated review jobs are disabled (gates_by_execution returned None)."""
    return {"steps": card.get("steps"), "acceptanceEvidence": card.get("acceptanceEvidence"),
            "gate": (gate or {}).get("reviewGate"), "gateMode": "external" if external else "review", "merged": bool(link) and link.get("state") == "merged",
            "planWrittenBack": bool(link) and link.get("planWrittenBack") is True, "closed": closed}


def gates_by_execution(db, project, workspace):
    """All linked-PR gates (merged ones included) keyed by executionId; None with review jobs disabled."""
    from backend.canvas import opora_review_risk as risk
    from backend.canvas.opora_review_gate import review_gates

    config = risk.load()
    if not config["enabled"]:
        return None
    return {item["executionId"]: item for item in review_gates(db, project, workspace, config)}


def closure_gate(canvas, project, workspace, node):
    """None for a card without accepted steps (legacy closure), else its done-state.

    Raises ValueError when anything but the human close is missing. The caller holds the
    graph and project locks (desktop-v3 state write); every read here is re-entrant."""
    from backend.canvas import opora_agent_state_pulls as pulls
    from backend.canvas.opora_plan_steps import steps_of
    from backend.canvas.opora_step_results import progress
    from database.repositories.opora_changesets import ChangesetRepository

    db = canvas.db_for(project)
    repo = ChangesetRepository(db, project, workspace)
    head = repo.head()
    document = next((item for item in (repo.read(head)["documents"] if head else []) if item["nodeId"] == node), None)
    if not document or not steps_of(document["fields"]):
        return None
    summary, evidence = progress(db, project, workspace, node, document)
    link = link_for(pulls.read(canvas, project, workspace), node)
    gates = gates_by_execution(db, project, workspace)
    gate = (gates or {}).get(link["executionId"]) if link else None
    state = card_done_state(facts({"steps": summary, "acceptanceEvidence": evidence}, link, gate,
                                  external=gates is None))
    if not closable(state):
        missing = [name for name in state["missing"] if name != "human_close"]
        raise ValueError("Kartu nelze uzavřít; definice hotovo (docs/oporahub-plan-steps.md) ještě chybí: "
                         + ", ".join(missing) + ".")
    return state
