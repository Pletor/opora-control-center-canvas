"""Most záznam činnosti → outbox pro to, co outbox sám nevydává (docs/zivy-proces.md §4).

Outbox OporaHubu vzniká v místě změny pro běhy, review, merge, návrhy i etapy. Bez vlastní
události zůstává jen paměť role (OpenViking je mimo transakci Opory) a starý commit zadání
`/api/opora-commit`. Ty se po úspěšném zápisu přidají do outboxu jako `memory.recall`,
`memory.write` a `plan.commit`; nic jiného se z `activity_log` nepřebírá, aby žádná změna
neměla dvě události.
"""
from backend.canvas.opora_events import emit_event

BRIDGED = {"/api/memory/recall": "memory.recall", "/api/memory/lend": "memory.recall",
           "/api/memory/remember": "memory.write", "/api/opora-commit": "plan.commit"}


def bridged_kind(method, path, status):
    """Druh události outboxu pro úspěšný zápis, nebo None."""
    if method != "POST" or not 200 <= status < 300:
        return None
    return BRIDGED.get(path)


def actor_name(actor, agent):
    return "human" if actor == "human" else (agent or "agent") if actor == "agent" else None


def bridge(service, *, method, path, status, actor, agent, described):
    """Zapíše jednu událost do outboxu projektu; bez rozsahu nebo pro neznámý projekt nic."""
    kind = bridged_kind(method, path, status)
    project, workspace = described.get("project"), described.get("workspace")
    if kind is None or not project or not workspace or not service.project_exists(project):
        return None
    nodes = described.get("nodeIds") or []
    with service.lock_for(project):
        return emit_event(service, project_id=project, workspace_id=workspace, kind=kind,
                          node_id=nodes[0] if nodes else None, actor=actor_name(actor, agent), data={"path": path})
