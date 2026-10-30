"""HTTP kontrakt Desktop v3: paměť projektu, stav uzlů, podklady pro agenta.

Zápis do paměti role (OpenViking) je **vedlejší účinek, nikdy podmínka**: prostor karty se
zrcadlí až po úspěšném uložení a uzavřená karta se předává jako session. Když je paměť
vypnutá, server dole nebo karta bez role, uložení v Opoře proběhne úplně stejně.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.http_etag import conditional, etag_of
from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas.activity_log import require_authority
from backend.canvas.graph import payload_project
from backend.canvas.opora_process_links import brief_metadata
from backend.canvas.source_realization import realize_source, source_status
from backend.editor.agent_handoff.external_agent_tasks import ExternalAgentTasks
from backend.editor.agent_memory import pipeline_library
from backend.editor.agent_memory.assignment_snapshots import assignment_comparison, save_assignment
from backend.editor.agent_memory.assignment_status import assignment_status
from backend.editor.agent_memory.card_leases import CardLeases
from backend.editor.agent_memory.confirm_proposals import confirm_proposals
from backend.editor.agent_memory.memory_items import BatchConflict, MemoryItems
from backend.editor.agent_memory.pipeline_routing import PipelineRouting
from backend.editor.agent_memory.pipeline_routing import profiles as pipeline_profiles
from backend.editor.agent_memory.scenario_history import scenario_history
from backend.editor.agent_memory.trace import trace
from backend.editor.agent_memory.usage import usage_summary
from backend.editor.agent_packet.card_checklist import checklists, missing
from backend.editor.agent_packet.frontier import frontier
from backend.editor.agent_packet.work_overview import work_overview


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
    items = MemoryItems(state)
    leases = CardLeases(state.canvas)
    routing = PipelineRouting(state.canvas, state)

    @router.get("/scenario-history")
    def read_scenario_history(project: str, workspace: str):
        return scenario_history(state.canvas, project, workspace)

    @router.get("/work-overview")
    def read_work_overview(project: str, workspace: str):
        return work_overview(state.canvas, project, workspace)

    @router.get("/source-status")
    def read_source_status(project: str, workspace: str):
        return source_status(state.canvas, project, workspace)

    @router.post("/realize-source")
    def write_source_realization(payload: dict, request: Request):
        return realize_source(state, payload, actor=request.state.actor)

    @router.post("/autonomy")
    def grant_autonomy(payload: dict, request: Request):
        require_authority(request.state.actor, "Autonomii svěřuje pouze člověk v UI.")
        if request.state.actor == "agent" and isinstance(payload, dict):
            # Atribuce: souhlas agenta s plnou autonomií nese jeho jméno, nikdy „human“.
            payload = {**payload, "grantedBy": f"agent {request.state.agent} (plná autonomie)"[:160]}
        project = payload_project(payload)
        with state.canvas.graph_lock_for(project), state.canvas.lock_for(project):
            return state.set_autonomy(payload)

    @router.post("/confirm-proposals")
    def confirm_sector_proposals(payload: dict, request: Request):
        require_authority(request.state.actor, "Hromadné potvrzení provádí člověk v UI.")
        return confirm_proposals(state, payload, actor=request.state.actor)

    @router.get("/leases")
    def read_leases(project: str, workspace: str):
        return leases.summary(project, workspace)

    @router.post("/lease")
    def write_lease(payload: dict, request: Request):
        return leases.apply(payload, actor=request.state.actor)

    @router.get("/usage-summary")
    def read_usage(project: str, workspace: str):
        return usage_summary(state.canvas, project, workspace)

    @router.get("/assignment-status")
    def read_assignment_status(project: str, workspace: str):
        return assignment_status(state.canvas, project, workspace)

    @router.get("/frontier")
    def read_frontier(project: str, workspace: str, nodeId: str = ""):
        with state.canvas.reading(project):
            graph = state.canvas.view(project, workspace)["graph"]
            stored = state.read(project, workspace)["state"]
            spaces = agent_workspace.read_many(project, workspace, [n["id"] for n in graph["nodes"]])
            linked = pulls.read(state.canvas, project, workspace) or []
            merged = {item["cardId"] for item in linked
                      if item.get("cardId") and item["state"] == "merged" and item.get("planWrittenBack") is True}
            out = frontier(graph, stored, nodeId, {key: value.get("frame", "") for key, value in spaces.items()},
                           leases.summary(project, workspace)["nodes"], merged=merged)
            # Kontrolní pás: co každé kartě chybí (klíče polí), aby relace věděla, co doplnit.
            rows = [row for group in ("frontier", "claimed", "blocked", "waiting", "closed") for row in out[group]]
            lists = checklists(state.canvas, project, workspace, graph, stored, {row["id"] for row in rows})
            for row in rows:
                if row["id"] in lists:
                    row["missing"] = missing(lists[row["id"]])
            return out

    @router.get("/card-checklist")
    def read_card_checklist(project: str, workspace: str, layer: str = ""):
        """Kontrolní pás karet jedné vrstvy (`layer` = rodič, prázdný = kořen) pro plátno."""
        with state.canvas.reading(project):
            view = state.canvas.view(project, workspace)
            if view["readOnly"]:
                return {"nodes": {}}
            graph = view["graph"]
            ids = {n["id"] for n in graph["nodes"] if (n.get("parentId") or "") == layer}
            # Oblast zobrazuje souhrn svých karet: patří na stejnou vrstvu, takže stačí tato sada.
            return {"nodes": checklists(state.canvas, project, workspace, graph, state.read(project, workspace)["state"], ids)}

    @router.post("/assignment-snapshot")
    def write_assignment_snapshot(payload: dict):
        return save_assignment(state.canvas, payload)

    @router.get("/assignment-comparison")
    def read_assignment_comparison(project: str, workspace: str, nodeId: str, id: str, source: str = "result"):
        return assignment_comparison(state.canvas, project, workspace, nodeId, id, source)

    @router.get("/rule")
    def read_rule(project: str, workspace: str, id: str):
        return items.read("rules", project, workspace, id)

    @router.post("/rule")
    def write_rule(payload: dict, request: Request, full: bool = False):
        """Vrací {revision, item}; `?full=1` i celý stav (starší klienti)."""
        return items.apply("rules", payload, actor=request.state.actor, full=full)

    @router.post("/rule-review")
    def review_rule(payload: dict, request: Request, full: bool = False):
        """Člověk schválí (`approve`) nebo zamítne (`reject`) návrh pravidla od agenta; agent 403."""
        return items.review_rule(payload, actor=request.state.actor, full=full)

    @router.post("/rule-review-batch")
    def review_rules(payload: dict, request: Request, full: bool = False):
        """Člověk posoudí víc návrhů agenta naráz: všechno, nebo nic; 409 nese `conflicts` (ID kolizí)."""
        try:
            return items.review_rules(payload, actor=request.state.actor, full=full)
        except BatchConflict as conflict:
            return JSONResponse({"error": str(conflict), "conflicts": conflict.conflicts}, status_code=409)

    @router.get("/decision")
    def read_decision(project: str, workspace: str, id: str):
        return items.read("decisions", project, workspace, id)

    @router.post("/decision")
    def write_decision(payload: dict, request: Request, full: bool = False):
        """Vrací {revision, item}; `?full=1` i celý stav (starší klienti)."""
        return items.apply("decisions", payload, actor=request.state.actor, full=full)

    def _require_lease(payload, request):
        """Kartu drženou cizím lease smí měnit jen držitel tokenu nebo člověk (upgrade-opora #35)."""
        if isinstance(payload, dict):
            leases.require(payload.get("project"), payload.get("workspace"), payload.get("nodeId"),
                           request.state.actor, request.headers.get("x-opora-lease"))

    def remembered(call):
        """Paměť je nejvýš doplněk: každá její chyba se tiše spolkne, uložení už proběhlo."""
        if memory_service is None:
            return
        try:
            call()
        except Exception:  # noqa: BLE001 - zápis do paměti nikdy nesmí shodit uložení
            return

    @router.get("/pipeline-profiles")
    def read_pipeline_profiles():
        return pipeline_profiles()

    @router.post("/pipeline")
    def write_pipeline(payload: dict, request: Request, full: bool = False):
        """Router (orchestrátor) nebo člověk určí proces karty; pravomoci a podlahu hlídá PipelineRouting.
        Vrací {revision, nodeId, stages}; `?full=1` celý stav (starší klienti)."""
        return routing.apply(payload, actor=request.state.actor, agent=getattr(request.state, "agent", ""), full=full)

    @router.get("/state")
    def read_state(project: str, workspace: str, request: Request):
        """Celý stav; ETag z revize a času uložení, `If-None-Match` beze změny → 304 (karta P3)."""
        with state.canvas.reading(project):
            tag = etag_of("state", project, workspace, state.stamp(project, workspace))
            return conditional(request, tag, lambda: state.read(project, workspace))

    @router.post("/state")
    def save_state(payload: dict, request: Request):
        before = set()
        if memory_service is not None and isinstance(payload, dict):
            try:
                before = confirmed_nodes(state.read(payload["project"], payload["workspace"])["state"])
            except Exception:  # noqa: BLE001 - neplatný rozsah vyřeší samo state.save
                before = set()
        saved = state.save(payload, actor=request.state.actor)
        for node_id in sorted(confirmed_nodes(saved["state"]) - before):
            remembered(lambda node_id=node_id: _commit_card(payload, saved, node_id))
        return saved

    @router.post("/node")
    def save_node(payload: dict, request: Request):
        """Štíhlý zápis jedné karty: tělo `nodes[nodeId]`, odpověď {revision, nodeId, node} (oprava 8)."""
        _require_lease(payload, request)
        before = set()
        if memory_service is not None and isinstance(payload, dict):
            try:
                stored = state.read(payload["project"], payload["workspace"])["state"]["nodes"]
                before = confirmed_nodes({"nodes": {payload["nodeId"]: stored.get(payload["nodeId"])}})
            except Exception:  # noqa: BLE001 - neplatný rozsah vyřeší samo state.save_node
                before = set()
        saved = state.save_node(payload, actor=request.state.actor)
        node_id, after = saved["nodeId"], {"nodes": {saved["nodeId"]: saved["node"]}}
        if node_id in confirmed_nodes(after) - before:
            remembered(lambda: _commit_card(payload, {"state": after}, node_id))
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

    @router.get("/pipelines")
    def read_pipelines():
        """Knihovna předloh pro blok Akce; jen čtení z library/pipelines.json."""
        return pipeline_library.load()

    @router.get("/node-brief")
    def read_node_brief(project: str, workspace: str, nodeId: str):
        """Karta jako jeden JSON pro model (opora.node-brief/1); popis stavu, ne příkazy."""
        return {**briefs.build(project, workspace, nodeId), "processSync": brief_metadata(project, workspace, nodeId)}

    @router.post("/agent-output")
    def write_agent_output(payload: dict, request: Request):
        """Výstup modelu (opora.agent-output/1) pod CAS revizí; vrací novou StateResponse."""
        _require_lease(payload, request)
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
    def write_block(payload: dict, request: Request):
        """Operace nad jedním blokem (add/update/remove/todo) pod CAS revizí; vrací StateResponse + block."""
        _require_lease(payload, request)
        return block_access.apply(payload, actor=request.state.actor)

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
