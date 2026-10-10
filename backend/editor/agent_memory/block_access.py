"""Adresný přístup k jednomu bloku karty (`opora.block-access/1`): čtení bloku s dětmi a rodičem,
zápis jedné operace (`add`, `update`, `remove`, `todo`) pod CAS revizí.

Kontrakt je `docs/karta-pro-agenty.md`, sekce „Adresný blok“. Agent nečte a nepřepisuje
celý strom bloků kvůli jedné maličkosti; sáhne na konkrétní `blockId` a dostane jen to,
co potřebuje k rozhodnutí (blok, jeho přímé děti, jeho rodiče). Zápis mění bloky téže karty
podle stejných pravidel jako `frontend/editor/node-detail/tree/logic/tree-model.ts`
(číslování, výchozí hodnoty nového bloku, úklid větví po smazání), ale mutuje se kopie stavu
a teprve celek jde přes `DesktopV3State.save`, která drží zámek i CAS na revizi. Uzavřená
karta (`done.confirmed`) zápis odmítne, neznámý `nodeId`/`blockId` je chyba a nezapíše se nic.
"""

import copy
import uuid

from backend.canvas.graph import valid_id
from backend.editor.agent_memory.desktop_v3_state import (
    MAX_BLOCK_TEXT,
    MAX_KEY,
    MAX_TEXT,
    MAX_TITLE,
    DesktopV3State,
    default_done,
)

PAYLOAD_KEYS = {"project", "workspace", "nodeId", "expectedRevision", "op"}
OP_KINDS = ("add", "update", "remove", "todo")
ADD_KEYS = {"kind", "parentBlockId", "title", "text"}
UPDATE_KEYS = {"kind", "blockId", "patch"}
REMOVE_KEYS = {"kind", "blockId"}
TODO_OP_KEYS = {"kind", "blockId", "todo"}
PATCH_KEYS = {"title", "text", "tags", "state", "ports"}
TODO_KINDS = ("add", "toggle", "remove")


def _fail(message):
    raise ValueError("Neplatná operace nad blokem: " + message)


def _text(value, limit, label, allow_empty=True):
    if not isinstance(value, str) or "\0" in value or len(value) > limit:
        _fail(f"{label} musí být text do {limit} znaků.")
    if not allow_empty and not value.strip():
        _fail(f"{label} nesmí být prázdný.")
    return value


def _validate_todo_op(todo):
    if not isinstance(todo, dict) or "kind" not in todo or todo["kind"] not in TODO_KINDS:
        _fail("todo musí mít kind add, toggle nebo remove.")
    kind = todo["kind"]
    if kind == "add":
        if set(todo) - {"kind", "text", "assignee"} or "text" not in todo:
            _fail("todo add musí mít text a smí mít assignee.")
        _text(todo["text"], MAX_TEXT, "text TODO", allow_empty=False)
        if "assignee" in todo:
            _text(todo["assignee"], MAX_KEY, "assignee")
    else:
        if set(todo) != {"kind", "id"}:
            _fail(f"todo {kind} musí mít jen id.")
        if not valid_id(todo["id"]):
            _fail("id úkolu má neplatný identifikátor.")
    return todo


