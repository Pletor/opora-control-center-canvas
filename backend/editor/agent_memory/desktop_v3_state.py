"""Desktop v3 paměť projektu a stav uzlů: jedna revizovaná pravda v SQLite.

State = {settings, rules, decisions, nodes, tickets, edges}. Prázdné pole/objekt jsou výchozí
hodnoty; žádná demo data. Fáze uzlu je plánovací stav člověka, nikoli důkaz testů či
nasazení: postup vpřed vyžaduje neprázdná splněná kritéria, opačný směr je volný.

`edges` je sekce zpráv agenta na vazbách grafu (log, souhrn, předání, zlepšení, chyby);
uzel navíc nese `done` (uzavření karty), `agentRole` (která role agenta si tuhle práci
pamatuje napříč projekty) a blok `ports` (tlačítka, z nichž vede vazba na jinou kartu).
Všechny tyto klíče jsou volitelné, aby starší uložený stav zůstal platný.
"""

import json
import re
from datetime import datetime

from backend.canvas.canvas_service import now
from backend.canvas.graph import valid_id
from backend.memory.roles import role_ids
from backend.project.workspace.workspace_sources import relative_path

PHASES = ("discover", "define", "build", "verify", "live")
RULE_KINDS = ("must", "must_not")
RULE_SCOPES = ("project", "path", "node")
ACTORS = ("human", "agent")
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
DECISION_KEYS = {"id", "text", "pinned", "path", "nodeId", "createdAt", "by"}
NODE_KEYS = {"phase", "criteria", "steps"}
# Bloky uzlu z portů karty: akce (pipeline z knihovny) a pravidla uzlu. Starší stav je nemá;
# oba klíče přicházejí vždy spolu, aby klient nemohl uložit půlku bloku.
NODE_KEYS_WITH_BLOCKS = NODE_KEYS | {"actions", "rules"}
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
MAX_EDGE_REPORTS = 4000
MAX_AGENT = 120


def _node_key_sets():
    """Volitelné klíče uzlu; `actions` a `rules` chodí vždy spolu, zbytek nezávisle."""
    sets = (frozenset(NODE_KEYS), frozenset(NODE_KEYS) | {"actions", "rules"})
    for optional in ("blocks", "materials", "done", "agentRole"):
        sets = sets + tuple(item | {optional} for item in sets)
    return sets
TICKET_KEYS = {"id", "title", "priority", "status", "nodeId", "sessionId", "createdBy"}
STATE_KEYS = {"settings", "rules", "decisions", "nodes", "tickets"}
STATE_KEY_SETS = (frozenset(STATE_KEYS), frozenset(STATE_KEYS) | {"edges"})
SAVE_KEYS = {"project", "workspace", "expectedRevision", "state"}


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
    for port in _items(block.get("ports", []), PORT_KEYS, MAX_PORTS, f"ports[{block['id']}]"):
        _text(port["label"], MAX_PORT_LABEL, "název portu bloku", allow_empty=True)


def _validate_done(node, node_id):
    """Uzavření karty; agent smí `done` jen navrhnout, potvrzení zapisuje člověk."""
    if "done" not in node:
        return
    done = node["done"]
    if not isinstance(done, dict) or set(done) != DONE_KEYS:
        _fail(f"uzavření uzlu {node_id} má neplatná pole.")
    confirmed = _bool(done["confirmed"], "potvrzení uzavření")
    _timestamp(done["at"], f"čas uzavření uzlu {node_id}", allow_empty=True)
    by = _enum(done["by"], ACTORS, "původce uzavření")
    _text(done["note"], MAX_TEXT, "poznámka k uzavření", allow_empty=True)
    if by == "agent" and confirmed:
        _fail("agent smí uzavření karty jen navrhnout; potvrzuje ho člověk.")


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
        if not isinstance(report, dict) or set(report) != EDGE_REPORT_KEYS:
            _fail(f"zpráva na vazbě {edge_id} má neplatná pole.")
        for key in EDGE_REPORT_TEXTS:
            _text(report[key], MAX_TEXT, f"{key} zprávy na vazbě {edge_id}", allow_empty=True)
        _timestamp(report["updatedAt"], f"updatedAt zprávy na vazbě {edge_id}", allow_empty=True)
        _enum(report["by"], ACTORS, "původce zprávy na vazbě")
        _text(report["agent"], MAX_AGENT, "označení agenta", allow_empty=True)


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
        if not isinstance(state, dict) or set(state) != STATE_BLOCK_KEYS:
            _fail("stav bloku má neplatná pole.")
        _enum(state["status"], BLOCK_STATUSES, "status bloku")
        _text(state["condition"], MAX_TEXT, "podmínka bloku", allow_empty=True)
        _branch(state["onMet"], "onMet", block_ids, action_ids)
        _branch(state["onUnmet"], "onUnmet", block_ids, action_ids)
        _validate_ports(item)
        parent = item["parentBlockId"]
        if parent != "":
            if parent == item["id"] or parent not in block_ids:
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


