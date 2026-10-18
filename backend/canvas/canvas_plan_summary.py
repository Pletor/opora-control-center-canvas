"""Souhrn dávky plánu pro kartu schválení i odpověď (`docs/davka-planu.md` §3).

Tvar: „Přidá 1 oblast, 5 sektorů, 23 karet, 61 bloků, 74 portů, 38 vazeb (next 21, block 15,
flow 2), 19 pravidel, 6 rozhodnutí, text u 23 karet.“ Nulové položky se vynechají.

Počítá se z nepřeloženého `plan` (refy, ne UUID): stejnou funkci volá `/api/canvas-plan`
i karta schválení (`approvals.plan_summary`), takže člověk vidí přesně tentýž text, jaký
vrátí backend. Neplatnou dávku nic neodmítá — jen ji počítá (neznámý druh, „jiný“ port);
odmítnutí je věc validace dávky. Jen počty, nikdy texty.
"""

from backend.canvas.graph import EDGE_PORTS

# Tvary (po „Přidá“) pro 1, 2–4 a 5+ kusů.
KINDS = (
    ("area", ("oblast", "oblasti", "oblastí")),
    ("sector", ("sektor", "sektory", "sektorů")),
    ("node", ("kartu", "karty", "karet")),
    ("comment", ("komentář", "komentáře", "komentářů")),
)
UNKNOWN_KIND = ("uzel neznámého druhu", "uzly neznámého druhu", "uzlů neznámého druhu")
OTHER_PORT = "jiný"


def counted(number, forms):
    """Číslo s tvarem podle češtiny: 1 kartu, 2–4 karty, 5 a víc karet."""
    return f"{number} {forms[0] if number == 1 else forms[1] if 2 <= number <= 4 else forms[2]}"


def _items(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def plan_summary(plan):
    """Souhrn z nepřeloženého `plan` (`{nodes, edges, decisions}`)."""
    plan = plan if isinstance(plan, dict) else {}
    nodes, edges = _items(plan.get("nodes")), _items(plan.get("edges"))
    extensions = _items(plan.get("extend"))
    content = nodes + extensions
    blocks = [block for node in content for block in _items(node.get("blocks"))]
    kinds = [node.get("kind", "node") for node in nodes]
    parts = [counted(kinds.count(kind), forms) for kind, forms in KINDS if kinds.count(kind)]
    other = sum(1 for kind in kinds if kind not in dict(KINDS))
    if other:
        parts.append(counted(other, UNKNOWN_KIND))
    ports = sum(len(_items(block.get("ports"))) for block in blocks)
    ports += sum(len(_items(addition.get("ports"))) for item in extensions for addition in _items(item.get("ports")))
    block_count = len(blocks) + sum(node.get("downloadsUrl") is True for node in nodes)
    for number, forms in ((block_count, ("blok", "bloky", "bloků")), (ports, ("port", "porty", "portů"))):
        if number:
            parts.append(counted(number, forms))
    if edges:
        # Vazba bez portu je `next`, stejně jako v dávce i v grafu.
        names = [edge.get("port", "next") for edge in edges]
        names = [name if name in EDGE_PORTS else OTHER_PORT for name in names]
        detail = ", ".join(f"{port} {names.count(port)}" for port in (*EDGE_PORTS, OTHER_PORT) if port in names)
        parts.append(f"{counted(len(edges), ('vazbu', 'vazby', 'vazeb'))} ({detail})")
    rules = sum(len(_items(node.get("rules"))) for node in content)
    decisions = len(_items(plan.get("decisions")))
    for number, forms in ((rules, ("pravidlo", "pravidla", "pravidel")), (decisions, ("rozhodnutí",) * 3)):
        if number:
            parts.append(counted(number, forms))
    texts = sum(1 for node in nodes if isinstance(node.get("text"), str) and node["text"].strip())
    if texts:
        parts.append(f"text u {texts} {'karty' if texts == 1 else 'karet'}")
    result = ("Přidá " + ", ".join(parts) + ".") if parts else ""
    if extensions:
        result += (" " if result else "") + f"Rozšíří {len(extensions)} existujících karet; spec {sum('spec' in item for item in extensions)}, text {sum('text' in item for item in extensions)}."
        replaced = sum(item.get("replaceBlocks") is True for item in extensions)
        if replaced:
            result += f" Bloky nahradí u {replaced}."
        moved = sum("parent" in item for item in extensions)
        recolored = sum("color" in item for item in extensions)
        if moved or recolored:
            result += f" Přesuny {moved}, změny barev {recolored}."
    return result or "Dávka nic nepřidá."
