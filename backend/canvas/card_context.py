"""Kontext karty: efektivní druh a stav, čitelná cesta a adresa (počítá se, neukládá se).

Kontrakt je `docs/kontext-karet-a-index.md` §1 a §3. Frontend má stejná pravidla v
`frontend/shared/card-context/logic/card-context.ts`; obě strany se testují na stejné případy.

- Typ workflow: čte se jen z předpony názvu přesně ve tvaru `[research] `, `[prototype] `,
  `[grilling] ` nebo `[task] ` (malými písmeny, s mezerou). Neukládá se, název se nikdy nemění.
- Vrstva karty: uložené `card.layer` (`frontend` / `backend` / `database` / `library`), jinak `None`.
- Stav karty: `done`, když je karta uzavřená (`done.confirmed`); jinak `card.status`; jinak
  `None` (neznámé, ne „draft“). `done` se do grafu nikdy neukládá.
- Adresa: slugy názvů předků a karty spojené `/`. Nikdy není klíčem ani odkazem; stabilní
  `id` zůstává jediným klíčem.
"""

import re
import unicodedata

CARD_TYPES = ("research", "prototype", "grilling", "task")
TYPE_PREFIXES = {f"[{kind}] ": kind for kind in CARD_TYPES}
CARD_LAYERS = ("frontend", "backend", "database", "library")
# Krátký štítek vrstvy v UI i v korpusu hledání (filtr `vrstva:fe|be|db|knihovna`).
LAYER_LABELS = {"frontend": "FE", "backend": "BE", "database": "DB", "library": "Knihovna"}


def _card(node):
    card = node.get("card") if isinstance(node, dict) else None
    return card if isinstance(card, dict) else {}


def prefix_type(name):
    """Druh z předpony názvu, nebo None, když název přesnou předponou nezačíná."""
    if not isinstance(name, str):
        return None
    for prefix, kind in TYPE_PREFIXES.items():
        if name.startswith(prefix):
            return kind
    return None


def effective_type(node):
    """Typ workflow z předpony názvu, jinak None."""
    return prefix_type(node.get("name") if isinstance(node, dict) else None)


def card_layer(node):
    """Uložená vrstva karty, jinak None."""
    stored = _card(node).get("layer")
    return stored if stored in CARD_LAYERS else None


def effective_status(node, done_confirmed):
    """`done` u uzavřené karty, jinak ruční `card.status`, jinak None."""
    if done_confirmed:
        return "done"
    return _card(node).get("status") or None


def strip_type_prefix(name):
    """Název bez předpony druhu (jen pro slug; uložený název se nemění)."""
    kind = prefix_type(name)
    return name[len(f"[{kind}] "):] if kind else name


def fold(text):
    """Text bez diakritiky a bez rozdílu velikosti písmen (pro slug i hledání)."""
    decomposed = unicodedata.normalize("NFKD", text if isinstance(text, str) else "")
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def slug(name, node_id):
    """Čitelný kousek adresy: bez diakritiky, malá písmena, mimo `[a-z0-9]` pomlčka; prázdný → id."""
    value = re.sub(r"[^a-z0-9]+", "-", fold(strip_type_prefix(name or ""))).strip("-")
    return value or node_id


def card_chain(nodes_by_id, node):
    """Předci od kořene ke kartě včetně karty; cyklus ani chybějící rodič chain nezacyklí."""
    chain, seen, cursor = [], set(), node
    while cursor is not None and cursor["id"] not in seen:
        seen.add(cursor["id"])
        chain.append(cursor)
        parent_id = cursor.get("parentId")
        cursor = nodes_by_id.get(parent_id) if parent_id else None
    return list(reversed(chain))


def card_path(nodes_by_id, node):
    """Názvy předků a karty shora dolů, např. `["Editor", "Pop-up tvorby"]`."""
    return [item["name"] for item in card_chain(nodes_by_id, node)]


def card_address(nodes_by_id, node):
    """Slugy téže cesty spojené `/`, např. `editor/pop-up-tvorby`."""
    return "/".join(slug(item["name"], item["id"]) for item in card_chain(nodes_by_id, node))
