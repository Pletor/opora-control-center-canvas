"""Desktop v3 paměť projektu a stav uzlů: jedna revizovaná pravda v SQLite.

State = {settings, rules, decisions, nodes, tickets, edges}. Prázdné pole/objekt jsou výchozí
hodnoty; žádná demo data. Fáze uzlu je plánovací stav člověka, nikoli důkaz testů či
nasazení: postup vpřed vyžaduje neprázdná splněná kritéria, opačný směr je volný.

`edges` je sekce zpráv agenta na vazbách grafu (log, souhrn, předání, zlepšení, chyby);
uzel navíc nese `done` (uzavření karty), `agentRole` (která role agenta si tuhle práci
pamatuje napříč projekty), blok `ports` (tlačítka, z nichž vede vazba na jinou kartu), `ideas`
(podněty k dalšímu vývoji, `card_ideas.py`), `fragmentRefs` (z čeho ve schránce zadání karta
vznikla, `backend/editor/brief_vault/brief_vault_refs.py`), `round` (starší číslo kola karty, jen ke čtení; kola jsou zrušená, `card_round_legacy.py`)
a značky struktury Schránky `briefGroup` / `briefDiscipline` (oblast skupiny a sektor disciplíny, `brief_vault_marks.py`).
Všechny tyto klíče jsou volitelné, aby starší uložený stav zůstal platný.
"""

import copy
import functools
import json
import re
from datetime import datetime, timedelta

from backend.canvas.authority import acts_as_human
from backend.canvas.canvas_service import now
from backend.canvas.graph import valid_date, valid_id
from backend.memory.roles import role_ids
from backend.project.workspace.workspace_sources import relative_path

PHASES = ("discover", "define", "build", "verify", "live")
RULE_KINDS = ("must", "must_not")
RULE_SCOPES = ("project", "path", "node")
ACTORS = ("human", "agent")
# Uzavření karty navíc zná „autonomy“: potvrdil agent v sektoru, kterému člověk svěřil autonomii.
DONE_ACTORS = ("human", "agent", "autonomy")
PRIORITIES = ("low", "normal", "high")
STATUSES = ("open", "doing", "done")

MAX_ITEMS = 500
MAX_NODES = 2000
MAX_SUBITEMS = 200
MAX_TEXT = 4000
MAX_KEY = 120
MAX_TITLE = 400

SETTING_KEYS = {"id", "key", "value"}
RULE_KEYS = {"id", "text", "kind", "scope", "target"}
# `by` = původce pravidla. Chybí = člověk (starší stav). Pravidlo od agenta je jen návrh:
# do effectiveRules a stopConditions jde až po schválení člověkem (upgrade-opora #37).
RULE_AUTHORS = ("human", "agent")
DECISION_KEYS = {"id", "text", "pinned", "path", "nodeId", "createdAt", "by"}
# Volitelné klíče rozhodnutí: `supersedes` (oprava) a `executionId` (zapsal ho výsledek běhu OporaHubu).
DECISION_KEY_SETS = tuple(DECISION_KEYS | set(extra) for extra in ((), ("supersedes",), ("executionId",),
                                                                   ("supersedes", "executionId")))
NODE_KEYS = {"phase", "criteria", "steps"}
CRITERION_KEYS = {"id", "text", "checked"}
STEP_KEYS = {"id", "text", "assignee", "done"}
ACTION_KEYS = {"id", "pipelineId", "label", "params"}
NODE_RULE_KEYS = {"id", "text", "kind"}
MAX_PARAMS = 50
# Strom obsahu uzlu: očíslované bloky s vlastním stavem a větvením; každá entita má stabilní ID.
BLOCK_KEYS = {"id", "number", "title", "text", "tags", "todos", "images", "state", "parentBlockId"}
# Tlačítka bloku: z každého portu se táhne vazba `port: "block"` na jinou kartu.
# Starší blok `ports` nemá a čte se jako prázdné pole.
PORT_KEYS = {"id", "label"}
BLOCK_KEY_SETS = (frozenset(BLOCK_KEYS), frozenset(BLOCK_KEYS) | {"ports"})
MAX_PORTS = 8
MAX_PORT_LABEL = 80
TODO_KEYS = {"id", "text", "done", "assignee"}
IMAGE_KEYS = {"id", "path", "caption"}
STATE_BLOCK_KEYS = {"status", "condition", "onMet", "onUnmet"}
BRANCH_KEYS = {"kind", "targetId", "note"}
# Podklady z portu karty: nahraný obrázek (upload = jméno souboru ve složce projektu),
# odkaz do zdroje projektu (source = relativní cesta) nebo URL (link).
MATERIAL_KEYS = {"id", "kind", "path", "caption"}
MATERIAL_KINDS = ("upload", "source", "link")
MAX_MATERIALS = 50
MAX_URL = 2000
# Jméno nahraného podkladu: node_materials.save_upload ukládá `YYYYMMDD-HHMMSS-<8 hex>.<přípona>`;
# starší podklady mají 32 hex znaků. Obě podoby jsou platné, nic jiného (žádné cesty).
UPLOAD_FILE = re.compile(r"(?:[a-f0-9]{32}|[0-9]{8}-[0-9]{6}-[a-f0-9]{8})\.(png|jpg|gif|webp|svg)")
BLOCK_STATUSES = ("open", "met", "unmet", "blocked")
BRANCH_KINDS = ("block", "node", "action", "none")
MAX_BLOCKS = 200
MAX_TODOS = 100
MAX_IMAGES = 20
MAX_TAGS = 20
MAX_TAG = 40
MAX_BLOCK_TEXT = 12000
NUMBER = re.compile(r"[0-9]+(\.[0-9]+)*")


