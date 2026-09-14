"""Životní cyklus procesu: návrh (draft) → proces (running) → hotovo (done) → oprava (repair).

Čisté funkce nad slovníkem procesu; nic nezapisují. Tabulka přechodů je jediný zdroj pravdy,
každý zakázaný přechod končí ValueError se jménem obou stavů.
"""

from backend.editor.process.process_store import STATES, STEP_STATES, now, validate

LABELS = {"draft": "návrh", "running": "proces", "done": "hotovo", "repair": "oprava"}

# (z, do) -> (kdo smí, popis podmínky)
TRANSITIONS = {
    ("draft", "running"): (("human", "agent"), "přiřazený worktree, nebo poznámka „bez worktree“"),
    ("running", "done"): (("human", "agent"), "každý krok hotový s důkazem, žádný neselhal"),
    ("running", "repair"): (("system", "agent", "human"), "failure s důvodem, krokem a autorem"),
    ("repair", "running"): (("human", "agent"), "vyplněný popis opravy failure.fix"),
    ("done", "repair"): (("human",), "failure s důvodem"),
}


def allowed_targets(process: dict, actor_kind: str) -> list[str]:
    return [to for (frm, to), (who, _) in TRANSITIONS.items() if frm == process["state"] and actor_kind in who]


def _copy(process: dict) -> dict:
    return {
        **process,
        "inputs": {**process["inputs"], "references": list(process["inputs"].get("references", []))},
        "steps": [{**step, "evidence": dict(step["evidence"]) if step.get("evidence") else None} for step in process["steps"]],
        "outputs": [dict(item) for item in process["outputs"]],
        "failure": dict(process["failure"]) if process.get("failure") else None,
        "history": [dict(item) for item in process["history"]],
    }


def transition(process: dict, to: str, *, by: dict, note: str = "", failure: dict | None = None) -> dict:
    validate(process)
    frm = process["state"]
    if to not in STATES:
        raise ValueError("Neznámý cílový stav.")
    if frm == to:
        raise ValueError(f"Proces už je ve stavu {LABELS[frm]}; přechod {LABELS[frm]} → {LABELS[to]} není povolen.")
    rule = TRANSITIONS.get((frm, to))
    if rule is None:
        raise ValueError(f"Přechod {LABELS[frm]} → {LABELS[to]} není povolen.")
    who, condition = rule
    if by.get("kind") not in who:
        raise ValueError(f"Přechod {LABELS[frm]} → {LABELS[to]} smí vyvolat jen: {', '.join(who)}.")

    result = _copy(process)
    stamp = now()
    if to == "running" and frm == "draft":
        if not isinstance(result["inputs"].get("worktree"), str) and "bez worktree" not in note.casefold():
            raise ValueError("Spuštění vyžaduje přiřazený worktree, nebo výslovnou poznámku „bez worktree“.")
    elif to == "done":
        for step in result["steps"]:
            if step["state"] == "failed":
                raise ValueError(f"Krok {step['id']} selhal; proces nelze dokončit.")
            if step["state"] != "done" or not step.get("evidence"):
                raise ValueError(f"Krok {step['id']} není hotový s důkazem; proces nelze dokončit.")
    elif to == "repair":
        if not failure or not failure.get("reason") or "stepId" not in failure or not failure.get("reportedBy"):
            raise ValueError("Přechod do opravy vyžaduje failure s reason, stepId a reportedBy.")
        result["failure"] = {"reason": failure["reason"], "stepId": failure["stepId"], "at": failure.get("at") or stamp, "reportedBy": failure["reportedBy"], "fix": None}
        for step in result["steps"]:
            if step["id"] == failure["stepId"]:
                step["state"] = "failed"
                step["evidence"] = step.get("evidence") or {"summary": failure["reason"], "at": stamp, "by": failure["reportedBy"], "reportId": failure.get("reportId"), "outputs": []}
    elif to == "running" and frm == "repair":
        fix = (result.get("failure") or {}).get("fix")
        if not isinstance(fix, str) or not fix.strip():
            raise ValueError("Návrat z opravy vyžaduje vyplněný popis opravy (failure.fix).")
        for step in result["steps"]:
            if step["state"] == "failed":
                step["state"] = "pending"
                step["evidence"] = None
    result["state"] = to
    result["history"].append({"from": frm, "to": to, "at": stamp, "by": by, "note": note or condition})
    validate(result)
    return result


def set_fix(process: dict, fix: str) -> dict:
    if process["state"] != "repair" or not process.get("failure"):
        raise ValueError("Popis opravy lze zapsat jen procesu ve stavu oprava.")
    if not isinstance(fix, str) or not fix.strip():
        raise ValueError("Popis opravy nesmí být prázdný.")
    result = _copy(process)
    result["failure"]["fix"] = fix.strip()
    return result


def mark_step(process: dict, step_id: str, state: str, evidence: dict | None = None) -> dict:
    if state not in STEP_STATES:
        raise ValueError("Neznámý stav kroku.")
    if state in ("done", "failed") and not evidence:
        raise ValueError(f"Krok ve stavu {state} musí mít důkaz.")
    result = _copy(process)
    for step in result["steps"]:
        if step["id"] == step_id:
            step["state"] = state
            step["evidence"] = dict(evidence) if evidence else None
            validate(result)
            return result
    raise ValueError("Krok neexistuje.")
