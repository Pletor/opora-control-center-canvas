"""The single definition of done of an OporaHub card (night contract §3).

done = every accepted plan step reported `done` + card acceptance evidenced against the
current accepted spec + review gate `ready` (in a project without GitHub: the local gate,
docs/lokalni-slouceni.md) + PR (or local) merge + plan written back + every customer
journey the card lies on verified by a passed, fresh run (docs/brana-cesty.md §5) + the card close
(`human_close`, the name stays). The close is deterministic: once everything else is met the server closes
the card itself (`opora_card_auto_close`, `by: "opora"`); a manual close in the UI stays possible, never
required. `card_done_state` is pure; `closure_gate` loads the facts for the close precondition and replaces the legacy evidence/checks/pipeline closure gate for every card
whose accepted spec has plan steps (cards without steps keep the legacy path readable).
docs/oporahub-plan-steps.md.
"""
REQUIREMENTS = ("steps", "card_acceptance", "gate_ready", "merged", "plan_written_back", "journeys", "human_close")
def merged_gate(gate, merged):
    """The review gate of a PR as the definition of done reads it: once the PR is merged, a `pending` gate
    (freshness, approvals, a review still running or never enqueued, self-checks) counts as `ready`, because the
    merge already decided (decision 2026-10-31, "zavři to a jdi dál"); a `blocked` gate (an open important finding,
    failed checks) keeps holding after the merge."""
    if not merged or not gate or gate.get("status") != "pending":
        return gate
    return {**gate, "status": "ready"}


def card_done_state(card):
    """`card` = {steps: {total, done}, acceptanceEvidence, gate: {status}|None, gateMode, merged,
    planWrittenBack, journeys?, closed} → {done, missing: [requirement, ...] in contract order, gate,
    blockingJourneys?}.

    `journeys` = journeys blocking the close (`journey_gate.journeys_blocking`: {journeyId, name, reason});
    missing or empty = the card is off every journey or each is verified. `blockingJourneys` repeats them
    only while the requirement is missing, so the human sees which journey and why.

    `gateMode` "review" (default): gate_ready = the OporaHub review gate is `ready`. "external"
    (automated review jobs disabled): GitHub branch protection is the gate, so gate_ready = merged.
    "local" (project without GitHub, docs/lokalni-slouceni.md): gate_ready = merged and the card's
    latest checks on the merged commit passed (`checksPassed`, True for a card without checks)."""
    steps = card.get("steps") or {}
    gate = card.get("gate") or {}
    mode = card.get("gateMode") if card.get("gateMode") in ("external", "local") else "review"
    if mode == "review":
        gate_ready = gate.get("status") == "ready"
    else:
        gate_ready = card.get("merged") is True and (mode == "external" or card.get("checksPassed", True) is True)
    met = {"steps": steps.get("total", 0) >= 1 and steps.get("done", 0) >= steps.get("total", 0),
           "card_acceptance": card.get("acceptanceEvidence") is True,
           "gate_ready": gate_ready,
           "merged": card.get("merged") is True,
           "plan_written_back": card.get("planWrittenBack") is True,
           "journeys": not card.get("journeys"),
           "human_close": card.get("closed") is True}
    missing = [name for name in REQUIREMENTS if not met[name]]
    return {"done": not missing, "missing": missing, "gate": mode,
            **({"blockingJourneys": list(card["journeys"])} if "journeys" in missing else {})}


def closable(state):
    """The close precondition: everything except the close itself is met (the server then closes the card)."""
    return state["missing"] == ["human_close"]


def link_for(links, node):
    """The card's PR link that counts for done: a merged one wins, else the newest reported."""
    own = [item for item in links or [] if item.get("cardId") == node]
    return next((item for item in own if item.get("state") == "merged"), own[-1] if own else None)


def facts(card, link, gate, closed=False, external=False, local_checks=None):
    """Done-state input from a process card (`steps`, `acceptanceEvidence`, `journeys`), its link and gate;
    `external` = automated review jobs are disabled (gates_by_execution returned None); `local_checks`
    None = the project has GitHub, a bool = local mode with the card's checks result (`local_checks_passed`)."""
    mode = "local" if local_checks is not None else "external" if external else "review"
    merged = bool(link) and link.get("state") == "merged"
    return {"steps": card.get("steps"), "acceptanceEvidence": card.get("acceptanceEvidence"),
            "journeys": card.get("journeys") or [],
            "gate": merged_gate((gate or {}).get("reviewGate"), merged), "gateMode": mode, "merged": merged,
            "planWrittenBack": bool(link) and link.get("planWrittenBack") is True, "closed": closed,
            "checksPassed": local_checks is not False}


