"""Katalog „toky dat“ plátna toku v knihovně (`kind = library_flow`, kontrakt
`docs/navrhy/2026-11-04-knihovna-platna-toku.md` §2, porty a parametry podle n8n).

Plátno toku se nespouští, typy nemají funkci (`run=None`). Po `main` teče `Item[] = {json, binary?, pairedItem?}`
zleva doprava; výstupy `main` mohou mít jméno (`true`/`false`, `loop`/`done`, větve Switch). Sub-porty (`model`,
`memory`, `tool` …) vedou vždy ze sub-uzlu (výstup) do kořenového uzlu (vstup) a nesou kind svého portu. Porty, které
závisí na parametrech (režim vektorového úložiště, `hasOutputParser` agenta, větve Switch a Merge), počítá
`dynamic(params)`; `ports` jsou porty výchozích parametrů. `onError: errorOutput` přidá výstup `error` (`graph_check`).

Vrstvy (`layer`), kroky FE/BE/DB/Infra (`process_layers.py`) a „kdy použít“ (`guidance.py`):
`docs/navrhy/2026-11-04-platno-procesu.md` §1.
"""

from dataclasses import replace

from backend.flow.catalogs.guidance import GUIDANCE
from backend.flow.catalogs.process_layers import PROCESS_TYPES
from backend.flow.node_spec import NodeType, Port

MAIN_IN, MAIN_OUT = Port("main", "in"), Port("main", "out")
LABELS = {"model": "Model", "memory": "Paměť", "tool": "Nástroj", "outputParser": "Výstupní parser",
          "embedding": "Embedding", "document": "Dokument", "textSplitter": "Dělič textu", "retriever": "Retriever",
          "vectorStore": "Vektorové úložiště", "reranker": "Reranker"}
VECTOR_MODES = ("insert", "load", "retrieve", "retrieveAsTool")
CHAIN_TYPES = ("llm", "qa", "classify", "extract", "summarize")


def sub_in(kind, required=False, one=True):
    """Sub-port kořenového uzlu (dole); `one` = nejvýš jedna hrana (n8n `maxConnections: 1`)."""
    return Port(kind, "in", kind, "one" if one else "many", required=required, label=LABELS[kind])


def sub_out(kind):
    return Port(kind, "out", kind, label=LABELS[kind])


def outs(*names):
    return tuple(Port(name, "out", label=name) for name in names)


def _agent(params):
    parser = (sub_in("outputParser"),) if params.get("hasOutputParser") else ()
    return (MAIN_IN, sub_in("model", required=True), sub_in("memory"), sub_in("tool", one=False), *parser, MAIN_OUT)


def _chain(params):
    kind = params.get("chainType", "llm")
    retriever = (sub_in("retriever", required=True),) if kind == "qa" else ()
    parser = () if kind == "classify" else (sub_in("outputParser"),)
    out = outs(*[str(c) for c in params.get("categories") or ()]) if kind == "classify" else ()
    return (MAIN_IN, sub_in("model", required=True), *retriever, *parser, *(out or (MAIN_OUT,)))


def _vector_store(params):
    mode = params.get("mode", "insert")
    embedding, reranker = sub_in("embedding", required=True), sub_in("reranker")
    if mode == "insert":
        return (MAIN_IN, embedding, sub_in("document", required=True), MAIN_OUT)
    if mode == "retrieveAsTool":
        return (embedding, reranker, sub_out("tool"))
    if mode == "retrieve":
        return (embedding, reranker, sub_out("vectorStore"))
    return (MAIN_IN, embedding, reranker, MAIN_OUT)  # load: Get Many přímo v toku


def _switch(params):
    names = [str(rule.get("output") or i) for i, rule in enumerate(params.get("rules") or ()) if isinstance(rule, dict)]
    fallback = ("fallback",) if params.get("fallback") == "extra" else ()
    return (MAIN_IN, *outs(*(names or ["0"]), *fallback))


def _merge(params):
    count = params.get("numberInputs", 2)
    count = count if isinstance(count, int) and 2 <= count <= 10 else 2
    return (*(Port(f"input{i}", "in", label=f"Vstup {i}") for i in range(1, count + 1)), MAIN_OUT)


def _type(name, category, ports, params, dynamic=None, trigger=False):
    return NodeType(name, 1, dynamic({}) if dynamic else ports, None, trigger=trigger, params=params,
                    category=category, dynamic=dynamic)


def _trigger(name, params):
    return _type(f"trigger.{name}", "trigger", (MAIN_OUT,), params, trigger=True)


