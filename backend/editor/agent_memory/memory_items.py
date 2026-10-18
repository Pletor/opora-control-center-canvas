"""Addressed rule/decision writes compare only the item the caller actually read.

Zápis vrací jen novou revizi a zapsanou položku (karta P3, < 10 kB místo celého stavu);
`full=True` (HTTP `?full=1`) vrátí kvůli starším klientům i celý stav.
Hromadné posouzení návrhů agenta (`review_rules`) jde stejnou cestou jako jedna položka,
jen všechny změny uloží jednou revizí: všechno, nebo nic.
"""
from backend.canvas.activity_log import require_human
from backend.canvas.graph import valid_id

KEYS = {"project", "workspace", "id", "op", "expected", "item"}
REVIEW_KEYS = {"project", "workspace", "id", "decision", "expected"}
BATCH_KEYS = {"project", "workspace", "items", "decision"}
BATCH_ITEM_KEYS = {"id", "expected"}
MAX_BATCH = 500


class ItemConflict(ValueError):
    """Položka se od přečtení změnila (CAS) nebo její cílová karta zmizela; nese ID položky."""

    def __init__(self, message, identifier):
        super().__init__(message)
        self.identifier = identifier


class BatchConflict(ValueError):
    """Dávka posouzení neprošla: `conflicts` jsou ID položek, které kolidovaly; neuložilo se nic."""

    def __init__(self, conflicts):
        shown = ", ".join(conflicts[:10]) + (" …" if len(conflicts) > 10 else "")
        super().__init__(f"Návrhy se mezitím změnily ({len(conflicts)}): {shown}. "
                         "Neuložilo se nic; načtěte paměť znovu.")
        self.conflicts = conflicts


def _validated(payload):
    """Tvar jednoho zápisu položky → (id, op, expected, item); stav se tu ještě nečte."""
    if not isinstance(payload, dict) or set(payload) != KEYS:
        raise ValueError("Zápis položky vyžaduje project, workspace, id, op, expected a item.")
    identifier, operation = payload["id"], payload["op"]
    expected, replacement = payload["expected"], payload["item"]
    if not valid_id(identifier) or operation not in ("add", "update", "remove"):
        raise ValueError("Neplatné ID nebo operace položky paměti.")
    if operation == "add":
        if expected is not None:
            raise ValueError("Přidání očekává expected: null.")
    elif not isinstance(expected, dict) or expected.get("id") != identifier:
        raise ValueError("Úprava vyžaduje původní položku v expected.")
    if operation == "remove":
        if replacement is not None:
            raise ValueError("Odstranění očekává item: null.")
    elif not isinstance(replacement, dict) or replacement.get("id") != identifier:
        raise ValueError("ID nové položky nesouhlasí.")
    return identifier, operation, expected, replacement


def _review_change(payload):
    """Posouzení návrhu agenta → zápis položky: schválení = uložení bez `by`, zamítnutí = odebrání."""
    expected, decision = payload["expected"], payload["decision"]
    if decision not in ("approve", "reject"):
        raise ValueError("Posouzení pravidla je approve nebo reject.")
    if not isinstance(expected, dict) or expected.get("by") != "agent":
        raise ValueError("Schválit nebo zamítnout lze jen návrh pravidla od agenta.")
    approved = {key: value for key, value in expected.items() if key != "by"}
    return {
        "project": payload["project"], "workspace": payload["workspace"], "id": payload["id"],
        "op": "update" if decision == "approve" else "remove", "expected": expected,
        "item": approved if decision == "approve" else None,
    }


