"""Port a typ uzlu: tvar registru `node_types.py`, sdílený s katalogy (`catalogs/*`) bez kruhového importu."""

from dataclasses import dataclass

PORT_KINDS = ("main", "model", "memory", "tool", "subagent", "approval")


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
    detached: bool = False  # běží mimo zámek: `running` s čerstvým heartbeatem = „běží jinde“, ne „přerušeno“

    def port(self, name, direction):
        return next((p for p in self.ports if p.name == name and p.direction == direction), None)