# Uzavření karty: člověk ji potvrzuje, agent ji smí jen navrhnout.
DONE_KEYS = {"confirmed", "at", "by", "note"}
# Zpráva agenta na vazbě: pět pojmenovaných textů, čas, původce a označení agenta.
EDGE_REPORT_KEYS = {"log", "summary", "handoff", "improvements", "errors", "updatedAt", "by", "agent"}
EDGE_REPORT_TEXTS = ("log", "summary", "handoff", "improvements", "errors")
# Volitelná pole zprávy (kontrakt `docs/kontext-karet-a-index.md` §4): `sentAt` je čas posledního
# předání neprázdného `handoff` (nastavuje ho aplikace, ne člověk ani agent), `due` je termín
# převzetí `YYYY-MM-DD` nebo "". Starší zprávy bez nich zůstávají platné.
EDGE_REPORT_OPTIONAL = ("sentAt", "due")
MAX_EDGE_REPORTS = 4000
MAX_AGENT = 120


@functools.cache
def _node_key_sets():
    """Volitelné klíče uzlu; `actions` a `rules` chodí vždy spolu, zbytek nezávisle.
    Sad je 2^14; spočítají se jednou a hledá se v množině, ne v n-tici."""
    sets = (frozenset(NODE_KEYS), frozenset(NODE_KEYS) | {"actions", "rules"})
    for optional in ("blocks", "materials", "done", "agentRole", "evidence", "scenarioRun", "downloadsUrl", "stages", "ideas", "fragmentRefs", "round",
                     "briefGroup", "briefDiscipline"):
        sets = sets + tuple(item | {optional} for item in sets)
    return frozenset(sets)
TICKET_KEYS = {"id", "title", "priority", "status", "nodeId", "sessionId", "createdBy"}
STATE_KEYS = {"settings", "rules", "decisions", "nodes", "tickets"}
STATE_KEY_SETS = tuple(frozenset(STATE_KEYS) | extra for extra in (set(), {"edges"}, {"autonomy"}, {"edges", "autonomy"}))
# Svěřená autonomie sektoru: {sectorId: {until, grantedAt, note}}; zapisuje jen člověk přes /autonomy.
AUTONOMY_KEYS = {"until", "grantedAt", "note"}
AUTONOMY_SAVE_KEYS = {"project", "workspace", "expectedRevision", "sectorId", "until", "note"}
MAX_AUTONOMY_DAYS = 30
SAVE_KEYS = {"project", "workspace", "expectedRevision", "state"}
NODE_SAVE_KEYS = {"project", "workspace", "expectedRevision", "nodeId", "node"}


def default_done():
    return {"confirmed": False, "at": "", "by": "human", "note": ""}


