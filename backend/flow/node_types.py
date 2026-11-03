"""Registr typů uzlů v kódu: porty a funkce, která uzel vykoná.

Funkce dostane `ctx` (node, input, config sub-portů, idempotency_key, now) a vrátí jedno z:
- `{"port": "<výstupní port>", "output": ...}`: uzel skončil a tok pokračuje hranami `main` z portu,
- `{"wait": "<na co čeká>", "deadline": <datetime>}`: uzel čeká; po deadline pokračuje portem `timeout`.
"""

from dataclasses import dataclass
from datetime import timedelta

PORT_KINDS = ("main", "model", "memory", "tool", "subagent", "approval")
DEFAULT_APPROVAL_SECONDS = 24 * 3600


@dataclass(frozen=True)
class Port:
    name: str
    direction: str  # "in" | "out"
    kind: str = "main"
    cardinality: str = "many"  # "one" | "many": kolik hran smí port nést
    schema: dict | None = None


@dataclass(frozen=True)
class NodeType:
    type: str
    version: int
    ports: tuple
    run: object
    trigger: bool = False

    def port(self, name, direction):
        return next((p for p in self.ports if p.name == name and p.direction == direction), None)


def _pass_input(ctx):
    """Spouštěč předá data spouštěče, `debug.echo` vrátí svůj vstup."""
    return {"port": "main", "output": ctx["input"]}


def _approval(ctx):
    seconds = int(ctx["node"].get("params", {}).get("timeout_seconds", DEFAULT_APPROVAL_SECONDS))
    return {"wait": "human", "deadline": ctx["now"] + timedelta(seconds=seconds)}


NODE_TYPES = {
    t.type: t
    for t in (
        NodeType("trigger.manual", 1, (Port("main", "out"),), _pass_input, trigger=True),
        NodeType("debug.echo", 1, (Port("main", "in"), Port("main", "out")), _pass_input),
        NodeType(
            "approval.human", 1,
            (Port("main", "in"), Port("approved", "out"), Port("rejected", "out"), Port("timeout", "out")),
            _approval,
        ),
    )
}
