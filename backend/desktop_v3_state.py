"""Desktop v3 paměť projektu a stav uzlů: jedna revizovaná pravda v SQLite.

State = {settings, rules, decisions, nodes, tickets}. Prázdné pole/objekt jsou výchozí
hodnoty; žádná demo data. Fáze uzlu je plánovací stav člověka, nikoli důkaz testů či
nasazení: postup vpřed vyžaduje neprázdná splněná kritéria, opačný směr je volný.
"""

import json
from datetime import datetime

from .graph import valid_id
from .service import now
from .workspace_sources import relative_path

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
CRITERION_KEYS = {"id", "text", "checked"}
STEP_KEYS = {"id", "text", "assignee", "done"}
TICKET_KEYS = {"id", "title", "priority", "status", "nodeId", "sessionId", "createdBy"}
STATE_KEYS = {"settings", "rules", "decisions", "nodes", "tickets"}
SAVE_KEYS = {"project", "workspace", "expectedRevision", "state"}


def default_state():
    return {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": []}


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
    if not isinstance(value, list) or len(value) > limit:
        _fail(f"{label} musí být pole nejvýše {limit} položek.")
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != keys:
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


def _created_at(value):
    if not isinstance(value, str) or len(value) > 40:
        _fail("createdAt musí být ISO 8601 text.")
    try:
        datetime.fromisoformat(value)
    except ValueError:
        _fail("createdAt musí být ISO 8601 text.")
    return value


def validate_state(state):
    if not isinstance(state, dict) or set(state) != STATE_KEYS:
        _fail("očekávám přesně pole settings, rules, decisions, nodes, tickets.")
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
        if not isinstance(node, dict) or set(node) != NODE_KEYS:
            _fail("stav uzlu má neplatná pole.")
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
    """Postup vpřed jen s neprázdnými splněnými kritérii; zpět je vždy možný."""
    before = previous.get("nodes", {}) if isinstance(previous, dict) else {}
    for node_id, node in state["nodes"].items():
        old_phase = before.get(node_id, {}).get("phase", PHASES[0])
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
        with canvas.lock:
            canvas.db.execute(
                """CREATE TABLE IF NOT EXISTS desktop_v3_state(
                project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, revision INTEGER NOT NULL,
                state TEXT NOT NULL, saved_at TEXT NOT NULL, PRIMARY KEY(project_id, workspace_id))"""
            )
            canvas.db.commit()

    def current(self, project, workspace):
        """Uložený stav bez ověření rozsahu; volající drží zámky a rozsah už ověřil."""
        row = self.canvas.db.execute(
            "SELECT revision,state FROM desktop_v3_state WHERE project_id=? AND workspace_id=?",
            (project, workspace),
        ).fetchone()
        if row is None:
            return {"revision": 0, "state": default_state()}
        return {"revision": row["revision"], "state": json.loads(row["state"])}

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
            with self.canvas.lock, self.canvas.db:
                self.canvas.db.execute("BEGIN IMMEDIATE")
                current = self.current(project, workspace)
                if current["revision"] != expected:
                    raise ValueError("Stav se změnil v jiném okně (revize nesouhlasí). Obnovte jej.")
                check_phase_transitions(current["state"], state)
                revision = expected + 1
                self.canvas.db.execute(
                    "INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
                    (project, workspace, revision, json.dumps(state, ensure_ascii=False), now()),
                )
            with self.canvas.lock:
                return {**self.current(project, workspace), "readOnly": False}