def default_state():
    return {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": [], "edges": {}}


def fill_defaults(state):
    """Starší uložený stav bez `edges` se čte jako prázdná sekce zpráv; zápis zůstává nedotčený."""
    if isinstance(state, dict) and "edges" not in state:
        return {**state, "edges": {}}
    return state


def _fail(message):
    raise ValueError("Neplatný stav Desktop v3: " + message)


def _text(value, limit, label, allow_empty=False):
    if not isinstance(value, str) or "\0" in value or len(value) > limit:
        _fail(f"{label} musí být text do {limit} znaků.")
    if not allow_empty and not value.strip():
        _fail(f"{label} nesmí být prázdný.")
    return value


def _ident(value, label):
    if not valid_id(value):
        _fail(f"{label} má neplatný identifikátor.")
    return value


def _optional_ident(value, label):
    if value == "":
        return value
    return _ident(value, label)


def _bool(value, label):
    if type(value) is not bool:
        _fail(f"{label} musí být true/false.")
    return value


def _enum(value, allowed, label):
    if not isinstance(value, str) or value not in allowed:
        _fail(f"{label} musí být jedna z hodnot {', '.join(allowed)}.")
    return value


def _items(value, keys, limit, label):
    """`keys` je jedna sada polí, nebo n-tice povolených sad (starší zápis bez volitelného klíče)."""
    allowed = keys if isinstance(keys, tuple) else (keys,)
    if not isinstance(value, list) or len(value) > limit:
        _fail(f"{label} musí být pole nejvýše {limit} položek.")
    seen = set()
    for item in value:
        if not isinstance(item, dict) or all(set(item) != option for option in allowed):
            _fail(f"{label}: položka má neplatná pole.")
        _ident(item["id"], f"{label}.id")
        if item["id"] in seen:
            _fail(f"{label}: duplicitní id {item['id']}.")
        seen.add(item["id"])
    return value


def _rule_target(rule):
    scope, target = rule["scope"], rule["target"]
    if not isinstance(target, str):
        _fail("cíl pravidla musí být text.")
    if scope == "project":
        if target != "":
            _fail("pravidlo s rozsahem projekt má prázdný cíl.")
    elif scope == "path":
        try:
            relative_path(target)
        except ValueError:
            _fail("pravidlo s rozsahem cesta vyžaduje platnou relativní cestu.")
    else:
        _ident(target, "cíl pravidla (uzel)")


def _timestamp(value, label, allow_empty=False):
    if allow_empty and value == "":
        return value
    if not isinstance(value, str) or len(value) > 40:
        _fail(f"{label} musí být ISO 8601 text.")
    try:
        datetime.fromisoformat(value)
    except ValueError:
        _fail(f"{label} musí být ISO 8601 text.")
    return value


def _created_at(value):
    return _timestamp(value, "createdAt")


def _branch(value, label, block_ids, action_ids):
    if not isinstance(value, dict) or set(value) != BRANCH_KEYS:
        _fail(f"{label} má neplatná pole.")
    kind = _enum(value["kind"], BRANCH_KINDS, f"druh větve {label}")
    target = value["targetId"]
    if not isinstance(target, str):
        _fail(f"cíl větve {label} musí být text.")
    if kind == "none":
        if target != "":
            _fail(f"větev {label} bez cíle musí mít prázdný targetId.")
    else:
        _ident(target, f"cíl větve {label}")
    if kind == "block" and target not in block_ids:
        _fail(f"větev {label} míří na neexistující blok {target}.")
    if kind == "action" and target not in action_ids:
        _fail(f"větev {label} míří na neexistující akci {target}.")
    _text(value["note"], MAX_TEXT, f"poznámka větve {label}", allow_empty=True)


def _validate_ports(block):
    """Tlačítka bloku; `_items` hlídá tvar a jedinečnost ID uvnitř bloku."""
    port_shapes = (PORT_KEYS, PORT_KEYS | {"status", "reason"}, PORT_KEYS | {"onMet"}, PORT_KEYS | {"status", "reason", "onMet"})
    for port in _items(block.get("ports", []), port_shapes, MAX_PORTS, f"ports[{block['id']}]"):
        _text(port["label"], MAX_PORT_LABEL, "název portu bloku", allow_empty=True)
        if "status" in port:
            _enum(port["status"], ("chosen", "rejected"), "rozhodnutí portu")
            _text(port["reason"], MAX_TEXT, "důvod rozhodnutí portu")
        if "onMet" in port:
            from backend.editor.agent_memory.port_spawn import validate_spawn
            validate_spawn(port["onMet"])


def _validate_done(node, node_id):
    """Uzavření karty; agent smí `done` jen navrhnout, potvrzení zapisuje člověk."""
    if "done" not in node:
        return
    done = node["done"]
    if not isinstance(done, dict) or set(done) != DONE_KEYS:
        _fail(f"uzavření uzlu {node_id} má neplatná pole.")
    confirmed = _bool(done["confirmed"], "potvrzení uzavření")
    _timestamp(done["at"], f"čas uzavření uzlu {node_id}", allow_empty=True)
    by = _enum(done["by"], DONE_ACTORS, "původce uzavření")
    _text(done["note"], MAX_TEXT, "poznámka k uzavření", allow_empty=True)
    # `agent` + potvrzeno = agent s plnou autonomií projektu (docs/plna-autonomie-agenta.md); kdo smí
    # potvrzení zapsat, hlídá brána zápisu stavu, ne tvar.
    if by == "autonomy" and not confirmed:
        _fail("„autonomy“ označuje jen potvrzené uzavření ve svěřené autonomii.")


def _validate_autonomy(state):
    """Sektory se svěřenou autonomií; tvar hlídá validace, změnu jen cesta /autonomy."""
    grants = state.get("autonomy", {})
    if not isinstance(grants, dict) or len(grants) > MAX_ITEMS:
        _fail(f"autonomy musí být objekt nejvýše {MAX_ITEMS} sektorů.")
    for sector_id, grant in grants.items():
        _ident(sector_id, "sektor autonomie")
        if not isinstance(grant, dict) or set(grant) not in (AUTONOMY_KEYS, AUTONOMY_KEYS | {"grantedBy"}):
            _fail(f"autonomie sektoru {sector_id} má neplatná pole.")
        _timestamp(grant["until"], "platnost autonomie")
        _timestamp(grant["grantedAt"], "čas udělení autonomie")
        _text(grant["note"], MAX_TEXT, "poznámka k autonomii", allow_empty=True)
        if "grantedBy" in grant:
            _text(grant["grantedBy"], 160, "autor souhlasu")
        if datetime.fromisoformat(grant["until"]).tzinfo is None or datetime.fromisoformat(grant["grantedAt"]).tzinfo is None:
            _fail("Časy autonomie musí obsahovat časovou zónu.")


def autonomy_active(state, sector_id, at):
    """Platí v čase `at` svěřená autonomie pro sektor? `at` je datetime s časovou zónou."""
    grant = state.get("autonomy", {}).get(sector_id) if sector_id else None
    return grant is not None and datetime.fromisoformat(grant["until"]) > at


def _validate_agent_role(node, node_id):
    """Role karty (`agentRole`): kdo si tuhle práci pamatuje napříč projekty.

    Klíč je volitelný a výchozí hodnota je `null` — starší uložený stav zůstává platný.
    Povolené hodnoty drží knihovna `library/agent-roles.json`, aby paměť role nepřestala
    existovat po překlepu v id."""
    if "agentRole" not in node:
        return
    value = node["agentRole"]
    if value is None:
        return
    if not isinstance(value, str) or value not in role_ids():
        _fail(f"role karty {node_id} musí být null nebo id z knihovny rolí agenta.")


def _validate_edge_reports(state):
    """Zprávy agenta na vazbách; vazba už v grafu být nemusí (mohla být smazána)."""
    reports = state.get("edges", {})
    if not isinstance(reports, dict) or len(reports) > MAX_EDGE_REPORTS:
        _fail(f"edges musí být objekt nejvýše {MAX_EDGE_REPORTS} zpráv.")
    for edge_id, report in reports.items():
        _ident(edge_id, "klíč vazby")
        if (
            not isinstance(report, dict)
            or not EDGE_REPORT_KEYS <= set(report)
            or not set(report) <= EDGE_REPORT_KEYS | set(EDGE_REPORT_OPTIONAL)
        ):
            _fail(f"zpráva na vazbě {edge_id} má neplatná pole.")
        for key in EDGE_REPORT_TEXTS:
            _text(report[key], MAX_TEXT, f"{key} zprávy na vazbě {edge_id}", allow_empty=True)
        _timestamp(report["updatedAt"], f"updatedAt zprávy na vazbě {edge_id}", allow_empty=True)
        _enum(report["by"], ACTORS, "původce zprávy na vazbě")
        _text(report["agent"], MAX_AGENT, "označení agenta", allow_empty=True)
        if "sentAt" in report:
            _timestamp(report["sentAt"], f"sentAt zprávy na vazbě {edge_id}", allow_empty=True)
        if "due" in report and report["due"] != "" and not valid_date(report["due"]):
            _fail(f"due zprávy na vazbě {edge_id} musí být YYYY-MM-DD nebo prázdné.")


def _validate_blocks(node, node_id):
    blocks = node.get("blocks", [])
    label = f"blocks[{node_id}]"
    _items(blocks, BLOCK_KEY_SETS, MAX_BLOCKS, label)
    block_ids = {item["id"] for item in blocks}
    action_ids = {item["id"] for item in node.get("actions", [])}
    numbers = set()
    parents = {}
    for item in blocks:
        number = item["number"]
        if not isinstance(number, str) or not NUMBER.fullmatch(number):
            _fail(f"{label}: číslo bloku musí být tvaru 1, 1.2, 1.2.3.")
        if number in numbers:
            _fail(f"{label}: duplicitní číslo bloku {number}.")
        numbers.add(number)
        _text(item["title"], MAX_TITLE, "název bloku")
        _text(item["text"], MAX_BLOCK_TEXT, "text bloku", allow_empty=True)
        tags = item["tags"]
        if not isinstance(tags, list) or len(tags) > MAX_TAGS or len(set(tags)) != len(tags):
            _fail(f"štítky bloku musí být pole nejvýše {MAX_TAGS} různých položek.")
        for tag in tags:
            _text(tag, MAX_TAG, "štítek")
        for todo in _items(item["todos"], TODO_KEYS, MAX_TODOS, f"todos[{item['id']}]"):
            _text(todo["text"], MAX_TEXT, "text TODO")
            _bool(todo["done"], "done")
            _text(todo["assignee"], MAX_KEY, "assignee", allow_empty=True)
        for image in _items(item["images"], IMAGE_KEYS, MAX_IMAGES, f"images[{item['id']}]"):
            if not isinstance(image["path"], str) or not image["path"]:
                _fail("obrázek musí mít relativní cestu.")
            try:
                relative_path(image["path"])
            except ValueError:
                _fail("cesta obrázku musí být platná relativní cesta.")
            _text(image["caption"], MAX_TITLE, "popisek obrázku", allow_empty=True)
        state = item["state"]
        if not isinstance(state, dict) or set(state) - {"note"} != STATE_BLOCK_KEYS:
            _fail("stav bloku má neplatná pole.")
        if "note" in state:
            _text(state["note"], MAX_TEXT, "poznámka ke stavu bloku", allow_empty=True)
        _enum(state["status"], BLOCK_STATUSES, "status bloku")
        _text(state["condition"], MAX_TEXT, "podmínka bloku", allow_empty=True)
        _branch(state["onMet"], "onMet", block_ids, action_ids)
        _branch(state["onUnmet"], "onUnmet", block_ids, action_ids)
        _validate_ports(item)
        parent = item["parentBlockId"]
        if parent != "" and (parent == item["id"] or parent not in block_ids):
            _fail(f"{label}: rodič bloku {item['id']} musí být jiný existující blok.")
        parents[item["id"]] = parent
    for start in parents:
        seen, cursor = set(), start
        while cursor:
            if cursor in seen:
                _fail(f"{label}: bloky tvoří cyklus.")
            seen.add(cursor)
            cursor = parents[cursor]


def _validate_materials(node, node_id):
    for item in _items(node.get("materials", []), MATERIAL_KEYS, MAX_MATERIALS, f"materials[{node_id}]"):
        _enum(item["kind"], MATERIAL_KINDS, "druh podkladu")
        path = item["path"]
        if not isinstance(path, str) or not path:
            _fail("podklad musí mít cestu, jméno souboru nebo URL.")
        if item["kind"] == "upload" and not UPLOAD_FILE.fullmatch(path):
            _fail("nahraný podklad musí odkazovat na soubor vytvořený nahráním.")
        if item["kind"] == "source":
            try:
                relative_path(path)
            except ValueError:
                _fail("cesta podkladu musí být platná relativní cesta ve zdroji projektu.")
        if item["kind"] == "link" and (len(path) > MAX_URL or not re.fullmatch(r"https?://\S+", path)):
            _fail("odkaz podkladu musí být http(s) URL.")
        _text(item["caption"], MAX_TITLE, "popisek podkladu", allow_empty=True)


def branch_targets(state):
    """Větve druhu `node` míří na uzly grafu; graf validate_state nezná, kontroluje se při uložení."""
    for node_id, node in state["nodes"].items():
        for item in node.get("blocks", []):
            for via in ("onMet", "onUnmet"):
                branch = item["state"][via]
                if branch["kind"] == "node":
                    yield node_id, item["id"], via, branch["targetId"]


def check_node_branches(state, graph_node_ids):
    for node_id, block_id, via, target in branch_targets(state):
        if target not in graph_node_ids:
            raise ValueError(f"Blok {block_id} uzlu {node_id}: větev {via} míří na neexistující uzel {target}.")


def validate_state(state, *, unchanged=None):
    """Ověří celý stav. `unchanged` = uzly uloženého (už ověřeného) stavu, ze kterého volající
    vyšel mělkou kopií: uzel, který je s ním totožný objekt (`is`), se znovu neprochází (karta P3)."""
    if not isinstance(state, dict) or frozenset(state) not in STATE_KEY_SETS:
        _fail("očekávám pole settings, rules, decisions, nodes, tickets a volitelně edges a autonomy.")
    _validate_edge_reports(state)
    _validate_autonomy(state)
    for item in _items(state["settings"], SETTING_KEYS, MAX_ITEMS, "settings"):
        _text(item["key"], MAX_KEY, "klíč nastavení")
        _text(item["value"], MAX_TEXT, "hodnota nastavení", allow_empty=True)
    for item in _items(state["rules"], (RULE_KEYS, RULE_KEYS | {"by"}), MAX_ITEMS, "rules"):
        _text(item["text"], MAX_TEXT, "text pravidla")
        if "by" in item:
            _enum(item["by"], RULE_AUTHORS, "původce pravidla")
        _enum(item["kind"], RULE_KINDS, "druh pravidla")
        _enum(item["scope"], RULE_SCOPES, "rozsah pravidla")
        _rule_target(item)
    for item in _items(state["decisions"], DECISION_KEY_SETS, MAX_ITEMS, "decisions"):
        _text(item["text"], MAX_TEXT, "text rozhodnutí")
        if "executionId" in item:
            _ident(item["executionId"], "běh rozhodnutí")
        _bool(item["pinned"], "pinned")
        try:
            relative_path(item["path"])
        except ValueError:
            _fail("cesta rozhodnutí musí být platná relativní cesta nebo prázdná.")
        _optional_ident(item["nodeId"], "uzel rozhodnutí")
        _created_at(item["createdAt"])
        _enum(item["by"], ACTORS, "původce rozhodnutí")
    from backend.editor.agent_memory.decision_versions import validate_versions
    validate_versions(state["decisions"])
    nodes = state["nodes"]
    if not isinstance(nodes, dict) or len(nodes) > MAX_NODES:
        _fail(f"nodes musí být objekt nejvýše {MAX_NODES} uzlů.")
    for node_id, node in nodes.items():
        _ident(node_id, "klíč uzlu")
        if not isinstance(node, dict) or frozenset(node) not in _node_key_sets():
            _fail("stav uzlu má neplatná pole.")
        if unchanged is not None and unchanged.get(node_id) is node:
            continue
        _validate_blocks(node, node_id)
        _validate_materials(node, node_id)
        _validate_done(node, node_id)
        from backend.editor.agent_memory.input_security import validate_input_security
        validate_input_security(node)
        if "scenarioRun" in node:
            from backend.canvas.gate_scenario import validate_run
            validate_run(node["scenarioRun"])
        if "evidence" in node:
            from backend.editor.agent_memory.completion_evidence import validate_evidence
            validate_evidence(node["evidence"])
        if "stages" in node:
            from backend.editor.agent_memory.card_pipeline import validate_stages
            validate_stages(node["stages"])
        if "ideas" in node:
            from backend.editor.agent_memory.card_ideas import validate_ideas
            validate_ideas(node["ideas"])
        if "fragmentRefs" in node:
            from backend.editor.brief_vault.brief_vault_refs import validate_refs
            validate_refs(node["fragmentRefs"], f"fragmentRefs[{node_id}]")
        if "round" in node:
            from backend.editor.agent_memory.card_round_legacy import validate_round
            validate_round(node["round"], node_id)
        if "briefGroup" in node or "briefDiscipline" in node:
            from backend.editor.brief_vault.brief_vault_marks import validate_marks
            validate_marks(node, node_id)
        _validate_agent_role(node, node_id)
        for item in _items(node.get("actions", []), ACTION_KEYS, MAX_SUBITEMS, f"actions[{node_id}]"):
            _text(item["pipelineId"], MAX_KEY, "pipelineId akce")
            _text(item["label"], MAX_TITLE, "název akce")
            params = item["params"]
            if not isinstance(params, dict) or len(params) > MAX_PARAMS:
                _fail(f"parametry akce musí být objekt nejvýše {MAX_PARAMS} položek.")
            for key, value in params.items():
                _text(key, MAX_KEY, "klíč parametru akce")
                _text(value, MAX_TEXT, "hodnota parametru akce", allow_empty=True)
        for item in _items(node.get("rules", []), NODE_RULE_KEYS, MAX_SUBITEMS, f"rules[{node_id}]"):
            _text(item["text"], MAX_TEXT, "text pravidla uzlu")
            _enum(item["kind"], RULE_KINDS, "druh pravidla uzlu")
        _enum(node["phase"], PHASES, "fáze uzlu")
        for item in _items(node["criteria"], CRITERION_KEYS, MAX_SUBITEMS, f"criteria[{node_id}]"):
            _text(item["text"], MAX_TEXT, "text kritéria")
            _bool(item["checked"], "checked")
        for item in _items(node["steps"], STEP_KEYS, MAX_SUBITEMS, f"steps[{node_id}]"):
            _text(item["text"], MAX_TEXT, "text kroku")
            _text(item["assignee"], MAX_KEY, "assignee", allow_empty=True)
            _bool(item["done"], "done")
    for item in _items(state["tickets"], TICKET_KEYS, MAX_ITEMS, "tickets"):
        _text(item["title"], MAX_TITLE, "název ticketu")
        _enum(item["priority"], PRIORITIES, "priorita ticketu")
        _enum(item["status"], STATUSES, "stav ticketu")
        _optional_ident(item["nodeId"], "uzel ticketu")
        _text(item["sessionId"], MAX_KEY, "session ticketu", allow_empty=True)
        _enum(item["createdBy"], ACTORS, "původce ticketu")
    return state


def stamp_agent_rules(actor, previous, rules):
    """Nové nebo změněné pravidlo od ne-člověka je návrh agenta; lidské pravidlo agent nemění ani nemaže."""
    before = {rule["id"]: rule for rule in previous}
    for rule in rules:
        old = before.get(rule["id"])
        if old == rule:
            continue
        if old is not None and old.get("by", "human") != "agent" and not acts_as_human(actor):
            from backend.canvas.activity_log import HumanRequired
            raise HumanRequired(actor, "Pravidlo člověka mění jen člověk; navrhněte nové pravidlo.")
        rule["by"] = "agent"
    kept = {rule["id"] for rule in rules}
    if (any(rule.get("by", "human") != "agent" for rule_id, rule in before.items() if rule_id not in kept)
            and not acts_as_human(actor)):
        from backend.canvas.activity_log import HumanRequired
        raise HumanRequired(actor, "Pravidlo člověka odebírá jen člověk.")


def _scope_ids(project, workspace):
    if not isinstance(project, str) or (project != "draft" and not valid_id(project)):
        raise ValueError("Neplatný identifikátor projektu.")
    if not isinstance(workspace, str) or not valid_id(workspace):
        raise ValueError("Neplatný identifikátor pracovního prostoru.")


HEAD_SQL = "SELECT revision,saved_at FROM desktop_v3_state WHERE project_id=? AND workspace_id=?"


class DesktopV3State:
    def __init__(self, canvas):
        self.canvas = canvas

    def current(self, project, workspace):
        """Uložený stav bez ověření rozsahu; volající drží zámky a rozsah už ověřil.

        Stav se cachuje podle tokenu dat a revize (karta P3; `backend/canvas/read_cache.py`):
        vrácený `state` je sdílený mezi požadavky a jen ke čtení. Kdo ho mění, vezme si kopii
        (mělkou tam, kde mění jen jednu sekci, a `save(..., base=...)` pak neověřuje nezměněné uzly)."""
        # Under the project lock the read cache is off; a steady block reads the state once.
        return self.canvas.steady_value(project, ("desktop_v3.current", workspace),
                                        lambda: self._current(project, workspace))

    def _current(self, project, workspace):
        canvas = self.canvas
        with canvas.reading(project):
            key = ("state", project, workspace)
            token = canvas.data_token(project)
            hit = canvas.read_cache.get(key, token)
            if hit is None:
                db = canvas.db_for(project)
                head = db.execute(HEAD_SQL, (project, workspace)).fetchone()
                if head is None:
                    return {"revision": 0, "state": default_state()}
                stamp = (head["revision"], head["saved_at"])
                _token, previous = canvas.read_cache.peek(key)
                if previous is not None and previous[0] == stamp:
                    hit = previous
                else:
                    row = db.execute("SELECT state FROM desktop_v3_state WHERE project_id=? AND workspace_id=?",
                                     (project, workspace)).fetchone()
                    hit = (stamp, fill_defaults(json.loads(row["state"])))
                if token is not None:
                    canvas.read_cache.put(key, token, hit)
            return {"revision": hit[0][0], "state": hit[1]}

    def read(self, project, workspace):
        _scope_ids(project, workspace)
        with self.canvas.reading(project):
            view = self.canvas.view(project, workspace)
            if view["readOnly"]:
                return {"revision": 0, "state": default_state(), "readOnly": True}
            return {**self.current(project, workspace), "readOnly": False}

    def stamp(self, project, workspace):
        """Levná identita uloženého stavu pro ETag (revize + čas uložení), bez čtení samotného stavu."""
        _scope_ids(project, workspace)
        with self.canvas.reading(project):
            if self.canvas.view(project, workspace)["readOnly"]:
                return ("readOnly",)
            head = self.canvas.db_for(project).execute(HEAD_SQL, (project, workspace)).fetchone()
            return ("state", 0, "") if head is None else ("state", head["revision"], head["saved_at"])

    def save(self, payload, *, after_write=None, autonomy_close=frozenset(), autonomy=None, actor="system",
             base=None, slim=False, execution_actor=None):
        # execution_actor is an internal verified request identity, never an HTTP payload field.
        """Uloží celý stav. Interní parametry (nikdy z HTTP): `autonomy_close` = karty, které smí
        uzavřít agent ve svěřené autonomii (jen `AgentOutput`); `autonomy` = nová mapa svěřené
        autonomie (jen `set_autonomy`). Jinak se uložená autonomie přenáší beze změny.

        `actor` je ověřený původce HTTP zápisu (`human` / `agent` / `unknown`); `system` značí
        serverovou cestu, která pravidla hlídá sama (agent-output, potvrzení, bloky). Potvrzení
        a otevření uzavřené karty smí obecný zápis stavu jen od člověka (upgrade-opora #30).

        Interní `base` = uložený stav, ze kterého volající vyšel mělkou kopií: nezměněné uzly se
        znovu neověřují. `slim` = odpověď jen s revizí (karta P3); celý stav si volající nečte."""
        if not isinstance(payload, dict) or set(payload) != SAVE_KEYS:
            raise ValueError("Neplatný formát uložení stavu Desktop v3.")
        project, workspace = payload["project"], payload["workspace"]
        _scope_ids(project, workspace)
        expected = payload["expectedRevision"]
        if type(expected) is not int or expected < 0:
            raise ValueError("Neplatná očekávaná revize stavu.")
        state = validate_state(payload["state"], unchanged=base["nodes"] if base is not None else None)
        with self.canvas.graph_lock_for(project):
            view = self.canvas.view(project, workspace)
            if view["readOnly"]:
                raise ValueError("Main je pouze pro čtení; paměť projektu se ukládá v pracovním prostoru.")
            check_node_branches(state, {item["id"] for item in view["graph"]["nodes"]})
            db = self.canvas.db_for(project)
            with self.canvas.lock_for(project), db:
                db.execute("BEGIN IMMEDIATE")
                current = self.current(project, workspace)
                from backend.canvas.opora_execution_guard import state_write
                state_write(db, project, workspace, current["state"], state, view["graph"],
                            actor if execution_actor is None else execution_actor)
                if current["revision"] != expected:
                    raise ValueError("Stav se změnil v jiném okně (revize nesouhlasí). Obnovte jej.")
                # Kola karty jsou zrušená: starší číslo kola se zápisem stavu nemění (card_round_legacy.py).
                from backend.editor.agent_memory import card_round_legacy
                card_round_legacy.guard_state_write(actor, current["state"], state)
                # Nový odkaz do schránky zadání (karta i Podnět) míří na živý fragment tohoto prostoru.
                from backend.editor.brief_vault.brief_vault_refs import check_new_references
                check_new_references(db, project, workspace, current["state"], state)
                from backend.editor.agent_memory.decision_versions import preserve_versions
                preserve_versions(current["state"]["decisions"], state["decisions"])
                # Autonomii mění jen člověk cestou /autonomy; běžný zápis ji převezme z uloženého stavu.
                state["autonomy"] = (autonomy if autonomy is not None
                                     else copy.deepcopy(current["state"].get("autonomy", {})))
                if not state["autonomy"]:
                    del state["autonomy"]
                if actor not in ("human", "system"):
                    stamp_agent_rules(actor, current["state"]["rules"], state["rules"])
                    from backend.editor.agent_memory.card_pipeline import guard_state_write
                    for node_id in set(state["nodes"]) | set(current["state"]["nodes"]):
                        before = current["state"]["nodes"].get(node_id, {}).get("stages")
                        after = state["nodes"].get(node_id, {}).get("stages")
                        if before != after:
                            guard_state_write(actor, before, after)
                        from backend.editor.agent_memory import card_ideas
                        before = current["state"]["nodes"].get(node_id, {}).get("ideas")
                        after = state["nodes"].get(node_id, {}).get("ideas")
                        # Odebrání celé karty hlídají jiná pravidla; tady jen změna podnětů živé karty.
                        if node_id in state["nodes"] and before != after:
                            card_ideas.guard_state_write(actor, before, after)
                for node_id, node in state["nodes"].items():
                    done = node.get("done", default_done())
                    previous_done = current["state"]["nodes"].get(node_id, {}).get("done", default_done())
                    previous_evidence = current["state"]["nodes"].get(node_id, {}).get("evidence")
                    if (actor not in ("human", "system") and done != previous_done
                            and (done["confirmed"] or previous_done["confirmed"]) and not acts_as_human(actor)):
                        from backend.canvas.activity_log import HumanRequired
                        raise HumanRequired(actor, "Uzavření karty potvrzuje nebo ruší jen člověk v UI; agent ho navrhuje přes agent-output.")
                    previous_scenario = current["state"]["nodes"].get(node_id, {}).get("scenarioRun")
                    # OporaHub cards with accepted plan steps close by the single definition of done
                    # (opora_card_done.closure_gate raises when incomplete); the legacy gate below stays for the rest.
                    from backend.canvas.opora_card_done import closure_gate
                    if (done["confirmed"] and (not previous_done["confirmed"] or node.get("evidence") != previous_evidence or node.get("scenarioRun") != previous_scenario)
                            and closure_gate(self.canvas, project, workspace, node_id) is None):
                        from backend.canvas.card_checks import checks_passed
                        from backend.editor.agent_memory.completion_evidence import evidence_ready
                        graph_node = next(item for item in view["graph"]["nodes"] if item["id"] == node_id)
                        if not evidence_ready(node.get("evidence"), graph_node):
                            raise ValueError("Uzavření vyžaduje doložené testy, review, merge a úspěšné kontroly; neaplikovatelné kroky zdůvodněte "
                                             "([task] karta a karta s kontrolami nesmí mít testy ani merge jako N/A).")
                        if not checks_passed(graph_node, node.get("evidence")):
                            raise ValueError("Uzavření vyžaduje úspěšný běh každé zadané kontroly se shodným ID a příkazem.")
                        from backend.editor.agent_memory.card_pipeline import open_stages
                        waiting = open_stages(node.get("stages"))
                        if waiting:
                            raise ValueError("Uzavření vyžaduje hotovou pipeline karty; otevřené etapy: "
                                             + ", ".join(item["title"] for item in waiting) + ".")
                        scenario = graph_node.get("scenario")
                        scenario_run = node.get("scenarioRun", {})
                        if scenario and (scenario_run.get("command") != scenario["command"] or scenario_run.get("failed") != 0):
                            raise ValueError("Uzavření brány vyžaduje úspěšný běh jejího aktuálního scénáře.")
                        # Karta na cestě zákazníka: každá její cesta má prošlý a čerstvý doklad (docs/brana-cesty.md §5).
                        from backend.canvas.opora_card_done import journeys_blocking, journeys_refusal
                        blocking = journeys_blocking(self.canvas, project, workspace, node_id, view["graph"])
                        if blocking:
                            raise ValueError(journeys_refusal(blocking))
                    if done["by"] == "autonomy" and done != previous_done and node_id not in autonomy_close:
                        raise ValueError("Uzavření ve svěřené autonomii zapisuje jen výstup agenta (agent-output).")
                # Hromadný zápis stavu nesmí obejít zámek, který hlídá adresné API bloků.
                for node_id, previous in current["state"]["nodes"].items():
                    node = state["nodes"].get(node_id)
                    if node is None:
                        if (actor not in ("human", "system") and previous.get("done", default_done())["confirmed"]
                                and not acts_as_human(actor)):
                            from backend.canvas.activity_log import HumanRequired
                            raise HumanRequired(actor, "Uzavřenou kartu ze stavu odebírá jen člověk.")
                        continue
                    if (previous.get("done", default_done())["confirmed"]
                            and node.get("done", default_done())["confirmed"]
                            and (previous.get("blocks", []) != node.get("blocks", [])
                                 or previous.get("stages") != node.get("stages"))):
                        raise ValueError("Uzavřená karta má bloky, porty a pipeline jen ke čtení; nejprve ji otevřete.")
                from backend.editor.agent_memory.port_spawn import persist_spawns, prepare_spawns
                spawned = prepare_spawns(self.canvas, db, project, workspace, view["graph"], current["state"], state)
                if spawned:
                    state = spawned[0].state
                revision = expected + 1
                db.execute(
                    "INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
                    (project, workspace, revision, json.dumps(state, ensure_ascii=False), now()),
                )
                # card.closed in this transaction
                from backend.canvas.opora_card_events import closures
                closures(db, project, workspace, current["state"], state, actor)
                # Internal hook: result provenance commits or rolls back with the state.
                # It is never accepted from an HTTP payload.
                if after_write is not None:
                    after_write(db)
                persist_spawns(self.canvas, db, project, workspace, view["digest"], spawned, now())
            changed = {"graphChanged": True} if spawned else {}
            if slim:
                return {"revision": revision, "readOnly": False, **changed}
            with self.canvas.lock_for(project):
                return {**self.current(project, workspace), "readOnly": False, **changed}

    def save_node(self, payload, *, actor="system"):
        """Štíhlý zápis jedné karty (`docs/navrhy/2026-10-14-vykon-platna.md`, oprava 8).

        Tělo nese jen `nodes[nodeId]` (nebo `null` = stav karty odebrat) a odpověď jen revizi a
        uložený uzel, ne megabajty celého stavu; velké plátno tak nenarazí na strop 2 MB. Revize se
        hlídá stejně přísně jako u celého zápisu (`expectedRevision`), všechna pravidla uložení
        (fáze, uzavření, zámek uzavřené karty, spawn portů, kola) provádí tentýž `save`; ostatní
        karty jsou sdílené s uloženým stavem, takže se znovu neověřují."""
        if not isinstance(payload, dict) or set(payload) != NODE_SAVE_KEYS:
            raise ValueError("Zápis karty vyžaduje project, workspace, expectedRevision, nodeId a node.")
        project, workspace, node_id, node = payload["project"], payload["workspace"], payload["nodeId"], payload["node"]
        _scope_ids(project, workspace)
        _ident(node_id, "klíč uzlu")
        if node is not None and not isinstance(node, dict):
            _fail("stav uzlu musí být objekt nebo null.")
        with self.canvas.graph_lock_for(project):
            stored = self.read(project, workspace)
            if stored["readOnly"]:
                raise ValueError("Main je pouze pro čtení; paměť projektu se ukládá v pracovním prostoru.")
            if stored["revision"] != payload["expectedRevision"]:
                raise ValueError("Stav se změnil v jiném okně (revize nesouhlasí). Obnovte jej.")
            nodes = dict(stored["state"]["nodes"])
            if node is None:
                if nodes.pop(node_id, None) is None:
                    raise ValueError(f"Karta {node_id} nemá uložený stav, není co odebrat.")
            else:
                if not any(item["id"] == node_id for item in self.canvas.view(project, workspace)["graph"]["nodes"]):
                    raise ValueError(f"Karta {node_id} v tomto pracovním prostoru neexistuje.")
                nodes[node_id] = node
            saved = self.save({"project": project, "workspace": workspace, "expectedRevision": stored["revision"],
                               "state": {**stored["state"], "nodes": nodes}},
                              actor=actor, base=stored["state"], slim=True)
        return {**saved, "nodeId": node_id, "node": node}

    def set_autonomy(self, payload):
        """Člověk svěří sektoru autonomii do času `until` (prázdné `until` ji odebere).

        Agent pak smí v tomto sektoru kartu se všemi bloky `met` uzavřít sám (agent-output);
        bránu sektoru (karta s vazbou `next` ven ze sektoru) potvrzuje dál člověk."""
        if not isinstance(payload, dict) or set(payload) not in (AUTONOMY_SAVE_KEYS, AUTONOMY_SAVE_KEYS | {"grantedBy"}):
            raise ValueError("Neplatný formát autonomie: project, workspace, expectedRevision, sectorId, until, note.")
        sector_id, until, note = payload["sectorId"], payload["until"], payload["note"]
        _ident(sector_id, "sektor autonomie")
        _text(note, MAX_TEXT, "poznámka k autonomii", allow_empty=True)
        granted_by = _text(payload.get("grantedBy", "human"), 160, "autor souhlasu")
        if until != "":
            _timestamp(until, "platnost autonomie")
            limit = datetime.fromisoformat(until)
            current_time = datetime.fromisoformat(now())
            if limit.tzinfo is None:
                raise ValueError("Platnost autonomie musí mít časovou zónu.")
            if not current_time < limit <= current_time + timedelta(days=MAX_AUTONOMY_DAYS):
                raise ValueError(f"Platnost autonomie musí být v budoucnu a nejvýš {MAX_AUTONOMY_DAYS} dní.")
        project, workspace = payload["project"], payload["workspace"]
        _scope_ids(project, workspace)
        graph = self.canvas.view(project, workspace)["graph"]
        if not any(item["id"] == sector_id and item.get("kind") == "sector" for item in graph["nodes"]):
            raise ValueError("Autonomii lze svěřit jen existujícímu sektoru.")
        stored = self.read(project, workspace)
        grants = copy.deepcopy(stored["state"].get("autonomy", {}))
        if until == "":
            grants.pop(sector_id, None)
        else:
            grants[sector_id] = {"until": until, "grantedAt": now(), "note": note, "grantedBy": granted_by}
        state = {key: value for key, value in stored["state"].items() if key != "autonomy"}
        return self.save({"project": project, "workspace": workspace,
                          "expectedRevision": payload["expectedRevision"], "state": state}, autonomy=grants)
