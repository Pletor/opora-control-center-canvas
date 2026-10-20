"""Směrování pipeline karty (`POST /api/desktop-v3/pipeline`): router nebo člověk určí proces karty.

`op: "route"` sestaví pipeline ze šablony profilu (+ volitelné etapy navíc), `op: "add"` přidá
etapy za rozpracovanou část, `op: "retry"` (+ `stageId`) znovu zařadí zaseknutou etapu (oprava + opakování). Agent podléhá pravomocem a podlaze z `card_pipeline`; člověk smí
vše (i profil `custom` bez podlahy). Zápis jde přes `DesktopV3State.save` pod CAS revizí.

Odpověď nese jen `revision`, `nodeId` a novou pipeline karty `stages` (karta P3); `full=True`
(HTTP `?full=1`) vrátí kvůli starším klientům celý stav.
"""

import copy

from backend.canvas.graph import valid_id
from backend.editor.agent_memory import card_pipeline as pipeline
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_done
from backend.editor.agent_packet.frontier import ticket_type

PAYLOAD_KEYS = {"project", "workspace", "nodeId", "expectedRevision", "op", "reason"}
OPTIONAL_KEYS = {"profile", "stages", "stageId"}


def profiles():
    """Šablony profilů pro UI a router; jediný zdroj pravdy je `card_pipeline.TEMPLATES`."""
    return {"profiles": [{"id": profile, "stages": copy.deepcopy(pipeline.TEMPLATES[profile])}
                         for profile in pipeline.PROFILES],
            "floor": ["review", "critic hacker", "test for [task] cards and cards with checks"],
            "maxRetries": pipeline.MAX_RETRIES}


def _validate(payload):
    if not isinstance(payload, dict) or not PAYLOAD_KEYS <= set(payload) <= PAYLOAD_KEYS | OPTIONAL_KEYS:
        raise ValueError("Neplatné směrování pipeline: project, workspace, nodeId, expectedRevision, op, reason, profile?, stages?, stageId?.")
    if payload["op"] not in ("route", "add", "retry"):
        raise ValueError("op musí být route, add nebo retry.")
    if (payload["op"] == "retry") != ("stageId" in payload) or (payload["op"] == "retry" and (
            not isinstance(payload["stageId"], str) or not valid_id(payload["stageId"]) or payload.get("stages"))):
        raise ValueError("retry potřebuje stageId zaseknuté etapy (a nic jiného); stageId patří jen k retry.")
    if not valid_id(payload["nodeId"]) or type(payload["expectedRevision"]) is not int:
        raise ValueError("Neplatný uzel nebo revize.")
    if not isinstance(payload["reason"], str) or not payload["reason"].strip() or len(payload["reason"]) > pipeline.MAX_TEXT:
        raise ValueError("reason je jedna věta s fakty, proč tento proces.")
    if payload["op"] == "route" and payload.get("profile") not in pipeline.PROFILES:
        raise ValueError("route potřebuje profile: " + ", ".join(pipeline.PROFILES) + ".")
    if payload["op"] == "add" and not payload.get("stages"):
        raise ValueError("add potřebuje neprázdné stages.")
    pipeline.validate_templates(payload.get("stages", []))


class PipelineRouting:
    def __init__(self, canvas, state_store=None):
        self.canvas = canvas
        self.state = state_store or DesktopV3State(canvas)

    def apply(self, payload, *, actor, agent="", full=False):
        _validate(payload)
        project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        human = actor == "human"
        by = "human" if human else "agent"
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            graph = self.canvas.view(project, workspace)["graph"]
            graph_node = next((n for n in graph["nodes"] if n["id"] == node_id), None)
            if graph_node is None or graph_node.get("kind") != "node":
                raise ValueError("Pipeline lze nasměrovat jen existující kartě.")
            stored = self.state.read(project, workspace)
            if stored["revision"] != payload["expectedRevision"]:
                raise ValueError("Stav se změnil (revize nesouhlasí); načtěte frontier znovu.")
            # Mění se jen jeden uzel: kopie jen jeho, ostatní uzly zůstávají sdílené s uloženým stavem.
            state = {**stored["state"], "nodes": dict(stored["state"]["nodes"])}
            node = copy.deepcopy(state["nodes"].get(node_id, {"phase": "discover", "criteria": [], "steps": []}))
            if node.get("done", default_done())["confirmed"]:
                raise ValueError("Karta je uzavřená; pipeline je jen ke čtení.")
            current = node.get("stages")
            extra = [pipeline.new_stage(template, by) for template in payload.get("stages", [])]
            if payload["op"] == "route":
                if not human and current and current["items"] and (
                        current.get("routedBy", "human") == "human"
                        or any(item["status"] != "todo" for item in current["items"])):
                    from backend.canvas.activity_log import HumanRequired
                    raise HumanRequired(actor, "Rozpracovanou pipeline nebo pipeline od člověka přestaví jen člověk; přidejte etapy (op add).")
                goal = graph_node.get("goal_mode") == "until_checks_pass"
                value = {"profile": payload["profile"],
                         "items": pipeline.profile_stages(payload["profile"], goal, by) + extra,
                         "routedBy": "human" if human else (agent or "agent"), "reason": payload["reason"]}
            elif payload["op"] == "retry":
                if not current or not current["items"]:
                    raise ValueError("Karta nemá pipeline; nejprve ji nasměrujte (op route).")
                value = copy.deepcopy(current)
                if not pipeline.retry_stuck(value, payload["stageId"]):
                    if human:
                        raise ValueError(f"Smyčky oprav došly ({pipeline.MAX_RETRIES}); etapu přeskočte nebo upravte pipeline.")
                    from backend.canvas.activity_log import HumanRequired
                    raise HumanRequired(actor, f"Smyčky oprav došly ({pipeline.MAX_RETRIES}); rozhoduje člověk.")
            else:
                if not current or not current["items"]:
                    raise ValueError("Karta nemá pipeline; nejprve ji nasměrujte (op route).")
                value = copy.deepcopy(current)
                items = value["items"]
                last_started = max((i for i, item in enumerate(items) if item["status"] != "todo"), default=-1)
                items[last_started + 1:last_started + 1] = extra
            if not value["items"]:
                raise ValueError("Pipeline nemá žádnou etapu; vyberte profil nebo přidejte etapy.")
            if not human and payload["op"] == "route":
                missing = pipeline.floor_missing(pipeline.active(value), graph_node, ticket_type(graph_node.get("name")))
                if missing:
                    raise ValueError("Pipeline od agenta nesplňuje podlahu, chybí: " + ", ".join(missing) + ".")
            pipeline.validate_stages(value)
            node["stages"] = value
            state["nodes"][node_id] = node
            saved = self.state.save({"project": project, "workspace": workspace,
                                     "expectedRevision": payload["expectedRevision"], "state": state},
                                    base=stored["state"], slim=not full, execution_actor=actor)
            return saved if full else {**saved, "nodeId": node_id, "stages": value}
