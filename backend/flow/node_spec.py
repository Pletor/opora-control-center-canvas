"""Port a typ uzlu: tvar registru `node_types.py`, sdílený s katalogy (`catalogs/*`) bez kruhového importu."""

from dataclasses import dataclass

# data: tok dat záměru stránky; outputParser … reranker: sub-porty katalogu toků dat (`catalogs/data_flow.py`)
PORT_KINDS = ("main", "model", "memory", "tool", "subagent", "approval", "data", "outputParser", "embedding",
              "document", "textSplitter", "retriever", "vectorStore", "reranker")

LAYERS = ("fe", "be", "db", "infra", "ai", "neutral")
INTENTS = ("input", "validate", "compute", "store", "call-service", "show", "decide", "repeat", "trigger", "notify",
           "ai")


@dataclass(frozen=True)
class Port:
    name: str
    direction: str  # "in" | "out"
    kind: str = "main"
    cardinality: str = "many"  # "one" | "many": kolik hran smí port nést
    schema: dict | None = None
    required: bool = False  # povinný port (v editoru `*`): bez hrany je graf toku dat neplatný
    label: str = ""


@dataclass(frozen=True)
class NodeType:
    type: str
    version: int
    ports: tuple
    run: object
    trigger: bool = False
    detached: bool = False  # běží mimo zámek: `running` s čerstvým heartbeatem = „běží jinde“, ne „přerušeno“
    params: dict | None = None  # parametry uzlu pro editor ({jméno: popis}); katalog záměru je jen popisný
    category: str = ""  # kategorie palety editoru (katalog toků dat)
    layer: str = "neutral"  # výchozí vrstva (`LAYERS`); uzel ji smí přepsat polem `layer`
    use: str = ""  # „použij, když…“ (paleta, průvodce, LLM)
    avoid: str = ""  # „nepoužívej, když…“
    intents: tuple = ()  # štítky z `INTENTS` pro průvodce „Co chci udělat?“
    accepts: tuple = ()  # druhy dat (`DATA_KINDS`), které smí přijít hranou do uzlu; prázdné = cokoli
    emits: str = ""  # druh dat, který uzel typicky vydává; prázdné = neurčeno
    dynamic: object = None  # porty podle parametrů uzlu: `dynamic(params) -> tuple[Port]`; `ports` = výchozí params

    def ports_for(self, params=None):
        return self.dynamic(params or {}) if self.dynamic else self.ports

    def port(self, name, direction):
        return next((p for p in self.ports if p.name == name and p.direction == direction), None)
