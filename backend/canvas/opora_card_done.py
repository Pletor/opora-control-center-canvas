"""The single definition of done of an OporaHub card (night contract §3).

done = every accepted plan step reported `done` + card acceptance evidenced against the
current accepted spec + review gate `ready` (in a project without GitHub: the local gate,
docs/lokalni-slouceni.md) + PR (or local) merge + plan written back + every customer
journey the card lies on verified by a passed, fresh run (docs/brana-cesty.md §5) + the card close
(`human_close`, the name stays). The close is deterministic: once everything else is met the server closes
the card itself (`opora_card_auto_close`, `by: "opora"`); a manual close in the UI stays possible, never
required. `card_done_state` is pure; `closure_gate` loads the facts for the close precondition and replaces the legacy evidence/checks/pipeline closure gate for every card
whose accepted spec has plan steps (cards without steps keep the legacy path readable).
Steps and card acceptance added to the accepted spec after the merge count as met by the merge (`afterMerge`,
"Kroky přidané po sloučení"), visibly outside the standard process. docs/oporahub-plan-steps.md.
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
    latest checks on the merged commit passed (`checksPassed`, True for a card without checks).

    `afterMerge` (only with `merged`) = {executionId, number, mergeSha, steps: [{id, title}], acceptance}: what the
    merged run never had in its assignment (`after_merge_facts`). Such steps make up the missing ones and such an
    acceptance stands in for the evidence; the state then names the requirements met this way in `afterMerge`
    and carries `afterMergeEvidence`. Nothing is relaxed for an unmerged link."""
    steps = card.get("steps") or {}
    late = card.get("afterMerge") if card.get("merged") is True and isinstance(card.get("afterMerge"), dict) else None
    late_steps = list((late or {}).get("steps") or [])
    total, done = steps.get("total", 0), steps.get("done", 0)
    gate = card.get("gate") or {}
    mode = card.get("gateMode") if card.get("gateMode") in ("external", "local") else "review"
    if mode == "review":
        gate_ready = gate.get("status") == "ready"
    else:
        gate_ready = card.get("merged") is True and (mode == "external" or card.get("checksPassed", True) is True)
    after = []
    if total >= 1 and done < total and late_steps and done + len(late_steps) >= total:
        after.append("steps")
    if card.get("acceptanceEvidence") is not True and late is not None and late.get("acceptance") is True:
        after.append("card_acceptance")
    met = {"steps": (total >= 1 and done >= total) or "steps" in after,
           "card_acceptance": card.get("acceptanceEvidence") is True or "card_acceptance" in after,
           "gate_ready": gate_ready,
           "merged": card.get("merged") is True,
           "plan_written_back": card.get("planWrittenBack") is True,
           "journeys": not card.get("journeys"),
           "human_close": card.get("closed") is True}
    missing = [name for name in REQUIREMENTS if not met[name]]
    evidence = {"executionId": (late or {}).get("executionId"), "number": (late or {}).get("number"),
                "mergeSha": (late or {}).get("mergeSha"), "steps": late_steps if "steps" in after else []}
    return {"done": not missing, "missing": missing, "gate": mode,
            **({"blockingJourneys": list(card["journeys"])} if "journeys" in missing else {}),
            **({"afterMerge": after, "afterMergeEvidence": evidence} if after else {})}


def after_merge_note(state):
    """The trace sentence of a card met by the merge ("Kroky přidané po sloučení"), "" for a standard card."""
    after = (state or {}).get("afterMerge") or []
    if not after:
        return ""
    evidence = state.get("afterMergeEvidence") or {}
    number, sha = evidence.get("number"), (evidence.get("mergeSha") or "")[:7]
    where = (f"sloučení PR #{number}" if type(number) is int else "lokálním sloučení") + (f" ({sha})" if sha else "")
    parts = [" ".join(part for part in (item.get("id"), item.get("title")) if part) for item in evidence.get("steps") or []]
    tail = ([("kroky: " + ", ".join(parts))] if parts else []) + (["akceptace karty"] if "card_acceptance" in after else [])
    return (f"Kroky přibyly po {where} – uznány sloučením, mimo standardní proces"
            + (": " + "; ".join(tail) if tail else "") + ".")


def closable(state):
    """The close precondition: everything except the close itself is met (the server then closes the card)."""
    return state["missing"] == ["human_close"]


def link_for(links, node):
    """The card's PR link that counts for done: a merged one wins, else the newest reported."""
    own = [item for item in links or [] if item.get("cardId") == node]
    return next((item for item in own if item.get("state") == "merged"), own[-1] if own else None)


def after_merge_facts(db, project, workspace, node, document, link):
    """`afterMerge` input of `card_done_state` for a merged `link`, else None (opora_step_results.after_merge)."""
    from backend.canvas.opora_step_results import after_merge

    if not link or link.get("state") != "merged":
        return None
    found = after_merge(db, project, workspace, node, document, link["executionId"])
    if not found or not (found["steps"] or found["acceptance"]):
        return None
    return {"executionId": link["executionId"], "number": link.get("number"), "mergeSha": link.get("mergeSha"), **found}


def facts(card, link, gate, closed=False, external=False, local_checks=None):
    """Done-state input from a process card (`steps`, `acceptanceEvidence`, `journeys`), its link and gate;
    `external` = automated review jobs are disabled (gates_by_execution returned None); `local_checks`
    None = the project has GitHub, a bool = local mode with the card's checks result (`local_checks_passed`)."""
    mode = "local" if local_checks is not None else "external" if external else "review"
    merged = bool(link) and link.get("state") == "merged"
    late = card.get("afterMerge")
    late = late if merged and isinstance(late, dict) and late.get("executionId") == link.get("executionId") else None
    return {"steps": card.get("steps"), "acceptanceEvidence": card.get("acceptanceEvidence"), "afterMerge": late,
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
    late = after_merge_facts(db, project, workspace, node, document, link)
    state = card_done_state(facts({"steps": summary, "acceptanceEvidence": evidence, "journeys": blocking,
                                   "afterMerge": late}, link, gate,
                                  external=gates is None, local_checks=local))
    if not closable(state):
        missing = [name for name in state["missing"] if name != "human_close"]
        if missing == ["journeys"]:
            raise ValueError(journeys_refusal(blocking))
        raise ValueError("Kartu nelze uzavřít; definice hotovo (docs/oporahub-plan-steps.md) ještě chybí: "
                         + ", ".join(missing) + "."
                         + (" " + journeys_refusal(blocking) if blocking else ""))
    return state