def validate_state(state):
    if not isinstance(state, dict) or frozenset(state) not in STATE_KEY_SETS:
        _fail("očekávám pole settings, rules, decisions, nodes, tickets a volitelně edges.")
    _validate_edge_reports(state)
    for item in _items(state["settings"], SETTING_KEYS, MAX_ITEMS, "settings"):
        _text(item["key"], MAX_KEY, "klíč nastavení")
        _text(item["value"], MAX_TEXT, "hodnota nastavení", allow_empty=True)
    for item in _items(state["rules"], RULE_KEYS, MAX_ITEMS, "rules"):
        _text(item["text"], MAX_TEXT, "text pravidla")
        _enum(item["kind"], RULE_KINDS, "druh pravidla")
        _enum(item["scope"], RULE_SCOPES, "rozsah pravidla")
        _rule_target(item)
    for item in _items(state["decisions"], DECISION_KEYS, MAX_ITEMS, "decisions"):
        _text(item["text"], MAX_TEXT, "text rozhodnutí")
        _bool(item["pinned"], "pinned")
        try:
            relative_path(item["path"])
        except ValueError:
            _fail("cesta rozhodnutí musí být platná relativní cesta nebo prázdná.")
        _optional_ident(item["nodeId"], "uzel rozhodnutí")
        _created_at(item["createdAt"])
        _enum(item["by"], ACTORS, "původce rozhodnutí")
    nodes = state["nodes"]
    if not isinstance(nodes, dict) or len(nodes) > MAX_NODES:
        _fail(f"nodes musí být objekt nejvýše {MAX_NODES} uzlů.")
    for node_id, node in nodes.items():
        _ident(node_id, "klíč uzlu")
        if not isinstance(node, dict) or frozenset(node) not in _node_key_sets():
            _fail("stav uzlu má neplatná pole.")
        _validate_blocks(node, node_id)
        _validate_materials(node, node_id)
        _validate_done(node, node_id)
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


def check_phase_transitions(previous, state):
    """Postup existující karty vpřed jen s neprázdnými splněnými kritérii; zpět je vždy možný.
    Nová karta (v `previous` ještě neexistuje) smí vzniknout v libovolné fázi bez brány."""
    before = previous.get("nodes", {}) if isinstance(previous, dict) else {}
    for node_id, node in state["nodes"].items():
        if node_id not in before:
            continue
        old_phase = before[node_id].get("phase", PHASES[0])
        if PHASES.index(node["phase"]) <= PHASES.index(old_phase):
            continue
        criteria = node["criteria"]
        if not criteria or not all(item["checked"] for item in criteria):
            raise ValueError(
                f"Postup uzlu {node_id} do fáze {node['phase']} vyžaduje neprázdná a všechna splněná kritéria."
            )


def _scope_ids(project, workspace):
    if not isinstance(project, str) or (project != "draft" and not valid_id(project)):
        raise ValueError("Neplatný identifikátor projektu.")
    if not isinstance(workspace, str) or not valid_id(workspace):
        raise ValueError("Neplatný identifikátor pracovního prostoru.")


class DesktopV3State:
    def __init__(self, canvas):
        self.canvas = canvas

    def current(self, project, workspace):
        """Uložený stav bez ověření rozsahu; volající drží zámky a rozsah už ověřil."""
        row = self.canvas.db_for(project).execute(
            "SELECT revision,state FROM desktop_v3_state WHERE project_id=? AND workspace_id=?",
            (project, workspace),
        ).fetchone()
        if row is None:
            return {"revision": 0, "state": default_state()}
        return {"revision": row["revision"], "state": fill_defaults(json.loads(row["state"]))}

    def read(self, project, workspace):
        _scope_ids(project, workspace)
        with self.canvas.graph_lock:
            view = self.canvas.view(project, workspace)
            if view["readOnly"]:
                return {"revision": 0, "state": default_state(), "readOnly": True}
            with self.canvas.lock:
                return {**self.current(project, workspace), "readOnly": False}

    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) != SAVE_KEYS:
            raise ValueError("Neplatný formát uložení stavu Desktop v3.")
        project, workspace = payload["project"], payload["workspace"]
        _scope_ids(project, workspace)
        expected = payload["expectedRevision"]
        if type(expected) is not int or expected < 0:
            raise ValueError("Neplatná očekávaná revize stavu.")
        state = validate_state(payload["state"])
        with self.canvas.graph_lock:
            view = self.canvas.view(project, workspace)
            if view["readOnly"]:
                raise ValueError("Main je pouze pro čtení; paměť projektu se ukládá v pracovním prostoru.")
            check_node_branches(state, {item["id"] for item in view["graph"]["nodes"]})
            db = self.canvas.db_for(project)
            with self.canvas.lock, db:
                db.execute("BEGIN IMMEDIATE")
                current = self.current(project, workspace)
                if current["revision"] != expected:
                    raise ValueError("Stav se změnil v jiném okně (revize nesouhlasí). Obnovte jej.")
                check_phase_transitions(current["state"], state)
                # Hromadný zápis stavu nesmí obejít zámek, který hlídá adresné API bloků.
                for node_id, previous in current["state"]["nodes"].items():
                    node = state["nodes"].get(node_id)
                    if node is None:
                        continue
                    if (previous.get("done", default_done())["confirmed"]
                            and node.get("done", default_done())["confirmed"]
                            and previous.get("blocks", []) != node.get("blocks", [])):
                        raise ValueError("Uzavřená karta má bloky a porty jen ke čtení; nejprve ji otevřete.")
                revision = expected + 1
                db.execute(
                    "INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
                    (project, workspace, revision, json.dumps(state, ensure_ascii=False), now()),
                )
            with self.canvas.lock:
                return {**self.current(project, workspace), "readOnly": False}
