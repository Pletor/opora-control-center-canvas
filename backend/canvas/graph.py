import hashlib
import json
import math
import re
import unicodedata
from datetime import date

from backend.canvas.card_agent_context import validate_agent_context
from backend.canvas.card_checks import validate_checks
from backend.canvas.design_metadata import validate_design
from backend.canvas.gate_scenario import validate_scenario
from backend.canvas.project_facts import validate_fact_refs
from backend.canvas.site_metadata import SECTION_ID, validate_sites
from backend.canvas.source_realization import validate_realization
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
BLOCK_OFFSET_PORTS = {"action", "rule", "material", "pipeline"}
# `color` je nepovinná barva rámečku oblasti, aby šly skupiny na plátně rozeznat od sebe;
# smí ji nést jen oblast (kind "area") a jen jedna z šesti hodnot (viz `AREA_COLORS`).
AREA_COLORS = ("indigo", "teal", "amber", "rose", "violet", "slate")
# `card` je nepovinná karta uzlu (jen kind "node"): vrstva (otázka frontend / backend / database /
# library z `docs/pravidla-struktury.md`), ruční stav, termín a doporučený model s effortem; u komponenty
# navíc technologie `tech`, stavy `states` a sekce stránky `section` (viz níže).
# Typ workflow se neukládá, čte se jen z předpony názvu (`[task] …`). `done` se nikdy neukládá, odvozuje se z uzavření karty (`done.confirmed`).
# Kontrakt: `docs/kontext-karet-a-index.md` §1.
CARD_VALUES = {
    "layer": ("frontend", "backend", "database", "library"),
    "status": ("draft", "ready"),
    "model": ("fable", "opus", "sonnet", "haiku"),
    "effort": ("low", "medium", "high", "xhigh", "max"),
}
# `tech` a `states` popisují komponentu (kontrakt `docs/architektura-pro-agenty.md` §3.3) a píše je agent:
# `tech` je technologie realizace (1–80 znaků), `states` 1–8 krátkých stavů (každý 1–40 znaků, jedinečný).
# Prázdná hodnota se neukládá, klíč se vynechá; chybějící klíč nemění digest ani `contextVersion`.
CARD_TECH_MAX = 80
CARD_STATES_MAX, CARD_STATE_MAX = 8, 40
# `section` je id sekce nejbližší stránky, kterou komponenta realizuje (§3.3). Uložení ověří jen tvar id
# (`SECTION_ID`), ne existenci sekce: smazání sekce na stránce nesmí zablokovat uložení mapy. Neexistující
# sekci odmítne dávka plánu agenta a kontrola mapy ji ohlásí jako `section.unknown`.
# `fetch` a `fill` skládá vložení z knihovny: co si agent stáhne a která pole karty vyplní
# (`docs/zive-zobrazeni-a-knihovna.md` §5, tvar v `card_agent_context.py`). Nejsou součást zadání.
CARD_KEYS = set(CARD_VALUES) | {"due", "tech", "states", "section", "fetch", "fill"}
# `memberOf` je nepovinné výslovné logické členství uzlu nebo sektoru v oblasti (H01, kontrakt
# `docs/kontrakt-identity.md`): id oblasti se stejným rodičem. Oblast tím nezačne být rodičem a
# geometrické `areaId` (`areas.area_of`) zůstává jen nápovědou plátna, ne členstvím.
# `order` je nepovinné pořadí uzlu nebo sektoru podle záměru (1–9999, doporučeně fáze × 100 + pozice,
# `docs/navrhy/2026-10-31-poradi-karty.md`): jen láme remízu v pořadí karet, nikdy neblokuje jako vazba.
NODE_ORDER_MIN, NODE_ORDER_MAX = 1, 9999
# Uzel má právě jeden základ klíčů a k němu libovolnou podmnožinu nepovinných klíčů.
NODE_BASE_KEY_SETS = (NODE_KEYS, NODE_KEYS_WITH_SOURCE, NODE_KEYS_WITH_SIZE)
NODE_OPTIONAL_KEYS = {"blockOffsets", "color", "card", "site", "design", "gateNodeId", "checks", "goal_mode",
                      "factRefs", "realization", "scenario", "memberOf", "order"}


def valid_node_keys(keys):
    """Klíče uzlu = jeden základ (`NODE_BASE_KEY_SETS`) a libovolná podmnožina `NODE_OPTIONAL_KEYS`."""
    keys = set(keys)
    return any(base <= keys and keys - base <= NODE_OPTIONAL_KEYS for base in NODE_BASE_KEY_SETS)


EDGE_KEYS = {"id", "source", "target"}
# Port karty, ze kterého vazba vede; chybějící port u starších vazeb znamená `next`.
# `block` je tlačítko bloku: vazba pak povinně nese blok a port, ze kterého se táhne.
# `flow` je tok mezi oblastmi: smí spojovat jen dvě oblasti, nikdy uzel/sektor/komentář.
EDGE_PORTS = ("next", "action", "rule", "block", "flow")
EDGE_KEYS_WITH_PORT = EDGE_KEYS | {"port"}
EDGE_KEYS_WITH_BLOCK_PORT = EDGE_KEYS_WITH_PORT | {"sourceBlockId", "sourcePortId"}
# Co po vazbě teče (`docs/architektura-pro-agenty.md` §3.4): navigace zákazníka, čtení dat, odeslání/zápis,
# událost. Nepovinné, nikdy se nedoplňuje; smí ho mít jen vazba `next` (i bez portu). Port se tím nemění.
EDGE_CARRIES = ("navigation", "data", "command", "event")
EDGE_KEY_SETS = (EDGE_KEYS, EDGE_KEYS_WITH_PORT, EDGE_KEYS_WITH_BLOCK_PORT,
                 EDGE_KEYS | {"carries"}, EDGE_KEYS_WITH_PORT | {"carries"})


