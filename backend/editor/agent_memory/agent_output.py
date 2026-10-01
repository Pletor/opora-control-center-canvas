"""Výstup modelu (`opora.agent-output/1`): jeden zápis do paměti Desktop v3 pod CAS revizí.

Kontrakt je `docs/karta-pro-agenty.md`, sekce „Výstup modelu“. Agent hlásí stav bloků,
zprávy na vazbách, návrh uzavření karty a rozhodnutí; server je zapíše vždy s `by: "agent"`.
Uzavřená karta (`done.confirmed`) výstup odmítne, neznámý `blockId` nebo `edgeId` je chyba
a nezapíše se nic: mutuje se kopie stavu a teprve celek jde přes `DesktopV3State.save`,
která drží zámek i CAS na revizi.

`blocks[].note` je součást tvaru výstupu, ale datový model karty pro něj nemá místo:
ověří se a dál se nenese. Poznámka agenta patří do zprávy na vazbě.
"""

import copy
import uuid

from backend.canvas.canvas_service import now
from backend.canvas.graph import valid_id
from backend.editor.agent_memory.desktop_v3_state import (
    MAX_AGENT,
    MAX_BLOCKS,
    MAX_ITEMS,
    MAX_SUBITEMS,
    MAX_TEXT,
    DesktopV3State,
    default_done,
)

SCHEMA = "opora.agent-output/1"
PAYLOAD_KEYS = {"project", "workspace", "nodeId", "expectedRevision", "agent", "output"}
OUTPUT_KEYS = {"schema", "blocks", "reports", "done", "decisions"}
BLOCK_KEYS = {"blockId", "status", "note"}
REPORT_KEYS = {"edgeId", "log", "summary", "handoff", "improvements", "errors"}
REPORT_TEXTS = ("log", "summary", "handoff", "improvements", "errors")
DONE_KEYS = {"proposed", "note"}
STATUSES = ("met", "unmet", "blocked")


def output_json_schema():
    """Typový popis pro model; existence ID, duplicity a CAS stále ověřuje server."""
    def record(properties):
        return {"type": "object", "properties": properties,
                "required": list(properties), "additionalProperties": False}

    text = {"type": "string", "maxLength": MAX_TEXT, "pattern": "^[^\\u0000]*$"}
    identity = {"type": "string", "minLength": 1, "maxLength": 80,
                "pattern": r"^[A-Za-z0-9_-]+(?![\s\S])"}
    return record({
        "schema": {"type": "string", "const": SCHEMA},
        "blocks": {"type": "array", "maxItems": MAX_BLOCKS, "items": record({
            "blockId": identity, "status": {"type": "string", "enum": list(STATUSES)},
            "note": text,
        })},
        "reports": {"type": "array", "maxItems": MAX_SUBITEMS, "items": record({
            "edgeId": identity, **{key: text for key in REPORT_TEXTS},
        })},
        "done": record({"proposed": {"type": "boolean"}, "note": text}),
        "decisions": {"type": "array", "maxItems": MAX_ITEMS,
                      "items": {**text, "minLength": 1, "pattern": r"^[^\u0000]*[^\s\u0000][^\u0000]*$"}},
    })


def _fail(message):
    raise ValueError("Neplatný výstup agenta: " + message)


def _text(value, limit, label, allow_empty=True):
    if not isinstance(value, str) or "\0" in value or len(value) > limit:
        _fail(f"{label} musí být text do {limit} znaků.")
    if not allow_empty and not value.strip():
        _fail(f"{label} nesmí být prázdný.")
    return value


def _unique(values, label):
    if len(set(values)) != len(values):
        _fail(f"{label} se v jednom výstupu opakuje.")
    return values