def validate_block_op(payload):
    """Tvar celého požadavku; identita uzlu/bloku se proti stavu ověřuje až v `apply`."""
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_KEYS:
        _fail("očekávám project, workspace, nodeId, expectedRevision a op.")
    project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
    if not isinstance(project, str) or (project != "draft" and not valid_id(project)) or not valid_id(workspace):
        _fail("neplatný identifikátor projektu nebo pracovního prostoru.")
    if not valid_id(node_id):
        _fail("neplatný identifikátor uzlu.")
    if type(payload["expectedRevision"]) is not int or payload["expectedRevision"] < 0:
        _fail("expectedRevision musí být revize stavu, kterou agent četl.")
    op = payload["op"]
    if not isinstance(op, dict) or "kind" not in op or op["kind"] not in OP_KINDS:
        _fail("op musí mít kind add, update, remove nebo todo.")
    kind = op["kind"]
    if kind == "add":
        if set(op) != ADD_KEYS:
            _fail("op add musí mít parentBlockId, title a text.")
        parent = op["parentBlockId"]
        if parent != "" and not valid_id(parent):
            _fail("parentBlockId má neplatný identifikátor.")
        _text(op["title"], MAX_TITLE, "název bloku", allow_empty=False)
        _text(op["text"], MAX_BLOCK_TEXT, "text bloku")
    elif kind == "update":
        if set(op) != UPDATE_KEYS:
            _fail("op update musí mít blockId a patch.")
        if not valid_id(op["blockId"]):
            _fail("blockId má neplatný identifikátor.")
        patch = op["patch"]
        if not isinstance(patch, dict) or set(patch) - PATCH_KEYS:
            _fail("patch smí obsahovat jen title, text, tags, state a ports.")
    elif kind == "remove":
        if set(op) != REMOVE_KEYS:
            _fail("op remove musí mít jen blockId.")
        if not valid_id(op["blockId"]):
            _fail("blockId má neplatný identifikátor.")
    else:
        if set(op) != TODO_OP_KEYS:
            _fail("op todo musí mít blockId a todo.")
        if not valid_id(op["blockId"]):
            _fail("blockId má neplatný identifikátor.")
        _validate_todo_op(op["todo"])
    return payload


def _default_branch():
    return {"kind": "none", "targetId": "", "note": ""}


def _number_key(number):
    return [int(part) for part in number.split(".")]


def renumber_blocks(blocks):
    """Python obdoba `renumber` z tree-model.ts: kořenové bloky 1,2,3; děti 1.1, 1.2; pořadí
    sourozenců = pořadí v poli. Osiřelý blok (rodič zmizel) se připojí ke kořeni."""
    by_parent = {}
    for item in blocks:
        by_parent.setdefault(item["parentBlockId"], []).append(item)
    numbered = {}

    def walk(parent, prefix):
        for index, item in enumerate(by_parent.get(parent, [])):
            number = f"{prefix}.{index + 1}" if prefix else str(index + 1)
            numbered[item["id"]] = number
            walk(item["id"], number)

    walk("", "")
    known = {item["id"] for item in blocks}
    result = []
    for item in blocks:
        orphan = bool(item["parentBlockId"]) and item["parentBlockId"] not in known
        number = numbered.get(item["id"], str(len(numbered) + 1))
        result.append({**item, "number": number, "parentBlockId": "" if orphan else item["parentBlockId"]})
    return result


def _apply_add(blocks, op):
    parent_block_id = op["parentBlockId"]
    if parent_block_id != "" and not any(item["id"] == parent_block_id for item in blocks):
        raise ValueError(f"Rodičovský blok {parent_block_id} neexistuje.")
    new_block = {
        "id": uuid.uuid4().hex,
        "number": "",
        "title": op["title"],
        "text": op["text"],
        "tags": [],
        "todos": [],
        "images": [],
        "parentBlockId": parent_block_id,
        "ports": [],
        "state": {
            "status": "open",
            "condition": "",
            "onMet": _default_branch(),
            "onUnmet": _default_branch(),
        },
    }
    return blocks + [new_block], new_block["id"]


def _apply_update(blocks, op):
    block_id = op["blockId"]
    patch = op["patch"]
    if not any(item["id"] == block_id for item in blocks):
        raise ValueError(f"Blok {block_id} neexistuje.")
    return [{**item, **patch} if item["id"] == block_id else item for item in blocks], block_id


def _apply_remove(blocks, op):
    """Odebrání bloku i celého podstromu; větve mířící na odebrané bloky se vyprázdní."""
    block_id = op["blockId"]
    if not any(item["id"] == block_id for item in blocks):
        raise ValueError(f"Blok {block_id} neexistuje.")
    removed = {block_id}
    grew = True
    while grew:
        grew = False
        for item in blocks:
            if item["id"] not in removed and item["parentBlockId"] in removed:
                removed.add(item["id"])
                grew = True

    def clean(branch):
        if branch["kind"] == "block" and branch["targetId"] in removed:
            return _default_branch()
        return branch

    remaining = [
        {**item, "state": {**item["state"], "onMet": clean(item["state"]["onMet"]), "onUnmet": clean(item["state"]["onUnmet"])}}
        for item in blocks
        if item["id"] not in removed
    ]
    return remaining, None


