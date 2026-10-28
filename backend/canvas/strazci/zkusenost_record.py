"""Záznam zkušenosti strážce `zkusenost` (`docs/strazci.md` §4): čisté funkce, žádný model, žádné I/O.

Záznam `opora.guard-experience/1` = `{card, role, passed, failed, steps, evidence}`, tedy kontraktní „karta, role, co
prošlo, co spadlo a čím opraveno, čísla kroků, odkaz na doklad“. `role` doplní až doručení (role karty se může
nastavit později). Stejný vstup dává stejný záznam.

- Uzavření karty (`card.closed`) a merge PR (`merge.done`): kroky karty z událostí `step.done` / `step.failed`
  (u merge jen kroky sloučeného běhu). Prošlo = kroky, jejichž poslední zpráva je `done`; spadlo = kroky s aspoň
  jedním `failed`, `fixedBy` = pozdější `step.done` téhož kroku (běh a událost), jinak null. Doklad = událost
  a poslední merge PR karty.
- Doklad cesty (`journey_runs`): prošlo / spadlo = segmenty cesty; segment, který v předchozím dokladu téže cesty
  spadl a teď prošel, je opravený tímto dokladem. Čísla kroků = pořadí segmentů. Doklad = `seq`, příkaz, log.
Kroky i segmenty hlásí agent (`agent-reported`), strážce je jen skládá.
"""
SCHEMA = "opora.guard-experience/1"
MEANING = "Deterministický záznam strážce zkusenost z událostí OPORY; kroky a segmenty hlásil agent, nic neověřeno."
LIMIT = 50


def steps_summary(steps):
    """`[(eventId, kind, executionId, stepId)]` v pořadí událostí → (prošlo, spadlo, pořadí kroků)."""
    order, last, failed = [], {}, {}
    for event_id, kind, execution, step in steps:
        if step is None:
            continue
        if step not in last:
            order.append(step)
        last[step] = kind
        if kind == "step.failed":
            entry = failed.setdefault(step, {"step": step, "failures": 0, "fixedBy": None})
            entry["failures"] += 1
            entry["fixedBy"] = None  # nové selhání po opravě opravu ruší
        elif step in failed:
            failed[step]["fixedBy"] = {"executionId": execution, "eventId": event_id}
    passed = [step for step in order if last[step] == "step.done"]
    return passed[:LIMIT], [failed[step] for step in order if step in failed][:LIMIT], order[:LIMIT]


def card_record(project, trigger, steps, merge):
    """Záznam k `card.closed` / `merge.done`. `trigger` = událost `{id, at, kind, workspaceId, nodeId, executionId,
    prNumber, data}`, `steps` jako u `steps_summary`, `merge` = poslední `merge.done` karty `{prNumber, data}` nebo None."""
    passed, failed, order = steps_summary(steps)
    evidence = {"event": trigger["kind"], "eventId": trigger["id"], "at": trigger["at"]}
    if trigger.get("executionId"):
        evidence["executionId"] = trigger["executionId"]
    if merge is not None:
        data = merge.get("data") or {}
        evidence["pullRequest"] = {"number": merge.get("prNumber"), "repository": data.get("repository"),
                                   "mergeSha": data.get("mergeSha")}
    if trigger["kind"] == "card.closed":
        evidence["closedBy"] = (trigger.get("data") or {}).get("by")
    return {"schema": SCHEMA, "project": project, "workspace": trigger["workspaceId"], "card": trigger["nodeId"],
            "source": trigger["kind"], "at": trigger["at"], "passed": passed, "failed": failed, "steps": order,
            "evidence": evidence, "meaning": MEANING}


def _pair(segment):
    return f"{segment['from']} → {segment['to']}"


def journey_record(project, workspace, card, seq, run, previous):
    """Záznam k dokladu cesty `run` (uložený jako `seq`); `previous` = předchozí doklad téže cesty nebo None."""
    segments = run["segments"]
    passed = [_pair(segment) for segment in segments if segment["ok"]]
    failed = [{"segment": _pair(segment), "reason": segment.get("reason"), "fixedBy": None}
              for segment in segments if not segment["ok"]]
    now_ok = set(passed)
    for segment in (previous or {}).get("segments", []):
        if not segment["ok"] and _pair(segment) in now_ok:
            failed.append({"segment": _pair(segment), "reason": segment.get("reason"), "fixedBy": {"journeyRun": seq}})
    evidence = {"event": "journey.run", "journeyRun": seq, "applicationId": run["applicationId"],
                "journeyId": run["journeyId"], "command": run["command"], "at": run["at"], "passed": run["passed"],
                "planDigest": run["planDigest"], **({"logUrl": run["logUrl"]} if run.get("logUrl") else {})}
    return {"schema": SCHEMA, "project": project, "workspace": workspace, "card": card, "source": "journey.run",
            "at": run["at"], "passed": passed[:LIMIT], "failed": failed[:LIMIT],
            "steps": list(range(1, len(segments) + 1)), "evidence": evidence, "meaning": MEANING}