def validate_output(payload):
    """Tvar celého požadavku; identity se proti grafu a kartě ověřují až v `apply`."""
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_KEYS:
        _fail("očekávám project, workspace, nodeId, expectedRevision, agent a output.")
    project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
    if not isinstance(project, str) or (project != "draft" and not valid_id(project)) or not valid_id(workspace):
        _fail("neplatný identifikátor projektu nebo pracovního prostoru.")
    if not valid_id(node_id):
        _fail("neplatný identifikátor uzlu.")
    if type(payload["expectedRevision"]) is not int or payload["expectedRevision"] < 0:
        _fail("expectedRevision musí být revize stavu, kterou agent četl.")
    _text(payload["agent"], MAX_AGENT, "označení agenta")
    output = payload["output"]
    if not isinstance(output, dict) or set(output) != OUTPUT_KEYS:
        _fail("output musí mít schema, blocks, reports, done a decisions.")
    if output["schema"] != SCHEMA:
        _fail(f"schema výstupu musí být {SCHEMA}.")
    blocks = output["blocks"]
    if not isinstance(blocks, list) or len(blocks) > MAX_BLOCKS:
        _fail(f"blocks musí být pole nejvýše {MAX_BLOCKS} položek.")
    for item in blocks:
        if not isinstance(item, dict) or set(item) != BLOCK_KEYS:
            _fail("položka blocks musí mít blockId, status a note.")
        if not valid_id(item["blockId"]):
            _fail("blockId má neplatný identifikátor.")
        if item["status"] not in STATUSES:
            _fail("status bloku musí být met, unmet nebo blocked.")
        _text(item["note"], MAX_TEXT, "poznámka k bloku")
    _unique([item["blockId"] for item in blocks], "blockId")
    reports = output["reports"]
    if not isinstance(reports, list) or len(reports) > MAX_SUBITEMS:
        _fail(f"reports musí být pole nejvýše {MAX_SUBITEMS} zpráv.")
    for item in reports:
        if not isinstance(item, dict) or set(item) != REPORT_KEYS:
            _fail("zpráva musí mít edgeId, log, summary, handoff, improvements a errors.")
        if not valid_id(item["edgeId"]):
            _fail("edgeId má neplatný identifikátor.")
        for key in REPORT_TEXTS:
            _text(item[key], MAX_TEXT, f"{key} zprávy na vazbě")
    _unique([item["edgeId"] for item in reports], "edgeId")
    done = output["done"]
    if not isinstance(done, dict) or set(done) != DONE_KEYS:
        _fail("done musí mít proposed a note.")
    if type(done["proposed"]) is not bool:
        _fail("done.proposed musí být true/false.")
    _text(done["note"], MAX_TEXT, "poznámka k uzavření")
    decisions = output["decisions"]
    if not isinstance(decisions, list) or len(decisions) > MAX_ITEMS:
        _fail(f"decisions musí být pole nejvýše {MAX_ITEMS} textů.")
    for item in decisions:
        _text(item, MAX_TEXT, "text rozhodnutí", allow_empty=False)
    return payload


class AgentOutput:
    def __init__(self, canvas, state_store=None):
        self.canvas = canvas
        self.state = state_store or DesktopV3State(canvas)

    def apply(self, payload):
        """Zapíše výstup agenta do stavu a vrátí novou StateResponse; při chybě nezapíše nic."""
        validate_output(payload)
        project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        expected, output = payload["expectedRevision"], payload["output"]
        with self.canvas.graph_lock:
            graph = self.canvas.view(project, workspace)["graph"]
            if not any(item["id"] == node_id for item in graph["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            stored = self.state.read(project, workspace)
            if stored["readOnly"]:
                raise ValueError("Main je pouze pro čtení; výstup agenta patří do pracovního prostoru.")
            if stored["revision"] != expected:
                raise ValueError("Stav se změnil (revize nesouhlasí); načtěte kartu znovu.")
            state = copy.deepcopy(stored["state"])
            # Karta bez uloženého stavu vzniká až tím, co se do ní opravdu zapíše.
            node = state["nodes"].get(node_id, {"phase": "discover", "criteria": [], "steps": []})
            if node.get("done", default_done())["confirmed"]:
                raise ValueError("Karta je uzavřená; výstup agenta se do ní nezapisuje.")
            stamp = now()
            by_block = {item["id"]: item for item in node.get("blocks", [])}
            for item in output["blocks"]:
                block = by_block.get(item["blockId"])
                if block is None:
                    raise ValueError(f"Blok {item['blockId']} na kartě {node_id} neexistuje.")
                block["state"]["status"] = item["status"]
            # Zprávu smí odeslat jen zdroj vazby; příjemce nesmí přepsat předávku předchůdce.
            edge_ids = {edge["id"] for edge in graph["edges"] if edge["source"] == node_id}
            written = state.setdefault("edges", {})
            for item in output["reports"]:
                if item["edgeId"] not in edge_ids:
                    raise ValueError(f"Vazba {item['edgeId']} v tomto pracovním prostoru neexistuje.")
                written[item["edgeId"]] = {
                    **{key: item[key] for key in REPORT_TEXTS},
                    "updatedAt": stamp, "by": "agent", "agent": payload["agent"],
                }
            # Agent smí uzavření karty jen navrhnout; potvrzení zapisuje člověk.
            if output["done"]["proposed"]:
                node["done"] = {"confirmed": False, "at": stamp, "by": "agent", "note": output["done"]["note"]}
                state["nodes"][node_id] = node
            for text in output["decisions"]:
                state["decisions"].append({
                    "id": uuid.uuid4().hex, "text": text, "pinned": False, "path": "",
                    "nodeId": node_id, "createdAt": stamp, "by": "agent",
                })
            return self.state.save({
                "project": project, "workspace": workspace,
                "expectedRevision": expected, "state": state,
            })