def _apply_todo(blocks, op):
    block_id = op["blockId"]
    todo_op = op["todo"]
    kind = todo_op["kind"]
    if not any(item["id"] == block_id for item in blocks):
        raise ValueError(f"Blok {block_id} neexistuje.")

    def next_todos(todos):
        if kind == "add":
            new_todo = {"id": uuid.uuid4().hex, "text": todo_op["text"], "done": False, "assignee": todo_op.get("assignee", "")}
            return todos + [new_todo]
        todo_id = todo_op["id"]
        if kind == "toggle":
            if not any(item["id"] == todo_id for item in todos):
                raise ValueError(f"Úkol {todo_id} neexistuje.")
            return [{**item, "done": not item["done"]} if item["id"] == todo_id else item for item in todos]
        return [item for item in todos if item["id"] != todo_id]

    return [{**item, "todos": next_todos(item["todos"])} if item["id"] == block_id else item for item in blocks], block_id


class BlockAccess:
    def __init__(self, canvas, state_store=None):
        self.canvas = canvas
        self.state = state_store or DesktopV3State(canvas)

    def read(self, project, workspace, node_id, block_id):
        """Jeden blok s dětmi a rodičem; None = uzel nebo blok v tomto rozsahu neexistuje."""
        if not valid_id(node_id) or not valid_id(block_id):
            return None
        stored = self.state.read(project, workspace)
        graph = self.canvas.view(project, workspace)["graph"]
        node = next((item for item in graph["nodes"] if item["id"] == node_id), None)
        if node is None:
            return None
        blocks = stored["state"]["nodes"].get(node_id, {}).get("blocks", [])
        block = next((item for item in blocks if item["id"] == block_id), None)
        if block is None:
            return None
        children = sorted(
            (item for item in blocks if item["parentBlockId"] == block_id),
            key=lambda item: _number_key(item["number"]),
        )
        parent_id = block["parentBlockId"]
        parent = next((item for item in blocks if item["id"] == parent_id), None) if parent_id else None
        return {
            "revision": stored["revision"],
            "node": {"id": node["id"], "name": node["name"]},
            "block": block,
            "children": children,
            "parent": parent,
        }

    def apply(self, payload):
        """Zapíše jednu operaci nad blokem a vrátí novou StateResponse + `block`; při chybě nezapíše nic."""
        validate_block_op(payload)
        project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        expected, op = payload["expectedRevision"], payload["op"]
        with self.canvas.graph_lock_for(project):
            graph = self.canvas.view(project, workspace)["graph"]
            if not any(item["id"] == node_id for item in graph["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            stored = self.state.read(project, workspace)
            if stored["readOnly"]:
                raise ValueError("Main je pouze pro čtení; blok karty se mění v pracovním prostoru.")
            if stored["revision"] != expected:
                raise ValueError("Stav se změnil (revize nesouhlasí); načtěte kartu znovu.")
            state = copy.deepcopy(stored["state"])
            # Karta bez uloženého stavu vzniká až tím, co se do ní opravdu zapíše.
            node = state["nodes"].get(node_id, {"phase": "discover", "criteria": [], "steps": []})
            if node.get("done", default_done())["confirmed"]:
                raise ValueError("Karta je uzavřená; blok se do ní nemění.")
            blocks = node.get("blocks", [])
            kind = op["kind"]
            if kind == "add":
                blocks, affected_id = _apply_add(blocks, op)
            elif kind == "update":
                blocks, affected_id = _apply_update(blocks, op)
            elif kind == "remove":
                blocks, affected_id = _apply_remove(blocks, op)
            else:
                blocks, affected_id = _apply_todo(blocks, op)
            node["blocks"] = renumber_blocks(blocks)
            state["nodes"][node_id] = node
            result = self.state.save({
                "project": project, "workspace": workspace,
                "expectedRevision": expected, "state": state,
            })
            block = None
            if affected_id is not None:
                saved_blocks = result["state"]["nodes"].get(node_id, {}).get("blocks", [])
                block = next((item for item in saved_blocks if item["id"] == affected_id), None)
            return {**result, "block": block}