def local_mode(service, project):
    """Gate `local` (docs/lokalni-slouceni.md §2): derived, never set; the project has no GitHub repository."""
    from backend.canvas.opora_execution_pr_enrollment import configured

    return configured(service, project) is None


def local_checks_passed(graph_node, run, link):
    """Local gate checks of one card on its merged commit: the latest check run of the card (`/api/check-run`,
    scope = card) is green on that commit; a card without a run passes only when it declares no `checks`."""
    commit = (link or {}).get("mergeSha") or ""
    if run is None:
        return not (graph_node or {}).get("checks")
    sha = run.get("sha") or ""
    return run.get("status") == "green" and bool(commit and sha) and (commit.startswith(sha) or sha.startswith(commit))


def local_checks_by_card(canvas, project, workspace, graph, links, nodes):
    """`{nodeId: bool}` for `nodes` in local mode; one read of the check runs for the whole project."""
    from backend.canvas.check_runs import CheckRuns

    runs = CheckRuns(canvas).latest_for_project(project, workspace)
    by_id = {item["id"]: item for item in graph["nodes"]}
    return {node: local_checks_passed(by_id.get(node), runs.get(node), link_for(links, node)) for node in nodes}


def gates_by_execution(db, project, workspace):
    """All linked-PR gates (merged ones included) keyed by executionId; None with review jobs disabled."""
    from backend.canvas import opora_review_risk as risk
    from backend.canvas.opora_review_gate import review_gates

    config = risk.load()
    if not config["enabled"]:
        return None
    return {item["executionId"]: item for item in review_gates(db, project, workspace, config)}


def journeys_blocking(canvas, project, workspace, node, graph=None):
    """Journeys blocking the close of `node` (docs/brana-cesty.md §5): the card's workspace graph and the
    project's latest journey runs, `stale` against that graph (like node-brief)."""
    from backend.project.architecture.journey_gate import journeys_blocking as blocking
    from backend.project.architecture.journey_runs import latest_journey_runs

    graph = canvas.view(project, workspace)["graph"] if graph is None else graph
    # Without runs every journey of the card blocks; a card off every journey never touches journey_runs.
    if not blocking(graph, node, {}):
        return []
    return blocking(graph, node, latest_journey_runs(canvas, project))


def journeys_by_card(canvas, project, workspace, nodes):
    """{nodeId: blocking journeys} for many cards at once (agent-state `cards[].dod`); same rules as above."""
    from backend.project.architecture.journey_gate import blocking_by_node
    from backend.project.architecture.journey_runs import latest_journey_runs

    graph = canvas.view(project, workspace)["graph"]
    if not blocking_by_node(graph, {}, nodes):
        return {}
    return blocking_by_node(graph, latest_journey_runs(canvas, project), nodes)


def journeys_refusal(blocking):
    """ValueError text for a close refused by the journey gate."""
    from backend.project.architecture.journey_gate import refusal

    return "Kartu nelze uzavřít; cesta zákazníka není ověřena (docs/brana-cesty.md §5): " + refusal(blocking) + "."


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
    blocking = journeys_blocking(canvas, project, workspace, node)
    local = None
    if local_mode(canvas, project):
        graph = canvas.view(project, workspace)["graph"]
        local = local_checks_by_card(canvas, project, workspace, graph, [link] if link else [], [node])[node]
    state = card_done_state(facts({"steps": summary, "acceptanceEvidence": evidence, "journeys": blocking}, link, gate,
                                  external=gates is None, local_checks=local))
    if not closable(state):
        missing = [name for name in state["missing"] if name != "human_close"]
        if missing == ["journeys"]:
            raise ValueError(journeys_refusal(blocking))
        raise ValueError("Kartu nelze uzavřít; definice hotovo (docs/oporahub-plan-steps.md) ještě chybí: "
                         + ", ".join(missing) + "."
                         + (" " + journeys_refusal(blocking) if blocking else ""))
    return state
