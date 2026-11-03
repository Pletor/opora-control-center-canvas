"""Sekce WEB snímku srdce (docs/navrhy/2026-11-03-platno-2-zamer-stranky.md §7).

Nese jen vyplněná pole nastavení webu projektu (`settings.site`: seo, legal, email, design) a přebití stránek
(`site.seo`, `site.design` uzlu stránky). Nic vyplněného = sekce chybí, ať snímek projektu bez webu zůstane stejný.
"""

VALUE = 80  # znaků hodnoty pole
OVERRIDES = 5  # nejvýš stránek s přebitím


def _short(value, limit=VALUE):
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def filled(value, path=""):
    """`[(cesta, hodnota)]` neprázdných textů ve vnořeném slovníku, v uloženém pořadí."""
    if isinstance(value, dict):
        return [item for key, inner in value.items() for item in filled(inner, f"{path}{key}.")]
    return [(path.rstrip("."), value)] if isinstance(value, str) and value.strip() else []


def _row(head, pairs):
    return f"- {head} · " + " · ".join(f"{path}: {_short(value)}" for path, value in pairs)


def lines(site, pages):
    """Řádky sekce WEB: jedna řádka na vyplněnou část projektu, pak stránky s přebitím (`overrides`)."""
    rows = []
    for part, value in (site or {}).items():
        pairs = filled(value)
        if pairs:
            rows.append(_row(part, pairs))
    overriding = [page for page in pages if page.get("overrides")]
    for page in overriding[:OVERRIDES]:
        rows.append(_row(f"stránka {page['path'] or page['id']} přebíjí", filled(page["overrides"])))
    if len(overriding) > OVERRIDES:
        rows.append(f"- … a další stránky s přebitím ({len(overriding) - OVERRIDES})")
    return ["WEB:", *rows] if rows else []
