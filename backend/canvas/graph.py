import hashlib
import json
import math
import re
from datetime import date

from backend.project.workspace.workspace_sources import relative_path

EMPTY = {"nodes": [], "edges": []}
NODE_KEYS = {"id", "parentId", "kind", "name", "purpose", "x", "y"}
NODE_KEYS_WITH_SOURCE = NODE_KEYS | {"sourceRef"}
# `size` patří jen oblasti (kind "area"): dashovaný obdélník, který geometricky seskupuje
# karty na plátně. Oblast nikdy nenese zdroj, takže se `size` a `sourceRef` nekombinují.
NODE_KEYS_WITH_SIZE = NODE_KEYS | {"size"}
AREA_SIZE_MIN, AREA_SIZE_MAX = 120, 20000
# `blockOffsets` je nepovinný posun bočních bloků (akce / pravidla / podklady) proti kartě: uživatel
# si blok odtáhl jinam a poloha má přežít uložení. Je relativní, takže karta bloky bere s sebou;
# chybějící port stojí na výchozím místě u karty. Smí doplnit kterýkoli z tvarů uzlu výše.
BLOCK_OFFSET_PORTS = {"action", "rule", "material"}
# `color` je nepovinná barva rámečku oblasti, aby šly skupiny na plátně rozeznat od sebe;
# smí ji nést jen oblast (kind "area") a jen jedna z šesti hodnot (viz `AREA_COLORS`).
AREA_COLORS = ("indigo", "teal", "amber", "rose", "violet", "slate")
# `card` je nepovinná karta uzlu (jen kind "node"): vrstva (otázka frontend / backend / database /
# library z `docs/pravidla-struktury.md`), ruční stav, termín a doporučený model s effortem.
# Typ workflow se neukládá, čte se jen z předpony názvu (`[task] …`). `done` se nikdy neukládá, odvozuje se z uzavření karty (`done.confirmed`).
# Kontrakt: `docs/kontext-karet-a-index.md` §1.
CARD_VALUES = {
    "layer": ("frontend", "backend", "database", "library"),
    "status": ("draft", "ready"),
    "model": ("fable", "opus", "sonnet", "haiku"),
    "effort": ("low", "medium", "high", "xhigh", "max"),
}
CARD_KEYS = set(CARD_VALUES) | {"due"}
NODE_KEY_SETS = tuple(
    keys | offsets | color | card
    for keys in (NODE_KEYS, NODE_KEYS_WITH_SOURCE, NODE_KEYS_WITH_SIZE)
    for offsets in (set(), {"blockOffsets"})
    for color in (set(), {"color"})
    for card in (set(), {"card"})
)
EDGE_KEYS = {"id", "source", "target"}
# Port karty, ze kterého vazba vede; chybějící port u starších vazeb znamená `next`.
# `block` je tlačítko bloku: vazba pak povinně nese blok a port, ze kterého se táhne.
# `flow` je tok mezi oblastmi: smí spojovat jen dvě oblasti, nikdy uzel/sektor/komentář.
EDGE_PORTS = ("next", "action", "rule", "block", "flow")
EDGE_KEYS_WITH_PORT = EDGE_KEYS | {"port"}
EDGE_KEYS_WITH_BLOCK_PORT = EDGE_KEYS_WITH_PORT | {"sourceBlockId", "sourcePortId"}
EDGE_KEY_SETS = (EDGE_KEYS, EDGE_KEYS_WITH_PORT, EDGE_KEYS_WITH_BLOCK_PORT)


def valid_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value))


def validate_source_ref(ref, kind):
    """Ověří tvar odkazu na skutečný nebo navrhovaný zdroj; nesahá na disk."""
    if ref is None:
        return
    if not isinstance(ref, dict) or set(ref) != {"origin", "path", "kind"}:
        raise ValueError("Neplatný odkaz na zdroj.")
    if ref["origin"] not in ("existing", "planned"):
        raise ValueError("Neplatný typ odkazu na zdroj.")
    if ref["kind"] not in ("directory", "file"):
        raise ValueError("Neplatný druh zdroje.")
    if kind == "sector" and ref["kind"] != "directory":
        raise ValueError("Sektor může mít jen adresářový zdroj.")
    try:
        relative_path(ref["path"])
    except ValueError:
        raise ValueError("Neplatná cesta zdroje.")
    if kind == "node" and ref["origin"] == "existing" and ref["path"] == "":
        raise ValueError("Uzel musí odkazovat na potomka sektoru, ne na kořen.")


