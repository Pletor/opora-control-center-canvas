"""Vrstvy plátna toku: `via` hrany musí sedět na dvojici vrstev a `data` hrany má tvar (`docs/navrhy/2026-11-04-platno-procesu.md` §1–§2)."""

DATA_KINDS = ("text", "number", "json", "table", "document", "vector", "file", "event")
VIA_ALL = ("http", "sql", "event", "call", "render")
# povolené `via` podle (vrstva zdroje, vrstva cíle); stejná vrstva a vrstvy ai / neutral: libovolné
VIA = {("fe", "be"): ("http", "event"), ("be", "fe"): ("http", "event", "render"), ("be", "db"): ("sql", "call"),
       ("db", "be"): ("sql", "call"), ("be", "infra"): ("http", "call", "event"),
       ("infra", "be"): ("http", "call", "event"), ("fe", "infra"): ("http",)}


def _layer(node, types):
    return node.get("layer") or types[node["id"]].layer


def edge_errors(edge, source, target, types):
    """`via` smí být jen z povolených pro dvojici vrstev, `data` má tvar `{kind, schema?, example?}`."""
    eid, data, via = edge["id"], edge.get("data"), edge.get("via")
    pair = (_layer(source, types), _layer(target, types))
    errors = []
    if data is not None and not (isinstance(data, dict) and data.get("kind") in DATA_KINDS
                                 and isinstance(data.get("schema", {}), dict)):
        errors.append(f"Hrana {eid}: data je {{kind: {' | '.join(DATA_KINDS)}, schema?: objekt, example?}}.")
    kind = data["kind"] if isinstance(data, dict) and data.get("kind") in DATA_KINDS else types[source["id"]].emits
    accepts = types[target["id"]].accepts
    if kind and accepts and kind not in accepts:
        errors.append(f"Hrana {eid}: {source['id']} → {target['id']}: {target['id']} nepřijímá data druhu '{kind}' "
                      f"(přijímá: {', '.join(accepts)}).")
    if set(pair) == {"fe", "db"}:
        errors.append(f"Hrana {eid}: frontend nesmí sahat do databáze přímo, vlož krok BE.")
    if via is not None and via not in VIA_ALL:
        errors.append(f"Hrana {eid}: via je {' | '.join(VIA_ALL)}.")
    elif via is not None and pair in VIA and via not in VIA[pair]:
        errors.append(f"Hrana {eid}: via {via} nejde z vrstvy {pair[0]} do {pair[1]} (povoleno: {', '.join(VIA[pair])}).")
    elif via is not None and pair not in VIA and pair[0] != pair[1] and not {"ai", "neutral"} & set(pair):
        errors.append(f"Hrana {eid}: mezi vrstvami {pair[0]} → {pair[1]} žádné via neplatí.")
    return errors
