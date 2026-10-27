"""Kontext karty pro agenta z knihovny: `card.fetch` a `card.fill` (`docs/zive-zobrazeni-a-knihovna.md` §5).

Obě pole skládá deterministicky vložení z knihovny (bez modelu) a node-brief je vydá agentovi v `node`, mimo
`specification`, takže nemění `contextVersion` (stejný princip jako `architecture`, `docs/architektura-pro-agenty.md` §4).

- `fetch` = `{files?, docs?}`: co si agent stáhne do kontextu. Aspoň jeden seznam; každý přítomný seznam má
  1–20 různých položek. `files` jsou relativní cesty v repozitáři (`a/b.ts`, bez `..`, bez úvodního `/`, nejvýš
  200 znaků); `docs` totéž nebo adresa `https://`. Prázdný seznam se neukládá, klíč se vynechá. Uložení ověří jen
  tvar; existenci souborů hlídá lint katalogu tam, kde katalog vzniká (vitest nad repozitářem).
- `fill` = 1–11 různých polí karty, která agent vyplní (díry). Povolená jsou jen pole, která agent opravdu umí
  zapsat: `purpose` a `sourceRef` (změna grafu v OporaHubu), `spec.goal` / `spec.non_goals` / `spec.acceptance`
  a `text` (`extend` dávky plánu s revizí), `card.tech` / `card.states` / `card.section` (`extend`), `blocks`
  a `rules` (`extend`). Seznam zrcadlí `CARD_FILL_FIELDS` ve frontendu (`catalog-agent-context.ts`, test hlídá shodu).
"""

import re

from backend.project.workspace.workspace_sources import relative_path

CARD_FILL_FIELDS = ("purpose", "sourceRef", "spec.goal", "spec.non_goals", "spec.acceptance", "text",
                    "card.tech", "card.states", "card.section", "blocks", "rules")
FETCH_KEYS = ("files", "docs")
FETCH_ITEMS_MAX, FETCH_PATH_MAX = 20, 200
HTTPS_URL = re.compile(r"https://[^\s]{1,192}")


def repo_path(value):
    """Relativní cesta v repozitáři: neprázdná, nejvýš 200 znaků, bez `..`, `.git` a úvodního lomítka."""
    if not isinstance(value, str) or not 0 < len(value) <= FETCH_PATH_MAX:
        return False
    try:
        relative_path(value)
    except ValueError:
        return False
    return True


def _fetch_list(items, allow_url):
    return (
        isinstance(items, list)
        and 1 <= len(items) <= FETCH_ITEMS_MAX
        and all(repo_path(item) or (allow_url and isinstance(item, str) and HTTPS_URL.fullmatch(item)) for item in items)
        and len(set(items)) == len(items)
    )


def validate_agent_context(card):
    """Ověří `card.fetch` a `card.fill`, jsou-li; chybějící klíč je v pořádku a nic se nedoplňuje."""
    if "fetch" in card:
        fetch = card["fetch"]
        if (
            not isinstance(fetch, dict)
            or not fetch
            or not set(fetch) <= set(FETCH_KEYS)
            or not all(_fetch_list(fetch[key], key == "docs") for key in fetch)
        ):
            raise ValueError("Neplatné podklady karty fetch ({files, docs}: 1–20 relativních cest v repozitáři).")
    if "fill" in card:
        fill = card["fill"]
        if (
            not isinstance(fill, list)
            or not 1 <= len(fill) <= len(CARD_FILL_FIELDS)
            or not all(isinstance(item, str) and item in CARD_FILL_FIELDS for item in fill)
            or len(set(fill)) != len(fill)
        ):
            raise ValueError("Neplatná pole k vyplnění fill (různá pole z povoleného seznamu karty).")