class MemoryItems:
    def __init__(self, state):
        self.state = state
        self.canvas = state.canvas

    def read(self, collection, project, workspace, identifier):
        if not valid_id(identifier):
            raise ValueError("Neplatné ID položky paměti.")
        stored = self.state.read(project, workspace)
        item = next((x for x in stored["state"][collection] if x["id"] == identifier), None)
        return {"item": item, "revision": stored["revision"], "readOnly": stored["readOnly"]}

    def apply(self, collection, payload, *, actor="system", full=False):
        change = _validated(payload)
        saved, items = self._write(collection, payload["project"], payload["workspace"], [change],
                                   actor=actor, full=full)
        return {**saved, "item": items[0]}

    def _write(self, collection, project, workspace, changes, *, actor, full):
        """Všechny změny nad jedním přečteným stavem a jedno uložení (jedna revize), nebo nic.

        Každá změna porovná položku s tím, co volající přečetl (CAS). Kolize v dávce se sbírají přes
        všechny položky, aby odpověď řekla všechny najednou; při jediné kolizi se neuloží nic."""
        with self.canvas.graph_lock_for(project):
            stored = self.state.read(project, workspace)
            if stored["readOnly"]:
                raise ValueError("Main je pouze pro čtení.")
            # Mění se jen jedna sekce: mělká kopie stavu a nový seznam; ostatní uzly zůstávají sdílené
            # s uloženým stavem, a proto je `save(base=...)` znovu neověřuje.
            state = {**stored["state"], collection: list(stored["state"][collection])}
            items, nodes, conflicts = state[collection], None, []
            for change in changes:
                try:
                    nodes = self._change(collection, items, change, nodes, project, workspace)
                except ItemConflict as conflict:
                    if len(changes) == 1:
                        raise
                    conflicts.append(conflict.identifier)
            if conflicts:
                raise BatchConflict(conflicts)
            saved = self.state.save({"project": project, "workspace": workspace,
                                     "expectedRevision": stored["revision"], "state": state}, actor=actor,
                                    base=stored["state"], slim=not full)
            return saved, [next((x for x in items if x["id"] == change[0]), None) for change in changes]

    def _change(self, collection, items, change, nodes, project, workspace):
        """Jedna změna seznamu na místě; vrací (líně načtená) ID karet pro kontrolu cíle."""
        identifier, operation, expected, replacement = change
        current = next((x for x in items if x["id"] == identifier), None)
        if current != expected:
            raise ItemConflict("Položka se změnila; načtěte ji znovu (expected nesouhlasí).", identifier)
        if replacement is not None:
            target = (replacement.get("target") if replacement.get("scope") == "node" else "") \
                if collection == "rules" else replacement.get("nodeId")
            if target:
                if nodes is None:
                    nodes = {n["id"] for n in self.canvas.view(project, workspace)["graph"]["nodes"]}
                if target not in nodes:
                    raise ItemConflict("Cílová karta položky neexistuje.", identifier)
        if operation == "add":
            items.append(replacement)
        else:
            index = next(i for i, x in enumerate(items) if x["id"] == identifier)
            if operation == "remove":
                items.pop(index)
            else:
                items[index] = replacement
        return nodes

    def review_rule(self, payload, *, actor, full=False):
        """Člověk schválí nebo zamítne návrh pravidla od agenta (karta, projekt i cesta stejně).

        Schválení = uložení pravidla bez `by` (od té doby platí v `node-brief`), zamítnutí = odebrání.
        Agent dostane 403, neznámý původce 428; `expected` je přečtený návrh (CAS jako u zápisu položky)."""
        require_human(actor, "Návrh pravidla schvaluje nebo zamítá jen člověk v UI.")
        if not isinstance(payload, dict) or set(payload) != REVIEW_KEYS:
            raise ValueError("Posouzení pravidla vyžaduje project, workspace, id, decision a expected.")
        return self.apply("rules", _review_change(payload), actor=actor, full=full)

    def review_rules(self, payload, *, actor, full=False):
        """Člověk posoudí víc návrhů agenta jedním krokem: všechno, nebo nic (jedna revize).

        Každá položka `{id, expected}` projde stejnou cestou jako `review_rule` (CAS na přečtený návrh);
        když kterákoli koliduje, neuloží se nic a `BatchConflict.conflicts` řekne, které to byly."""
        require_human(actor, "Návrhy pravidel schvaluje nebo zamítá jen člověk v UI.")
        if not isinstance(payload, dict) or set(payload) != BATCH_KEYS:
            raise ValueError("Hromadné posouzení vyžaduje project, workspace, items a decision.")
        entries = payload["items"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_BATCH:
            raise ValueError(f"Vyberte 1 až {MAX_BATCH} návrhů pravidel.")
        if not all(isinstance(e, dict) and set(e) == BATCH_ITEM_KEYS for e in entries):
            raise ValueError("Každá položka dávky vyžaduje id a expected.")
        if len({e["id"] for e in entries if isinstance(e["id"], str)}) != len(entries):
            raise ValueError("Položky dávky musí mít různá ID.")
        scope = {"project": payload["project"], "workspace": payload["workspace"]}
        changes = [_validated(_review_change({**scope, "id": e["id"], "decision": payload["decision"],
                                              "expected": e["expected"]})) for e in entries]
        saved, items = self._write("rules", scope["project"], scope["workspace"], changes, actor=actor, full=full)
        return {**saved, "items": [{"id": change[0], "item": item} for change, item in zip(changes, items)]}