def validate_block_offsets(offsets):
    """Ověří posun odtažených bočních bloků: jen známé porty a v každém konečné `dx`/`dy`."""
    if not isinstance(offsets, dict) or not set(offsets) <= BLOCK_OFFSET_PORTS:
        raise ValueError("Neplatný posun bloků.")
    for spot in offsets.values():
        if not isinstance(spot, dict) or set(spot) != {"dx", "dy"}:
            raise ValueError("Neplatný posun bloků.")
        if any(
            type(spot[k]) not in (int, float) or not math.isfinite(spot[k]) or abs(spot[k]) > 1000000
            for k in ("dx", "dy")
        ):
            raise ValueError("Neplatný posun bloků.")


def valid_date(value):
    """Platné kalendářní datum přesně ve tvaru YYYY-MM-DD."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_card(card):
    """Ověří kartu uzlu: neprázdný objekt jen se známými klíči a povolenými hodnotami."""
    if not isinstance(card, dict) or not card or not set(card) <= CARD_KEYS:
        raise ValueError("Neplatná karta uzlu.")
    for key, allowed in CARD_VALUES.items():
        if key in card and card[key] not in allowed:
            raise ValueError("Neplatná karta uzlu.")
    if "due" in card and not valid_date(card["due"]):
        raise ValueError("Neplatný termín karty.")


def validate_graph(value):
    if not isinstance(value, dict) or set(value) != {"nodes", "edges"}:
        raise ValueError("Neplatný formát grafu.")
    nodes, edges = value["nodes"], value["edges"]
    if (
        not isinstance(nodes, list)
        or not isinstance(edges, list)
        or len(nodes) > 2000
        or len(edges) > 4000
    ):
        raise ValueError("Graf překročil povolený rozsah.")
    ids = set()
    sources = {}
    for n in nodes:
        if not isinstance(n, dict) or set(n) not in NODE_KEY_SETS:
            raise ValueError("Neplatný uzel.")
        if not valid_id(n["id"]) or n["id"] in ids or n["kind"] not in ("node", "sector", "comment", "area"):
            raise ValueError("Neplatná identita nebo typ uzlu.")
        # Komentář je lístek na plátně: nemá zdroj, není rodičem a nikdy nenese vazbu (viz níže).
        if n["kind"] == "comment" and "sourceRef" in n:
            raise ValueError("Komentář nemá zdroj.")
        # Oblast je dashovaný obdélník, který geometricky seskupuje karty na plátně: nemá
        # zdroj, není rodičem (viz níže) a jediná ze všech druhů uzlů nese rozměr `size`.
        if n["kind"] == "area" and "sourceRef" in n:
            raise ValueError("Oblast nemá zdroj.")
        if n["kind"] == "area" and "size" not in n:
            raise ValueError("Oblast musí mít rozměr.")
        if n["kind"] != "area" and "size" in n:
            raise ValueError("Rozměr smí mít jen oblast.")
        if "size" in n:
            size = n["size"]
            if (
                not isinstance(size, dict)
                or set(size) != {"w", "h"}
                or any(
                    type(size[k]) not in (int, float)
                    or not math.isfinite(size[k])
                    or not (AREA_SIZE_MIN <= size[k] <= AREA_SIZE_MAX)
                    for k in ("w", "h")
                )
            ):
                raise ValueError("Neplatný rozměr oblasti.")
        # Barvu smí nést jen oblast, a jen jednu ze šesti povolených hodnot.
        if "color" in n and (n["kind"] != "area" or n["color"] not in AREA_COLORS):
            raise ValueError("Neplatná barva oblasti.")
        # Boční bloky patří jen ke kartě uzlu nebo sektoru; komentář ani oblast je nemají.
        if "blockOffsets" in n:
            if n["kind"] not in ("node", "sector"):
                raise ValueError("Posun bloků má jen uzel nebo sektor.")
            validate_block_offsets(n["blockOffsets"])
        # Kartu (druh, stav, termín, model, effort) nese jen uzel; sektor, komentář ani oblast ne.
        if "card" in n:
            if n["kind"] != "node":
                raise ValueError("Kartu má jen uzel.")
            validate_card(n["card"])
        if (
            not isinstance(n["name"], str)
            or (n["kind"] != "area" and not n["name"].strip())
            or len(n["name"]) > 160
            or not isinstance(n["purpose"], str)
            or len(n["purpose"]) > 12000
        ):
            raise ValueError("Neplatný název nebo podstata.")
        if any(
            type(n[k]) not in (int, float) or not math.isfinite(n[k]) or abs(n[k]) > 1000000
            for k in ("x", "y")
        ):
            raise ValueError("Neplatná pozice.")
        source_ref = n.get("sourceRef") if "sourceRef" in n else None
        validate_source_ref(source_ref, n["kind"])
        if (
            n["kind"] == "sector"
            and source_ref
            and source_ref["origin"] == "planned"
            and len(n["purpose"].strip()) < 12
        ):
            raise ValueError("Návrh sektoru vyžaduje smysluplnou podstatu.")
        sources[n["id"]] = source_ref
        ids.add(n["id"])
    parents = {n["id"]: n["parentId"] for n in nodes}
    kinds = {n["id"]: n["kind"] for n in nodes}
    for key in ids:
        seen = set()
        current = key
        while current is not None:
            if current not in ids or current in seen:
                raise ValueError("Graf má cyklus nebo chybějícího rodiče.")
            seen.add(current)
            current = parents[current]
    for parent_id in parents.values():
        if parent_id is None:
            continue
        if kinds[parent_id] == "comment":
            raise ValueError("Komentář nesmí být rodičem.")
        if kinds[parent_id] == "area":
            raise ValueError("Oblast nesmí být rodičem.")
    for node_id, source_ref in sources.items():
        if source_ref is None or kinds[node_id] != "node":
            continue
        cursor = parents[node_id]
        has_sector = False
        while cursor is not None:
            if kinds[cursor] == "sector":
                has_sector = True
                break
            cursor = parents[cursor]
        if not has_sector:
            raise ValueError("Uzel se zdrojem musí ležet uvnitř sektoru.")
    edge_ids = set()
    for edge in edges:
        if (
            not isinstance(edge, dict)
            or set(edge) not in EDGE_KEY_SETS
            or ("port" in edge and edge["port"] not in EDGE_PORTS)
            or not valid_id(edge["id"])
            or edge["id"] in edge_ids
            or edge["source"] not in ids
            or edge["target"] not in ids
            or edge["source"] == edge["target"]
        ):
            raise ValueError("Neplatná vazba.")
        source_kind, target_kind = kinds[edge["source"]], kinds[edge["target"]]
        if source_kind == "comment" or target_kind == "comment":
            raise ValueError("Komentář nemá vazby.")
        # Tok (`flow`) smí spojovat jen dvě oblasti; jiný port mezi oblastmi stejně jako
        # `flow` mimo oblasti je vždy chyba.
        if source_kind == "area" or target_kind == "area" or edge.get("port") == "flow":
            if source_kind != "area" or target_kind != "area" or edge.get("port") != "flow":
                raise ValueError("Tok vede jen mezi oblastmi.")
        # Blok a port zdroje patří jen k portu `block` a naopak: půlka zápisu je vždy chyba.
        from_block = edge.get("port") == "block"
        if from_block != ("sourceBlockId" in edge):
            raise ValueError("Vazba z tlačítka bloku vyžaduje port block se sourceBlockId a sourcePortId.")
        if from_block and not (valid_id(edge["sourceBlockId"]) and valid_id(edge["sourcePortId"])):
            raise ValueError("Neplatný blok nebo port zdroje vazby.")
        edge_ids.add(edge["id"])
    return value


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()
