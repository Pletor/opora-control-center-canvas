"""Událost outboxu OporaHubu → pole živého procesu `opora.process-event/1` (docs/zivy-proces.md §4).

Čistá funkce bez I/O. Události přijaté z kanceláře nesou fázi, stav a titulek uložené; událostem
Opory (`source: "opora"`, sloupce NULL) je `derive` dopočítá z `kind`, `stage`, `health` a `data`.
Nic nedomýšlí: co z druhu nevyplývá, je `info`.
"""
from backend.canvas.process_event_validation import SCHEMA

# kind → (phase, state, titulek)
KINDS = {
    "lease.claimed": ("work", "start", "Běh převzal kartu"),
    "lease.heartbeat": ("work", "progress", "Běh prodloužil pronájem"),
    "lease.expired": ("work", "fail", "Pronájem běhu vypršel"),
    "result.reported": ("work", "ok", "Výsledek běhu nahlášen"),
    "step.started": ("work", "start", "Krok plánu začal"),
    "step.done": ("work", "ok", "Krok plánu hotov"),
    "step.failed": ("work", "fail", "Krok plánu selhal"),
    "pr.linked": ("review", "info", "PR propojen s během"),
    "review.round": ("review", "progress", "Kolo review"),
    "review.finding": ("review", "info", "Nález review"),
    "gate.changed": ("review", "info", "Brána merge se změnila"),
    "harness.fixture.observed": ("checks", "info", "Pozorování testu Harness"),
    "formal.result": ("checks", "info", "Výsledek formálního ověření"),
    "decision.created": ("intake", "wait", "Čeká na rozhodnutí člověka"),
    "decision.resolved": ("intake", "ok", "Rozhodnutí vyřízeno"),
    "changeset.proposed": ("plan", "info", "Návrh plánu zapsán"),
    "changeset.accepted": ("plan", "ok", "Plán přijat"),
    "autorebase.done": ("merge", "ok", "Auto-rebase návrhu hotov"),
    "autorebase.conflict": ("merge", "blocked", "Auto-rebase narazil na konflikt"),
    "merge.done": ("merge", "ok", "PR sloučen"),
    "writeback.done": ("merge", "ok", "Merge zapsán zpět do plánu"),
    "card.closed": ("memory", "ok", "Dokončení karty potvrzeno"),
    "card.reopened": ("work", "info", "Karta znovu otevřena"),
    "stage.changed": ("work", "info", "Etapa karty se změnila"),
    "memory.recall": ("memory", "info", "Vybavení z paměti role"),
    "memory.write": ("memory", "ok", "Zápis do paměti role"),
    "plan.commit": ("plan", "info", "Commit zadání (OporaHub)"),
}
STAGE_PHASE = {"plan": "plan", "proposal": "plan", "acceptance": "plan", "claim": "intake", "work": "work",
               "evidence": "checks", "review": "review", "pull_request": "review", "merge": "merge",
               "plan_writeback": "merge"}
HEALTH_STATE = {"ok": "progress", "waiting": "wait", "blocking": "blocked"}
GATE_STATE = {"ready": "ok", "pending": "wait", "blocked": "blocked"}
DECISION_PHASE = {"accept": "plan", "close_card": "merge", "review_round_cap": "review",
                  "verification_counterexample": "checks", "verification_failed": "checks"}
FORMAL_OK = {"proved", "passed", "verified", "ok"}
FORMAL_FAIL = {"failed", "counterexample", "refuted", "error"}


def _classify(event):
    kind, data = event["kind"], event.get("data") or {}
    phase, state, title = KINDS.get(kind, ("work", "info", kind))
    if kind == "stage.changed" and event.get("stage") in STAGE_PHASE:
        phase = STAGE_PHASE[event["stage"]]
        state = HEALTH_STATE.get(event.get("health"), "info")
        title = f"Karta v etapě {event['stage']}"
    elif kind == "gate.changed":
        gate = data.get("gate") if isinstance(data.get("gate"), dict) else {}
        state = GATE_STATE.get(gate.get("status"), "info")
    elif kind == "formal.result":
        outcome = data.get("outcome")
        state = "ok" if outcome in FORMAL_OK else "fail" if outcome in FORMAL_FAIL else "info"
    elif kind.startswith("decision.") and data.get("decision") in DECISION_PHASE:
        phase = DECISION_PHASE[data["decision"]]
    elif kind == "review.finding" and data.get("status") == "open":
        state = "wait"
    elif kind == "review.round" and isinstance(data.get("round"), int):
        title = f"Kolo review {data['round']}"
    return phase, state, title


def derive(event):
    """Doplní `schema`, `eventId`, `phase`, `state`, `title` a `refs` tam, kde zdroj nic neuložil."""
    phase, state, title = _classify(event)
    refs = event.get("refs")
    if refs is None:
        refs = {"project": event["projectId"], "workspace": event["workspaceId"]}
        for key, field in (("cardId", "nodeId"), ("executionId", "executionId"), ("pr", "prNumber")):
            if event.get(field) is not None:
                refs[key] = event[field]
    return {**event, "schema": SCHEMA, "eventId": event.get("externalId") or f"opora:{event['id']}",
            "phase": event.get("phase") or phase, "state": event.get("state") or state,
            "title": event.get("title") or title, "refs": refs}