def edge_carries_error(edge):
    """Důvod, proč vazba nesmí nést `carries`, nebo None; vazba bez `carries` je vždy v pořádku."""
    if "carries" not in edge:
        return None
    if edge["carries"] not in EDGE_CARRIES:
        return "Neznámý druh toku vazby (carries)."
    if edge.get("port", "next") != "next":
        return "Druh toku (carries) smí mít jen vazba next."
    return None


def valid_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value))


def payload_project(payload):
    """Projekt z těla požadavku pro výběr zámku projektu; neplatné tělo = klientská chyba."""
    project = payload.get("project") if isinstance(payload, dict) else None
    if project != "draft" and not valid_id(project):
        raise ValueError("Neplatné ID projektu.")
    return project


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
    if "tech" in card and not card_text(card["tech"], CARD_TECH_MAX):
        raise ValueError("Neplatná technologie karty (1–80 znaků bez okrajových mezer).")
    if "states" in card:
        states = card["states"]
        if (
            not isinstance(states, list)
            or not 1 <= len(states) <= CARD_STATES_MAX
            or not all(card_text(state, CARD_STATE_MAX) for state in states)
            or len({state.casefold() for state in states}) != len(states)
        ):
            raise ValueError("Neplatné stavy karty (1–8 různých stavů po 1–40 znacích).")
    if "section" in card and not (isinstance(card["section"], str) and SECTION_ID.fullmatch(card["section"])):
        raise ValueError("Neplatná sekce karty (id sekce: písmena, číslice, _ a -, nejvýše 80 znaků).")
    validate_agent_context(card)


def card_text(value, limit):
    """Krátký text karty: neprázdný, bez okrajových mezer a řídicích znaků, nejvýše `limit` znaků."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= limit
        and value == value.strip()
        and not any(unicodedata.category(char) == "Cc" for char in value)
    )


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
        if not isinstance(n, dict) or not valid_node_keys(n):
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
        validate_checks(n)
        validate_fact_refs(n)
        if "scenario" in n:
            if n["kind"] != "node":
                raise ValueError("Scénář patří jen kartě uzlu.")
            validate_scenario(n["scenario"])
        if "realization" in n:
            if n["kind"] not in ("node", "sector") or not n.get("sourceRef"):
                raise ValueError("Realizace patří kartě s cestou zdroje.")
            validate_realization(n["realization"])
        if "design" in n:
            if n["kind"] != "node":
                raise ValueError("Návrh patří pouze uzlu.")
            validate_design(n["design"])
        if "card" in n:
            if n["kind"] != "node":
                raise ValueError("Kartu má jen uzel.")
            validate_card(n["card"])
        if "memberOf" in n and (n["kind"] not in ("node", "sector") or not valid_id(n["memberOf"])):
            raise ValueError("Členství v oblasti má jen uzel nebo sektor.")
        if "order" in n and (
            n["kind"] not in ("node", "sector")
            or type(n["order"]) is not int
            or not NODE_ORDER_MIN <= n["order"] <= NODE_ORDER_MAX
        ):
            raise ValueError("Pořadí podle záměru má jen uzel nebo sektor a je celé číslo 1–9999.")
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
    for node in nodes:
        # Členství je výslovné a ověřené: oblast musí existovat ve stejném grafu (tedy ve stejném
        # projektu a prostoru) a mít stejného rodiče. Přesun ani smazání oblasti ho tiše nepřemapuje.
        if "memberOf" in node and (
            kinds.get(node["memberOf"]) != "area" or parents[node["memberOf"]] != node["parentId"]
        ):
            raise ValueError(
                "Členství v oblasti musí mířit na existující oblast se stejným rodičem; "
                "před přesunem karty nebo smazáním oblasti členství zrušte."
            )
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
    for node in nodes:
        if "gateNodeId" not in node:
            continue
        gate_id = node["gateNodeId"]
        if node["kind"] != "sector" or not valid_id(gate_id) or kinds.get(gate_id) != "node":
            raise ValueError("Brána sektoru musí být existující karta; před smazáním brány zrušte její přiřazení.")
        cursor = parents[gate_id]
        while cursor is not None and kinds[cursor] != "sector":
            cursor = parents[cursor]
        if cursor != node["id"]:
            raise ValueError("Brána musí patřit do svého nejbližšího sektoru.")
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
        if carries_error := edge_carries_error(edge):
            raise ValueError(carries_error)
        source_kind, target_kind = kinds[edge["source"]], kinds[edge["target"]]
        if source_kind == "comment" or target_kind == "comment":
            raise ValueError("Komentář nemá vazby.")
        # Tok (`flow`) smí spojovat jen dvě oblasti; jiný port mezi oblastmi stejně jako
        # `flow` mimo oblasti je vždy chyba.
        if (source_kind == "area" or target_kind == "area" or edge.get("port") == "flow") and (
            source_kind != "area" or target_kind != "area" or edge.get("port") != "flow"
        ):
            raise ValueError("Tok vede jen mezi oblastmi.")
        # Blok a port zdroje patří jen k portu `block` a naopak: půlka zápisu je vždy chyba.
        from_block = edge.get("port") == "block"
        if from_block != ("sourceBlockId" in edge):
            raise ValueError("Vazba z tlačítka bloku vyžaduje port block se sourceBlockId a sourcePortId.")
        if from_block and not (valid_id(edge["sourceBlockId"]) and valid_id(edge["sourcePortId"])):
            raise ValueError("Neplatný blok nebo port zdroje vazby.")
        edge_ids.add(edge["id"])
    validate_sites(nodes)
    return value


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()
