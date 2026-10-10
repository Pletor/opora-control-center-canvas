"""Výstup modelu (`opora.agent-output/1`): jeden zápis do paměti Desktop v3 pod CAS revizí.

Kontrakt je `docs/karta-pro-agenty.md`, sekce „Výstup modelu“. Agent hlásí stav bloků,
zprávy na vazbách, návrh uzavření karty a rozhodnutí; server je zapíše vždy s `by: "agent"`.
Uzavřená karta (`done.confirmed`) výstup odmítne, neznámý `blockId` nebo `edgeId` je chyba
a nezapíše se nic: mutuje se kopie stavu a teprve celek jde přes `DesktopV3State.save`,
která drží zámek i CAS na revizi.

Původní výstup včetně `blocks[].note` se uchová v neměnné historii výsledků. Volitelný
contextVersion váže výsledek k přesnému zadání; staré požadavky jsou legacy-unbound.
"""

import copy
import uuid

from backend.canvas.canvas_service import now
from backend.canvas.gate_scenario import run_schema, validate_run
from backend.canvas.graph import valid_id
from backend.editor.agent_memory.agent_results import AgentResults, result_record
from backend.editor.agent_memory.autonomy import authorize_close
from backend.editor.agent_memory.card_ideas import (
    MAX_IDEA_TEXT,
    MAX_OUTPUT_IDEAS,
    merge_ideas,
    validate_output_ideas,
)
from backend.editor.agent_memory.card_pipeline import apply_reports, validate_reports
from backend.editor.agent_memory.completion_evidence import evidence_json_schema, validate_evidence
from backend.editor.agent_memory.desktop_v3_state import (
    MAX_AGENT,
    MAX_BLOCKS,
    MAX_ITEMS,
    MAX_SUBITEMS,
    MAX_TEXT,
    DesktopV3State,
    default_done,
)
from backend.editor.agent_memory.work_activity import record_activity, validate_touched
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from backend.editor.agent_packet.sector_status import sector_blockers
from backend.editor.agent_packet.specification_context import capture_specification

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
    schema = record({
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
    schema["properties"]["usage"] = {
        "type": "object", "additionalProperties": False,
        "properties": {key: {"type": ["integer", "null"], "minimum": 0, "maximum": 9_007_199_254_740_991}
                       for key in ("tokens", "durationMs", "attempts")},
    }
    schema["properties"]["ports"] = {"type": "array", "maxItems": MAX_SUBITEMS, "items": record({
        "blockId": identity, "portId": identity,
        "status": {"type": "string", "enum": ["chosen", "rejected"]},
        "reason": {**text, "minLength": 1},
    })}
    schema["properties"]["done"]["properties"]["confirmed"] = {"type": "boolean"}
    schema["properties"]["evidence"] = evidence_json_schema()
    schema["properties"]["scenarioRun"] = run_schema()
    schema["properties"]["stages"] = {"type": "array", "maxItems": 40, "items": record({
        "id": identity, "status": {"type": "string", "enum": ["doing", "passed", "failed"]}, "note": text,
    })}
    schema["properties"]["ideas"] = {"type": "array", "maxItems": MAX_OUTPUT_IDEAS, "items": record({
        "text": {**text, "minLength": 1, "maxLength": MAX_IDEA_TEXT},
        "source": {"type": "string", "pattern": "^(human|agent|review|work|test|fix|critic:(user|sly|hacker))$"},
        "fragmentId": identity,
    })}
    # fragmentId (fragment schránky zadání) je u podnětu volitelné.
    schema["properties"]["ideas"]["items"]["required"] = ["text", "source"]
    schema["properties"]["touched"] = {"type": "array", "maxItems": 500, "uniqueItems": True, "items": {"type": "string", "minLength": 1, "maxLength": 2048}}
    return schema


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
    # contextVersion je povinný (upgrade-opora #36): bez něj by šlo zastaralé zadání obejít tím,
    # že ho agent nepošle. Staré záznamy bez vazby zůstávají v historii jako legacy-unbound.
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_KEYS | {"contextVersion"}:
        _fail("očekávám project, workspace, nodeId, expectedRevision, contextVersion (z node-briefu), agent a output.")
    version = payload["contextVersion"]
    if not isinstance(version, str) or len(version) != 64 or any(c not in "0123456789abcdef" for c in version):
        _fail("contextVersion musí být otisk zadání z aktuálního node-briefu.")
    project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
    if not isinstance(project, str) or (project != "draft" and not valid_id(project)) or not valid_id(workspace):
        _fail("neplatný identifikátor projektu nebo pracovního prostoru.")
    if not valid_id(node_id):
        _fail("neplatný identifikátor uzlu.")
    if type(payload["expectedRevision"]) is not int or payload["expectedRevision"] < 0:
        _fail("expectedRevision musí být revize stavu, kterou agent četl.")
    _text(payload["agent"], MAX_AGENT, "označení agenta")
    output = payload["output"]
    if not isinstance(output, dict) or set(output) - {"usage", "ports", "evidence", "touched", "scenarioRun", "stages", "ideas"} != OUTPUT_KEYS:
        _fail("output musí mít schema, blocks, reports, done a decisions.")
    if "touched" in output:
        validate_touched(output["touched"])
    if "scenarioRun" in output:
        validate_run(output["scenarioRun"])
    if "stages" in output:
        validate_reports(output["stages"])
    if "ideas" in output:
        validate_output_ideas(output["ideas"])
    if "usage" in output:
        usage = output["usage"]
        if not isinstance(usage, dict) or set(usage) - {"tokens", "durationMs", "attempts"}:
            _fail("usage smí mít jen tokens, durationMs a attempts.")
        if any(value is not None and (type(value) is not int or not 0 <= value <= 9_007_199_254_740_991)
               for value in usage.values()):
            _fail("údaje usage musí být nezáporná celá čísla nebo null (nedostupné).")
    if output["schema"] != SCHEMA:
        _fail(f"schema výstupu musí být {SCHEMA}.")
    if "evidence" in output:
        validate_evidence(output["evidence"])
    ports = output.get("ports", [])
    if not isinstance(ports, list) or len(ports) > MAX_SUBITEMS:
        _fail("ports musí být omezené pole rozhodnutí portů.")
    for port in ports:
        if not isinstance(port, dict) or set(port) != {"blockId", "portId", "status", "reason"}:
            _fail("Rozhodnutí portu musí mít blockId, portId, status a reason.")
        if not valid_id(port["blockId"]) or not valid_id(port["portId"]) or port["status"] not in ("chosen", "rejected"):
            _fail("Neplatná identita nebo stav portu.")
        _text(port["reason"], MAX_TEXT, "důvod rozhodnutí portu", allow_empty=False)
    _unique([(port["blockId"], port["portId"]) for port in ports], "port")
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
    if not isinstance(done, dict) or set(done) not in (DONE_KEYS, DONE_KEYS | {"confirmed"}):
        _fail("done musí mít proposed a note.")
    if type(done["proposed"]) is not bool:
        _fail("done.proposed musí být true/false.")
    if "confirmed" in done and (type(done["confirmed"]) is not bool or (done["confirmed"] and not done["proposed"])):
        _fail("done.confirmed musí být boolean; uzavření musí mít proposed=true.")
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
        self.results = AgentResults(canvas)

    def apply(self, payload):
        """Zapíše výstup agenta do stavu a vrátí novou StateResponse; při chybě nezapíše nic."""
        validate_output(payload)
        project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        expected, output = payload["expectedRevision"], payload["output"]
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            graph = self.canvas.view(project, workspace)["graph"]
            if not any(item["id"] == node_id for item in graph["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            stored = self.state.read(project, workspace)
            if sector_blockers(graph, stored["state"], node_id):
                raise ValueError("Výsledek nelze přijmout: předchozí sektor ještě není ověřený.")
            if stored["readOnly"]:
                raise ValueError("Main je pouze pro čtení; výstup agenta patří do pracovního prostoru.")
            if stored["revision"] != expected:
                raise ValueError("Stav se změnil (revize nesouhlasí); načtěte kartu znovu.")
            captured = capture_specification(self.canvas, project, workspace, node_id) if "contextVersion" in payload else None
            if captured and captured["contextVersion"] != payload["contextVersion"]:
                raise ValueError("Zadání nebo jeho kontext se změnily (contextVersion nesouhlasí). "
                                 "Výsledek nebyl uložen; zachovejte rozepsaný výstup a načtěte nové zadání.")
            state = copy.deepcopy(stored["state"])
            # Karta bez uloženého stavu vzniká až tím, co se do ní opravdu zapíše.
            node = state["nodes"].get(node_id, {"phase": "discover", "criteria": [], "steps": []})
            if node.get("done", default_done())["confirmed"]:
                raise ValueError("Karta je uzavřená; výstup agenta se do ní nezapisuje.")
            stamp = now()
            if "scenarioRun" in output:
                graph_node = next(n for n in graph["nodes"] if n["id"] == node_id)
                if output["scenarioRun"]["command"] != graph_node.get("scenario", {}).get("command"):
                    raise ValueError("Příkaz běhu neodpovídá aktuálnímu scénáři karty.")
                node["scenarioRun"] = copy.deepcopy(output["scenarioRun"])
                state["nodes"][node_id] = node
            if "evidence" in output:
                node["evidence"] = copy.deepcopy(output["evidence"])
                state["nodes"][node_id] = node
            if output.get("stages"):
                # Pipeline karty: stav schválené etapy hlásí agent jen tudy (pořadí, nezávislost, GOAL).
                graph_node = next(n for n in graph["nodes"] if n["id"] == node_id)
                apply_reports(node.get("stages"), output["stages"], payload["agent"], stamp,
                              graph_node, node.get("evidence"))
                state["nodes"][node_id] = node
            if output.get("ideas"):
                # Ne-blokující nálezy (review, kritici): podněty k dalšímu vývoji, etapu nezastaví.
                closed = [item["id"] for item in output.get("stages", []) if item["status"] != "doing"]
                node["ideas"] = merge_ideas(node.get("ideas"), output["ideas"], payload["agent"], stamp,
                                            closed[0] if closed else "")
                state["nodes"][node_id] = node
            by_block = {item["id"]: item for item in node.get("blocks", [])}
            for item in output.get("ports", []):
                block = by_block.get(item["blockId"], {})
                port = next((p for p in block.get("ports", []) if p["id"] == item["portId"]), None)
                if port is None:
                    raise ValueError("Port rozhodnutí na této kartě neexistuje.")
                port.update(status=item["status"], reason=item["reason"])
            for item in output["blocks"]:
                block = by_block.get(item["blockId"])
                if block is None:
                    raise ValueError(f"Blok {item['blockId']} na kartě {node_id} neexistuje.")
                block["state"]["status"] = item["status"]
                block["state"]["note"] = item["note"]
            # Zprávu smí odeslat jen zdroj vazby; příjemce nesmí přepsat předávku předchůdce.
            edge_ids = {edge["id"] for edge in graph["edges"] if edge["source"] == node_id}
            written = state.setdefault("edges", {})
            for item in output["reports"]:
                if item["edgeId"] not in edge_ids:
                    raise ValueError(f"Vazba {item['edgeId']} v tomto pracovním prostoru neexistuje.")
                previous = written.get(item["edgeId"], {})
                report = {
                    **{key: item[key] for key in REPORT_TEXTS},
                    "updatedAt": stamp, "by": "agent", "agent": payload["agent"],
                }
                # `sentAt` a `due` agent neposílá: termín převzetí se přenese ze stávající zprávy
                # a čas předání se posune jen tehdy, když agent mění neprázdný `handoff`.
                for key in ("sentAt", "due"):
                    if key in previous:
                        report[key] = previous[key]
                if item["handoff"].strip() and item["handoff"] != previous.get("handoff"):
                    report["sentAt"] = stamp
                written[item["edgeId"]] = report
            # Agent smí uzavření karty jen navrhnout; potvrzení zapisuje člověk.
            if output["done"]["proposed"]:
                node["done"] = {"confirmed": False, "at": stamp, "by": "agent", "note": output["done"]["note"]}
                state["nodes"][node_id] = node
            autonomous = output["done"].get("confirmed", False)
            if autonomous:
                authorize_close(graph, state, node_id, stamp, stored["state"])
                node["done"] = {"confirmed": True, "at": stamp, "by": "autonomy", "note": output["done"]["note"]}
            for text in output["decisions"]:
                state["decisions"].append({
                    "id": uuid.uuid4().hex, "text": text, "pinned": False, "path": "",
                    "nodeId": node_id, "createdAt": stamp, "by": "agent",
                })
            record = result_record(payload, captured)
            def after_write(db):
                self.results.insert(db, project, workspace, record)
                record_activity(db, project, workspace, node_id, payload["agent"], stamp, touched=output.get("touched"))
            saved = self.state.save({
                "project": project, "workspace": workspace,
                "expectedRevision": expected, "state": state,
            }, after_write=after_write,
                autonomy_close={node_id} if autonomous else frozenset())
            return {**saved, "acceptedResult": redact_deep(record)}
