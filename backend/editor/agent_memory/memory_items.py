"""Addressed rule/decision writes compare only the item the caller actually read.

Zápis vrací jen novou revizi a zapsanou položku (karta P3, < 10 kB místo celého stavu);
`full=True` (HTTP `?full=1`) vrátí kvůli starším klientům i celý stav.
"""
from backend.canvas.activity_log import require_human
from backend.canvas.graph import valid_id

KEYS = {"project", "workspace", "id", "op", "expected", "item"}
REVIEW_KEYS = {"project", "workspace", "id", "decision", "expected"}


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
        project, workspace = payload["project"], payload["workspace"]
        with self.canvas.graph_lock_for(project):
            stored = self.state.read(project, workspace)
            if stored["readOnly"]:
                raise ValueError("Main je pouze pro čtení.")
            current = next((x for x in stored["state"][collection] if x["id"] == identifier), None)
            if current != expected:
                raise ValueError("Položka se změnila; načtěte ji znovu (expected nesouhlasí).")
            if replacement is not None:
                target = (replacement.get("target") if replacement.get("scope") == "node" else "") \
                    if collection == "rules" else replacement.get("nodeId")
                nodes = self.canvas.view(project, workspace)["graph"]["nodes"]
                if target and not any(n["id"] == target for n in nodes):
                    raise ValueError("Cílová karta položky neexistuje.")
            # Mění se jen jedna sekce: mělká kopie stavu a nový seznam; ostatní uzly zůstávají sdílené
            # s uloženým stavem, a proto je `save(base=...)` znovu neověřuje.
            state = {**stored["state"], collection: list(stored["state"][collection])}
            items = state[collection]
            if operation == "add":
                items.append(replacement)
            else:
                index = next(i for i, x in enumerate(items) if x["id"] == identifier)
                if operation == "remove":
                    items.pop(index)
                else:
                    items[index] = replacement
            saved = self.state.save({"project": project, "workspace": workspace,
                                     "expectedRevision": stored["revision"], "state": state}, actor=actor,
                                    base=stored["state"], slim=not full)
            item = next((x for x in state[collection] if x["id"] == identifier), None)
            return {**saved, "item": item}

    def review_rule(self, payload, *, actor, full=False):
        """Člověk schválí nebo zamítne návrh pravidla od agenta (karta, projekt i cesta stejně).

        Schválení = uložení pravidla bez `by` (od té doby platí v `node-brief`), zamítnutí = odebrání.
        Agent dostane 403, neznámý původce 428; `expected` je přečtený návrh (CAS jako u zápisu položky)."""
        require_human(actor, "Návrh pravidla schvaluje nebo zamítá jen člověk v UI.")
        if not isinstance(payload, dict) or set(payload) != REVIEW_KEYS:
            raise ValueError("Posouzení pravidla vyžaduje project, workspace, id, decision a expected.")
        expected, decision = payload["expected"], payload["decision"]
        if decision not in ("approve", "reject"):
            raise ValueError("Posouzení pravidla je approve nebo reject.")
        if not isinstance(expected, dict) or expected.get("by") != "agent":
            raise ValueError("Schválit nebo zamítnout lze jen návrh pravidla od agenta.")
        approved = {key: value for key, value in expected.items() if key != "by"}
        return self.apply("rules", {
            "project": payload["project"], "workspace": payload["workspace"], "id": payload["id"],
            "op": "update" if decision == "approve" else "remove", "expected": expected,
            "item": approved if decision == "approve" else None,
        }, actor=actor, full=full)
