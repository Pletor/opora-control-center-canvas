"""Shrnutí design systému pro srdce, dělníka a kontrolu mapy (kontrakt Správy webu §4).

`summary` je krátký přehled dokumentu: titulek, témata, počty tokenů po rodinách, typografické styly, komponenty
a jen stav nastavení SEO, GDPR a e-mailu (vyplněno = část se liší od výchozí), nikdy hodnoty ani `secretRef`.
`has_design` říká, jestli projekt design systém má (uložený dokument s aspoň jednou barvou, pravidlo `site.no-design`).
`is_web_domain` je kopie `domainKindOf(...) === "web"` z frontendu (`landing/logic/domain-kind.ts`).
"""

from urllib.parse import quote

from backend.project.site_admin import store
from backend.project.site_admin.design_system import empty

SETTINGS = ("seo", "gdpr", "email")


def _count(family, value):
    if family == "type":
        return sum(len(group.get("styles") or []) for group in value["groups"])
    return len(value.get("tokens") or []) if isinstance(value, dict) else 0


def summary(document):
    tokens = document["design"]["tokens"]
    defaults = empty()["settings"]
    return {"revision": document["revision"], "title": document.get("title") or "",
            "themes": [theme["id"] for theme in tokens["color"]["themes"]],
            "tokens": {family: _count(family, value) for family, value in tokens.items()},
            "styles": [style["name"] for group in tokens["type"]["groups"] for style in group.get("styles") or []],
            "components": [component["name"] for component in document["design"]["components"]],
            "settings": {part: document["settings"].get(part) != defaults[part] for part in SETTINGS}}


def has_design(document):
    return document["revision"] > 0 and bool(document["design"]["tokens"]["color"]["tokens"])


def read_summary(service, project):
    """Shrnutí uloženého dokumentu; projekt bez dokumentu (revize 0) = None."""
    document = store.read(service, project)
    return summary(document) if document["revision"] else None


def is_web_domain(node):
    """Doména webu: aplikace (`site.kind application`) mimo Android/iOS, jejíž první host (jinak jméno) nezačíná
    `app.` ani `admin`."""
    site = node.get("site") if isinstance(node.get("site"), dict) else {}
    if site.get("kind") != "application" or site.get("platform") in ("android", "ios"):
        return False
    hosts = [env.get("host") for env in site.get("environments") or [] if isinstance(env, dict)]
    host = next((value for value in hosts if isinstance(value, str) and value.strip()), None) or node.get("name") or ""
    first = host.strip().lower().split(".")[0]
    return not first.startswith("admin") and first != "app"


def design_ref(service, project, graph, card_id):
    """`machine.design` ticketu: `{revision, export}`, když karta leží pod webovou doménou (předek po `parentId`)
    a projekt má design systém; jinak None. Dělník si export stáhne a design jen čte."""
    by_id = {node["id"]: node for node in graph.get("nodes") or []}
    chain, current = [], card_id
    while current in by_id and current not in chain:
        chain.append(current)
        current = by_id[current].get("parentId")
    if not any(is_web_domain(by_id[node]) for node in chain):
        return None
    document = store.read(service, project)
    if not has_design(document):
        return None
    return {"revision": document["revision"], "export": f"/api/site-admin/export?project={quote(project)}"}
