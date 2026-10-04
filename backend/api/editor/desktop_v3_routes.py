"""HTTP kontrakt Desktop v3: paměť projektu, stav uzlů, podklady pro agenta.

Zápis do paměti role (OpenViking) je **vedlejší účinek, nikdy podmínka**: prostor karty se
zrcadlí až po úspěšném uložení a uzavřená karta se předává jako session. Když je paměť
vypnutá, server dole nebo karta bez role, uložení v Opoře proběhne úplně stejně.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.editor.agent_handoff.external_agent_tasks import ExternalAgentTasks
from backend.editor.agent_memory import pipeline_library
from backend.editor.agent_memory.trace import tags_index, trace


def _node_role(node):
    value = node.get("agentRole") if isinstance(node, dict) else None
    return value if isinstance(value, str) and value else None


def confirmed_nodes(state_payload):
    """Které karty jsou v daném stavu uzavřené; podklad pro „právě se uzavřela“."""
    nodes = state_payload.get("nodes", {}) if isinstance(state_payload, dict) else {}
    return {
        node_id for node_id, node in nodes.items()
        if isinstance(node, dict) and bool(node.get("done", {}).get("confirmed", False))
    }


def create_desktop_v3_router(state, packets, briefs, agent_output, block_access, agent_workspace,
                             *, memory_service=None):
    router = APIRouter(prefix="/api/desktop-v3", tags=["desktop-v3"])
    external_tasks = ExternalAgentTasks(packets)

    def remembered(call):
        """Paměť je nejvýš doplněk: každá její chyba se tiše spolkne, uložení už proběhlo."""
        if memory_service is None:
            return
        try:
            call()
        except Exception:  # noqa: BLE001 - zápis do paměti nikdy nesmí shodit uložení
            return

    @router.get("/state")
    def read_state(project: str, workspace: str):
        return state.read(project, workspace)

    @router.post("/state")
    def save_state(payload: dict):
        before = set()
        if memory_service is not None and isinstance(payload, dict):
            try:
                before = confirmed_nodes(state.read(payload["project"], payload["workspace"])["state"])
            except Exception:  # noqa: BLE001 - neplatný rozsah vyřeší samo state.save
                before = set()
        saved = state.save(payload)
        for node_id in sorted(confirmed_nodes(saved["state"]) - before):
            remembered(lambda node_id=node_id: _commit_card(payload, saved, node_id))
        return saved

    def _commit_card(payload, saved, node_id):
        """Právě potvrzená karta jde do paměti role jako session; extrakci dělá OpenViking."""
        role = _node_role(saved["state"]["nodes"].get(node_id, {}))
        if role is None:
            return
        project, workspace = payload["project"], payload["workspace"]
        space = agent_workspace.read(project, workspace, node_id) or {}
        sections = {key: value for key, value in (space.get("workspace") or {}).items()
                    if key not in ("updatedAt", "by")}
        memory_service.commit_card(role, project, node_id, sections)

    @router.get("/trace")
    def read_trace(project: str, workspace: str, id: str):
        """Co ID je, komu patří a odkud/kam vede; 404 = žádná taková entita v tomto rozsahu."""
        stored = state.read(project, workspace)
        graph = state.canvas.view(project, workspace)["graph"]
        found = trace(stored["state"], graph, id)
        if found is None:
            return JSONResponse({"error": f"Entita {id} v tomto pracovním prostoru neexistuje."}, status_code=404)
        return found

    @router.get("/tags")
    def read_tags(project: str, workspace: str):
        return tags_index(state.read(project, workspace)["state"])

    @router.get("/pipelines")
    def read_pipelines():
        """Knihovna předloh pro blok Akce; jen čtení z library/pipelines.json."""
        return pipeline_library.load()

    @router.get("/node-brief")
    def read_node_brief(project: str, workspace: str, nodeId: str):
        """Karta jako jeden JSON pro model (opora.node-brief/1); popis stavu, ne příkazy."""
        return briefs.build(project, workspace, nodeId)

    @router.post("/agent-output")
    def write_agent_output(payload: dict):
        """Výstup modelu (opora.agent-output/1) pod CAS revizí; vrací novou StateResponse."""
        return agent_output.apply(payload)

    @router.get("/agent-results")
    def read_agent_results(project: str, workspace: str, nodeId: str, before: int | None = None):
        """Original outputs retain their specification version after the live card changes."""
        return agent_output.results.history(project, workspace, nodeId, before)

    @router.get("/block")
    def read_block(project: str, workspace: str, nodeId: str, blockId: str):
        """Jeden blok karty s dětmi a rodičem (adresný přístup); 404 = blok v tomto rozsahu neexistuje."""
        found = block_access.read(project, workspace, nodeId, blockId)
        if found is None:
            return JSONResponse(
                {"error": f"Blok {blockId} uzlu {nodeId} v tomto pracovním prostoru neexistuje."}, status_code=404
            )
        return found

    @router.post("/block")
    def write_block(payload: dict):
        """Operace nad jedním blokem (add/update/remove/todo) pod CAS revizí; vrací StateResponse + block."""
        return block_access.apply(payload)

    @router.get("/agent-workspace")
    def read_agent_workspace(project: str, workspace: str, nodeId: str):
        """Pracovní prostor agenta u karty; 404 = karta v tomto rozsahu neexistuje."""
        found = agent_workspace.read(project, workspace, nodeId)
        if found is None:
            return JSONResponse(
                {"error": f"Karta {nodeId} v tomto pracovním prostoru neexistuje."}, status_code=404
            )
        return found

    @router.get("/agent-workspace-summaries")
    def read_agent_workspace_summaries(project: str, workspace: str):
        """Souhrn vyplněnosti pracovního prostoru všech karet v rozsahu jedním dotazem."""
        return agent_workspace.summaries(project, workspace)

    @router.post("/agent-workspace")
    def write_agent_workspace(payload: dict):
        """Přepis uvedených sekcí prostoru pod CAS revizí; neuvedené sekce zůstávají.

        Po úspěšném uložení se prostor zrcadlí do paměti role. Chyba zrcadlení se ignoruje:
        pravda je uložená v Opoře, OpenViking je jen druhá kopie."""
        saved = agent_workspace.save(payload)
        remembered(lambda: _mirror(payload, saved))
        return saved

    def _mirror(payload, saved):
        node_id = payload["nodeId"]
        stored = state.read(payload["project"], payload["workspace"])["state"]
        role = _node_role(stored["nodes"].get(node_id, {}))
        if role is None:
            return
        sections = {key: value for key, value in saved["workspace"].items()
                    if key not in ("updatedAt", "by")}
        memory_service.mirror_workspace(role, payload["project"], node_id, sections)

    @router.post("/packet/preview")
    def packet_preview(payload: dict):
        return packets.build(payload)

    @router.post("/packet/snapshot")
    def packet_snapshot(payload: dict):
        stored = packets.snapshot(payload)
        return {key: stored[key] for key in ("id", "digest", "packet", "createdAt")}

    @router.get("/packet/snapshots/{snapshot_id}")
    def packet_snapshot_read(snapshot_id: str, project: str, workspace: str):
        stored = packets.load(snapshot_id, project, workspace)
        return {key: stored[key] for key in ("id", "digest", "packet", "createdAt")}

    @router.post("/packet/snapshots/{snapshot_id}/external-export")
    def external_export(snapshot_id: str, payload: dict):
        return external_tasks.export(snapshot_id, payload)

    @router.get("/packet/snapshots/{snapshot_id}/external-export")
    def external_read(snapshot_id: str, project: str, workspace: str, nodeId: str, digest: str):
        return external_tasks.read(snapshot_id, {"project": project, "workspace": workspace,
                                                "nodeId": nodeId, "digest": digest})

    return router