def _ai_sub(name, out, params, ins=()):
    return _type(f"ai.{name}", "ai", (*ins, sub_out(out)), params)


FLOW_TYPES = {
    t.type: t
    for t in (
        _trigger("manual", {}),
        _trigger("schedule", {"rules": "[{interval: minutes|hours|days|weeks|months|cron, value}]"}),
        _trigger("webhook", {"path": "cesta", "method": "GET | POST | …"}),
        _trigger("chat", {"responseMode": "lastNode | responseNodes | streaming"}),
        _trigger("form", {"title": "titulek", "fields": "[{name, type, required}]"}),
        _trigger("subflowInput", {"inputSchema": "JSON Schema vstupu, nebo příklad"}),
        _trigger("evaluation", {"dataset": "zdroj dat evaluace", "limit": "nejvýš řádků"}),
        _type("transform.set", "transform", (MAIN_IN, MAIN_OUT),
              {"assignments": "[{name, type, value}]", "includeOtherFields": "true | false"}),
        _type("transform.code", "transform", (MAIN_IN, MAIN_OUT),
              {"language": "js | python", "code": "kód", "mode": "perItem | once"}),
        _type("flow.if", "flow", (MAIN_IN, *outs("true", "false")),
              {"conditions": "[{left, operator, right}]", "combinator": "and | or"}),
        _type("flow.switch", "flow", (), {"rules": "[{condition, output?}]", "fallback": "none | extra | first",
                                          "allMatching": "true | false"}, _switch),
        _type("flow.merge", "flow", (), {"mode": "append | combine | sql | chooseBranch", "numberInputs": "2–10",
                                         "matchFields": "[pole]"}, _merge),
        _type("flow.loop", "flow", (MAIN_IN, *outs("loop", "done")), {"batchSize": "velikost dávky", "reset": "bool"}),
        _type("flow.wait", "flow", (MAIN_IN, MAIN_OUT), {"resume": "time | webhook | form", "amount": "kolik"}),
        _type("flow.subflow", "flow", (MAIN_IN, MAIN_OUT),
              {"flowId": "id plátna toku", "mode": "perItem | once", "inputMapping": "{pole: výraz}", "wait": "bool"}),
        _type("flow.stopError", "flow", (MAIN_IN,), {"message": "text chyby"}),
        _type("ai.agent", "ai", (), {"prompt": "výraz vstupu", "systemMessage": "systémová zpráva",
                                     "hasOutputParser": "true | false"}, _agent),
        _type("ai.chain", "ai", (), {"chainType": " | ".join(CHAIN_TYPES), "prompt": "výraz vstupu",
                                     "categories": "[kategorie] (classify)"}, _chain),
        _ai_sub("model", "model", {"provider": "poskytovatel", "model": "model", "temperature": "0–1"}),
        _ai_sub("memory", "memory", {"sessionKey": "výraz klíče relace", "window": "počet zpráv"}),
        _ai_sub("tool", "tool", {"toolType": "code | http | subflow | mcp", "name": "jméno", "description": "popis",
                                 "schema": "JSON Schema vstupu"}),
        _type("ai.vectorStore", "ai", (), {"mode": " | ".join(VECTOR_MODES), "index": "index", "namespace": "jmenný "
                                           "prostor", "topK": "počet", "includeMetadata": "bool"}, _vector_store),
        _ai_sub("embedding", "embedding", {"model": "model"}),
        _ai_sub("documentLoader", "document", {"dataType": "json | binary", "metadata": "[{name, value}]"},
                (sub_in("textSplitter"),)),
        _ai_sub("textSplitter", "textSplitter", {"splitter": "char | recursive | token", "chunkSize": "velikost",
                                                 "overlap": "překryv"}),
        _ai_sub("retriever", "retriever", {"topK": "počet"}, (sub_in("vectorStore", required=True),)),
        _ai_sub("outputParser", "outputParser", {"jsonSchema": "JSON Schema", "example": "příklad výstupu"}),
        _ai_sub("reranker", "reranker", {"model": "model", "topN": "počet"}),
        _type("human.approval", "human", (MAIN_IN, *outs("approved", "rejected", "timeout")),
              {"channel": "kde člověk schvaluje", "message": "co schvaluje", "timeoutSeconds": "limit"}),
    )
}

FLOW_TYPES.update({t.type: t for t in PROCESS_TYPES})
FLOW_TYPES = {
    name: replace(t, layer="ai" if name.startswith("ai.") else t.layer, **dict(zip(("use", "avoid", "intents"),
                                                                                  GUIDANCE[name])))
    for name, t in FLOW_TYPES.items()
}
