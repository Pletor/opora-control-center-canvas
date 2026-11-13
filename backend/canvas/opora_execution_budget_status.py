"""Sparse budget admission projection, distinct from lease/context eligibility."""

from database.repositories.opora_execution_budgets import Budgets


def status(db, project, workspace, node, accepted):
    repo = Budgets(db, project, workspace, node)
    enrolled = repo.enrolled()
    head = repo.head()
    policy = repo.read_policy(head) if head else None
    family = repo.family(accepted, require_complete=enrolled) if accepted else None
    matching = policy if policy and policy["acceptedRevision"] == accepted else None
    attempts = family["attempts"] if family else 0
    repairs = family["repairRounds"] if family else 0
    reason = None
    if enrolled and not matching:
        reason = "Human budget policy for the current accepted revision is required."
    elif matching and attempts >= matching["limits"]["maxAttempts"]:
        reason = "Execution attempt budget is exhausted."
    elif matching and family["hasReported"] and repairs >= matching["limits"]["maxRepairRounds"]:
        reason = "Execution repair budget is exhausted."
    if reason and "exhausted" in reason:
        from backend.app import guards  # líně: balíček backend.app načítá factory (cyklus importů)

        # OP-F43588.budget: jediný výpočet vyčerpání; čte ho agent-state (blockReason) i before_claim
        if not guards.check("budget", project, blocked=True, subject=node,
                            message=f"Rozpočet karty vyčerpán: {attempts} pokusů, {repairs} kol oprav."):
            reason = None
    clock = db.execute("SELECT frozen FROM opora_execution_budget_clock WHERE id=1").fetchone()
    if enrolled and clock and clock[0]:
        reason = "Budget server clock is frozen after an observed regression."
    if (
        enrolled
        and not clock
        and db.execute(
            "SELECT 1 FROM opora_execution_budget_ledger WHERE kind='allocation' LIMIT 1"
        ).fetchone()
    ):
        reason = "Persisted budget clock authority is missing."
    return {
        "enrolled": enrolled,
        "policyHead": head,
        "policy": matching,
        "family": family,
        "attemptsUsed": attempts,
        "repairRoundsUsed": repairs,
        "remainingAttempts": max(0, matching["limits"]["maxAttempts"] - attempts)
        if matching
        else 0,
        "remainingRepairRounds": max(0, matching["limits"]["maxRepairRounds"] - repairs)
        if matching
        else 0,
        "latestExecutionId": family["lastExecutionId"] if family else None,
        "blockedReason": reason,
    }


def unavailable(db, project, workspace, node):
    """An unavailable/corrupt budget never advertises a v1 downgrade or invented counts."""
    if not isinstance(node, str):
        return 1, None
    repo = Budgets(db, project, workspace, node)
    try:
        enrolled = repo.enrolled()
    except ValueError:
        return 2, None
    try:
        from database.repositories.opora_changesets import ChangesetRepository

        accepted = ChangesetRepository(db, project, workspace).head()
        return (2 if enrolled else 1), status(db, project, workspace, node, accepted)
    except ValueError:
        return (2 if enrolled else 1), None
