"""Application hosts and page routes annotate the existing graph, never a second tree.

Hosts describe environments only; validation neither resolves DNS nor deploys anything.
Pages share their application's structure across environments and retain ordinary IDs.
"""

import ipaddress
import re
from urllib.parse import unquote, urlsplit

from backend.canvas.payload_errors import invalid, keys_problem

DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)
# Stejný tvar jako `graph.valid_id`; graph importuje tento modul, proto vlastní kopie bez cyklu.
SECTION_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
# Stránka nese záměr člověka (goal, feel, navLabel) a sekce, které navrhuje agent. Vše nepovinné, bez výchozích hodnot.
PAGE_KEYS = {"kind", "path", "goal", "feel", "navLabel", "sections"}
PAGE_TEXT_LIMITS = {"goal": ("cíl stránky", 200), "feel": ("působení stránky", 120), "navLabel": ("popisek v menu", 40)}
SECTION_KEYS = {"id", "role", "name", "intent"}
# Čím sekce posouvá zákazníka v kroku cesty (pain reliever / gain creator, `docs/cesta-zakaznika-a-brief.md` §2.3).
# Nepovinné, prázdné se neukládá, bez výchozí hodnoty.
SECTION_OPTIONAL_KEYS = {"moves"}
SECTION_MOVES_MAX = 120
SECTION_ROLES = ("hero", "cta", "form", "content", "gallery", "proof", "faq", "footer", "custom")
# Aplikace nese cesty zákazníka jako trychtýř stránek, který zadává člověk: cesta je proměna zákazníka (`actor`,
# bod A → bod B), krok je stránka s rolí, posunem, námitkou a signálem přechodu `via`; vazby mezi kroky (kudy
# zákazník jde po mapě) se neukládají, odvodí je stroj (§6). Počty lidí se neukládají (`docs/cesta-zakaznika-a-brief.md`).
APPLICATION_KEYS = {"kind", "environments", "healthPath", "journeys"}
JOURNEY_KEYS = {"id", "name", "steps"}
JOURNEY_TEXT_LIMITS = {"purpose": ("účel cesty", 200), "actor": ("zákazník cesty", 80),
                       "pointA": ("bod A cesty", 200), "pointB": ("bod B cesty", 200)}
JOURNEY_OPTIONAL_KEYS = set(JOURNEY_TEXT_LIMITS)
STEP_KEYS = {"id", "page"}
STEP_OPTIONAL_KEYS = {"label", "shift", "objection", "via", "after"}
STEP_TEXT_LIMITS = {"label": ("role kroku", 60), "shift": ("posun kroku", 160), "objection": ("námitka kroku", 120)}
JOURNEY_FROM_NAV = "nav"
# Signál přechodu: co zákazník udělá na stránce předchozího kroku, aby se dostal sem. `open` jen první krok.
VIA_ACTIONS = ("open", "click", "submit")
VIA_KEYS = {"do", "section", "text"}
VIA_TEXT_MAX = 60
# Krátké platné příklady do chybových zpráv: agent opraví tvar napoprvé, bez sondování (docs/plna-autonomie-agenta.md).
ENVIRONMENT_EXAMPLE = {"name": "local", "host": "127.0.0.1:5173"}
APPLICATION_EXAMPLE = {"kind": "application", "environments": [ENVIRONMENT_EXAMPLE]}
SECTION_EXAMPLE = {"id": "hero", "role": "hero", "name": "Úvod", "intent": "Proč tu zůstat."}
PAGE_EXAMPLE = {"kind": "page", "path": "/pribeh", "goal": "Návštěvník uvěří, že to zvládne.",
                "feel": "klidná, přírodní", "sections": [SECTION_EXAMPLE]}
STEP_EXAMPLES = [{"id": "vstup", "page": "nav"},
                 {"id": "pribeh", "page": "<id stránky nebo ref v dávce>", "via": {"do": "click", "text": "Příběh"}}]
JOURNEY_EXAMPLE = {"id": "zacit", "name": "Začít pěstovat", "steps": STEP_EXAMPLES}


def _shape(label, field, value, required, optional, expected, example):
    """Klíče objektu přesně podle tvaru, jinak 422 s tím, co chybí a co je navíc."""
    problem = keys_problem(value, required, optional)
    if problem:
        raise invalid(label, field, problem, expected, example)


def _text(value, minimum, maximum):
    """Krátký text bez řídicích znaků; prázdný ani jen z mezer se neukládá, pole se má vynechat."""
    return (isinstance(value, str) and minimum <= len(value) <= maximum
            and (minimum == 0 or bool(value.strip()))
            and not any(ord(char) < 32 or ord(char) == 127 for char in value))


def validate_page_fields(label, site):
    for key, (title, maximum) in PAGE_TEXT_LIMITS.items():
        if key in site and not _text(site[key], 1, maximum):
            raise invalid(label, f"site.{key}", f"{title} ({key}) má neplatnou hodnotu {site[key]!r}.",
                          f"text 1–{maximum} znaků bez řídicích znaků; prázdné pole vynechte", PAGE_EXAMPLE)
    if "sections" not in site:
        return
    sections = site["sections"]
    if not isinstance(sections, list) or not 1 <= len(sections) <= 20:
        raise invalid(label, "site.sections", "stránka má 1–20 sekcí; bez sekcí pole vynechte.",
                      "seznam 1–20 sekcí {id, role, name, intent, moves?}", [SECTION_EXAMPLE])
    seen = set()
    for index, section in enumerate(sections):
        field = f"site.sections[{index}]"
        _shape(label, field, section, SECTION_KEYS, SECTION_OPTIONAL_KEYS,
               "přesně {id, role, name, intent}, volitelně moves", SECTION_EXAMPLE)
        section_id = section["id"]
        if not isinstance(section_id, str) or not SECTION_ID.fullmatch(section_id):
            raise invalid(label, field + ".id", f"id sekce {section_id!r} nemá tvar id.",
                          "písmena, číslice, _ a -, nejvýše 80 znaků", SECTION_EXAMPLE)
        if section_id in seen:
            raise invalid(label, field + ".id", f"id sekce {section_id} se ve stránce opakuje.", "jedinečné id sekce")
        seen.add(section_id)
        if section["role"] not in SECTION_ROLES:
            raise invalid(label, field + ".role", f"role sekce {section['role']!r} není známá.",
                          "jedna z " + ", ".join(SECTION_ROLES), SECTION_EXAMPLE)
        if not _text(section["name"], 1, 60):
            raise invalid(label, field + ".name", "název sekce je prázdný nebo dlouhý.",
                          "text 1–60 znaků bez řídicích znaků", SECTION_EXAMPLE)
        if not _text(section["intent"], 0, 200):
            raise invalid(label, field + ".intent", "záměr sekce je dlouhý nebo není text.",
                          "text nejvýše 200 znaků bez řídicích znaků", SECTION_EXAMPLE)
        if "moves" in section and not _text(section["moves"], 1, SECTION_MOVES_MAX):
            raise invalid(label, field + ".moves", "čím sekce posouvá (moves) je prázdné nebo dlouhé.",
                          f"text 1–{SECTION_MOVES_MAX} znaků; prázdné pole vynechte")


def _validate_via(label, field, step_id, index, via):
    """`via` = `{do, section?, text?}`. Sekce se ověřuje jen tvarem: smazání sekce předchozí stránky nesmí zablokovat
    uložení mapy, chybějící sekci ohlásí kontrola mapy (`journey.via-unknown`)."""
    example = {"do": "click", "section": "cta", "text": "Chci začít"}
    _shape(label, field, via, {"do"}, VIA_KEYS - {"do"}, "{do, section?, text?}", example)
    if index == 0:
        if via != {"do": "open"}:
            raise invalid(label, field, f"první krok {step_id} smí mít jen via {{do: open}} (zákazník stránku otevře).",
                          '{"do": "open"} nebo via vynechte')
        return
    if via["do"] not in VIA_ACTIONS[1:]:
        raise invalid(label, field + ".do", f"krok {step_id} má via.do {via['do']!r}; open smí jen první krok.",
                      "click nebo submit", example)
    if "section" in via and (not isinstance(via["section"], str) or not SECTION_ID.fullmatch(via["section"])):
        raise invalid(label, field + ".section", f"via.section kroku {step_id} nemá tvar id sekce.",
                      "id sekce předchozí stránky (písmena, číslice, _ a -)", example)
    if "text" in via and not _text(via["text"], 1, VIA_TEXT_MAX):
        raise invalid(label, field + ".text", f"via.text kroku {step_id} je prázdný nebo dlouhý.",
                      f"text 1–{VIA_TEXT_MAX} znaků; prázdné pole vynechte", example)


def _page_hint(page, pages):
    """Nápověda, když `page` není id stránky: URL cesta známé stránky → její id."""
    if isinstance(page, str) and page.startswith("/"):
        known = (pages or {}).get(page.rstrip("/") or "/")
        return (f" {page!r} je URL cesta, page je id uzlu stránky"
                + (f" (stránka s path {page} má id {known})." if known else "; v dávce canvas-plan stačí ref stránky."))
    return ""


def _validate_steps(label, journey_field, journey_id, steps, pages=None):
    if not isinstance(steps, list) or not 2 <= len(steps) <= 30:
        raise invalid(label, journey_field + ".steps", f"cesta {journey_id} má 2–30 kroků.",
                      "seznam 2–30 kroků {id, page, label?, shift?, objection?, via?, after?}", STEP_EXAMPLES)
    seen = []
    for index, step in enumerate(steps):
        field = f"{journey_field}.steps[{index}]"
        _shape(label, field, step, STEP_KEYS, STEP_OPTIONAL_KEYS,
               "{id, page} a volitelně label, shift, objection, via, after", STEP_EXAMPLES[1])
        step_id, page = step["id"], step["page"]
        if not isinstance(step_id, str) or not SECTION_ID.fullmatch(step_id):
            raise invalid(label, field + ".id", f"id kroku cesty {journey_id} nemá tvar id.",
                          "písmena, číslice, _ a -, nejvýše 80 znaků", STEP_EXAMPLES[1])
        if step_id in seen:
            raise invalid(label, field + ".id", f"id kroku {step_id} se v cestě {journey_id} opakuje.", "jedinečné id kroku")
        if not isinstance(page, str) or not SECTION_ID.fullmatch(page) or (index > 0 and page == JOURNEY_FROM_NAV):
            raise invalid(label, field + ".page", f"krok {step_id} cesty {journey_id} má page {page!r}."
                          + _page_hint(page, pages),
                          "id stránky (uzel se site.kind page; v dávce canvas-plan ref stránky)"
                          + (" nebo nav (vstup z menu)" if index == 0 else "; nav smí jen první krok"), STEP_EXAMPLES)
        for key, (title, maximum) in STEP_TEXT_LIMITS.items():
            if key in step and not _text(step[key], 1, maximum):
                raise invalid(label, f"{field}.{key}", f"{title} ({key}) je prázdné nebo dlouhé.",
                              f"text 1–{maximum} znaků bez řídicích znaků; prázdné pole vynechte")
        if "via" in step:
            _validate_via(label, field + ".via", step_id, index, step["via"])
        if "after" in step and (index == 0 or step["after"] not in seen):
            raise invalid(label, field + ".after", f"krok {step_id} cesty {journey_id} navazuje na {step['after']!r}.",
                          "id dřívějšího kroku téže cesty; první krok after nemá")
        seen.append(step_id)


def validate_journeys(label, site, pages=None):
    """Tvar cest aplikace. Odkaz na stránku se tu neověřuje: smazání stránky nesmí zablokovat uložení mapy,
    krok s chybějící stránkou ohlásí kontrola mapy jako `journey.broken`. Stará podoba `{from, to}` se nepřijímá,
    stejně jako zrušená pole kroku `count` a `experience` (bez migrace). `pages` (path → id) jen zpřesní nápovědu."""
    if "journeys" not in site:
        return
    journeys = site["journeys"]
    if not isinstance(journeys, list) or not 1 <= len(journeys) <= 20:
        raise invalid(label, "site.journeys", "aplikace má 1–20 cest zákazníka; bez cest pole vynechte.",
                      "seznam 1–20 cest {id, name, steps}", [JOURNEY_EXAMPLE])
    seen = set()
    for index, journey in enumerate(journeys):
        field = f"site.journeys[{index}]"
        _shape(label, field, journey, JOURNEY_KEYS, JOURNEY_OPTIONAL_KEYS,
               "{id, name, steps} a volitelně purpose, actor, pointA, pointB", JOURNEY_EXAMPLE)
        journey_id = journey["id"]
        if not isinstance(journey_id, str) or not SECTION_ID.fullmatch(journey_id):
            raise invalid(label, field + ".id", f"id cesty {journey_id!r} nemá tvar id.",
                          "písmena, číslice, _ a -, nejvýše 80 znaků", JOURNEY_EXAMPLE)
        if journey_id in seen:
            raise invalid(label, field + ".id", f"id cesty {journey_id} se v aplikaci opakuje.", "jedinečné id cesty")
        seen.add(journey_id)
        if not _text(journey["name"], 1, 80):
            raise invalid(label, field + ".name", "název cesty je prázdný nebo dlouhý.", "text 1–80 znaků")
        for key, (title, maximum) in JOURNEY_TEXT_LIMITS.items():
            if key in journey and not _text(journey[key], 1, maximum):
                raise invalid(label, f"{field}.{key}", f"{title} ({key}) je prázdné nebo dlouhé.",
                              f"text 1–{maximum} znaků bez řídicích znaků; prázdné pole vynechte")
        _validate_steps(label, field, journey_id, journey["steps"], pages)




def nearest_page(by_id, node_id):
    """Nejbližší stránka (`site.kind == "page"`) mezi předky uzlu po řetězu `parentId`, nebo None.
    Uzel sám se nepočítá; cyklus ani chybějící rodič řetěz ukončí."""
    seen, current = {node_id}, by_id[node_id].get("parentId")
    while current is not None and current in by_id and current not in seen:
        seen.add(current)
        site = by_id[current].get("site")
        if isinstance(site, dict) and site.get("kind") == "page":
            return by_id[current]
        current = by_id[current].get("parentId")
    return None


def card_section_error(by_id, node_id):
    """Důvod, proč `card.section` uzlu nemíří na sekci nejbližší stránky (§3.3), nebo None.

    Uzel bez `card.section` je vždy v pořádku. Uložení grafu tohle neověřuje (smazání sekce nesmí zablokovat
    mapu); odmítá podle toho dávka plánu agenta a kontrola mapy to hlásí jako `section.unknown`."""
    card = by_id[node_id].get("card")
    section = card.get("section") if isinstance(card, dict) else None
    if section is None:
        return None
    page = nearest_page(by_id, node_id)
    if page is None:
        return f"karta leží mimo stránku, sekci {section} nemá kde realizovat."
    sections = page["site"].get("sections")
    known = [item.get("id") for item in sections if isinstance(item, dict)] if isinstance(sections, list) else []
    if section not in known:
        name = page.get("name") or page["id"]
        return (f"stránka {name} nemá sekci {section}; sekce musí být id ze site.sections nejbližší stránky"
                + (f" ({', '.join(str(item) for item in known)})." if known else " (stránka zatím sekce nemá)."))
    return None


def host_key(value):
    """Canonical comparison of hostname[:port], accepting localhost and bracketed IPv6."""
    if (not isinstance(value, str) or not value or len(value) > 300
            or any(ord(char) <= 32 or char in "/\\?#@" for char in value)):
        raise ValueError("Host musí být název domény nebo localhost s volitelným portem, bez URL cesty.")
    try:
        parsed = urlsplit("//" + value)
        host, port = parsed.hostname, parsed.port
        if not host or parsed.path or (port is not None and not 1 <= port <= 65535):
            raise ValueError
        if value.endswith(":"):
            raise ValueError
        if ":" in host:
            hostname = str(ipaddress.IPv6Address(host))
        else:
            hostname = host.rstrip(".").encode("idna").decode("ascii").lower()
            if len(hostname) > 253 or not all(DNS_LABEL.fullmatch(label) for label in hostname.split(".")):
                raise ValueError
        return hostname, port
    except (ValueError, UnicodeError) as error:
        raise ValueError("Neplatný host; použijte doménu nebo localhost:port bez protokolu.") from error


def route_key(value):
    if not isinstance(value, str) or not value.startswith("/") or len(value) > 2048:
        raise ValueError("Cesta stránky musí začínat / a mít nejvýše 2048 znaků.")
    try:
        decoded = unquote(value, errors="strict")
    except UnicodeError as error:
        raise ValueError("Neplatné kódování cesty stránky.") from error
    if ("//" in decoded or any(ord(char) <= 32 or char in "\\?#" for char in decoded)
            or any(part in (".", "..") for part in decoded.split("/"))):
        raise ValueError("Cesta stránky nesmí obsahovat mezery, dotaz, fragment ani . nebo .. segmenty.")
    return decoded.rstrip("/") or "/"


def _checked(check, value, label, field, expected, example):
    """`host_key` / `route_key` s chybou, která nese uzel a pole (422)."""
    try:
        return check(value)
    except ValueError as error:
        raise invalid(label, field, f"{value!r}: {error}", expected, example) from error


def validate_sites(nodes):
    """Validate metadata and uniqueness after the graph has validated its parent tree."""
    by_id = {node["id"]: node for node in nodes}
    hosts, pages = {}, {}
    # Jen pro nápovědu u kroku cesty, který místo id stránky nese její URL cestu.
    page_ids = {node["site"]["path"].rstrip("/") or "/": node["id"] for node in nodes
                if isinstance(node.get("site"), dict) and node["site"].get("kind") == "page"
                and isinstance(node["site"].get("path"), str)}
    for node in nodes:
        if "site" not in node:
            continue
        site = node["site"]
        label = node["name"] or node["id"]
        if not isinstance(site, dict):
            raise invalid(label, "site", "site není objekt.", "objekt aplikace (sektor) nebo stránky (uzel)",
                          APPLICATION_EXAMPLE)
        if site.get("kind") == "application":
            if node["kind"] != "sector":
                raise invalid(label, "kind", f"aplikace (site.kind application) leží na uzlu druhu {node['kind']}.",
                              "uzel kind sector", APPLICATION_EXAMPLE)
            _shape(label, "site", site, {"kind", "environments"}, APPLICATION_KEYS - {"kind", "environments"},
                   "aplikace {kind: application, environments: [{name, host}]} a volitelně healthPath, journeys",
                   APPLICATION_EXAMPLE)
            validate_journeys(label, site, page_ids)
            if "healthPath" in site:
                # Cesta, na které web hlásí zdraví (např. /api/v1/health); stejná pravidla jako cesta stránky.
                _checked(route_key, site["healthPath"], label, "site.healthPath",
                         "cesta začínající / bez dotazu a fragmentu", {**APPLICATION_EXAMPLE, "healthPath": "/api/health"})
            environments = site["environments"]
            if not isinstance(environments, list) or len(environments) > 20:
                raise invalid(label, "site.environments", "prostředí nejsou seznam nebo jich je víc než 20.",
                              "seznam nejvýše 20 prostředí {name, host}", [ENVIRONMENT_EXAMPLE])
            names = set()
            for index, environment in enumerate(environments):
                field = f"site.environments[{index}]"
                _shape(label, field, environment, {"name", "host"}, (), "{name, host}", ENVIRONMENT_EXAMPLE)
                name = environment["name"]
                if not isinstance(name, str) or not name.strip() or len(name) > 80 or "\0" in name:
                    raise invalid(label, field + ".name", "název prostředí je prázdný nebo dlouhý.",
                                  "text 1–80 znaků", ENVIRONMENT_EXAMPLE)
                key = name.strip().casefold()
                if key in names:
                    raise ValueError(f"{label}: název prostředí {name} se opakuje.")
                names.add(key)
                host = _checked(host_key, environment["host"], label, field + ".host",
                                "doména nebo localhost:port bez protokolu a cesty", ENVIRONMENT_EXAMPLE)
                if host in hosts:
                    raise ValueError(f"{label}: host {environment['host']} už patří prostředí {hosts[host]}.")
                hosts[host] = f"{label} / {name}"
        elif site.get("kind") == "page":
            if node["kind"] != "node":
                raise invalid(label, "kind", f"stránka (site.kind page) leží na uzlu druhu {node['kind']}.",
                              "uzel kind node pod sektorem aplikace", PAGE_EXAMPLE)
            _shape(label, "site", site, {"kind", "path"}, PAGE_KEYS - {"kind", "path"},
                   "stránka {kind: page, path} a volitelně goal, feel, navLabel, sections", PAGE_EXAMPLE)
            route = _checked(route_key, site["path"], label, "site.path",
                             "cesta začínající / bez dotazu a fragmentu", PAGE_EXAMPLE)
            validate_page_fields(label, site)
            parent = by_id.get(node["parentId"])
            while parent is not None and not (
                isinstance(parent.get("site"), dict) and parent["site"].get("kind") == "application"
            ):
                parent = by_id.get(parent["parentId"])
            if parent is None:
                raise invalid(label, "parentId", "stránka musí patřit pod aplikaci; žádný předek nemá site.kind application.",
                              "předek se site.kind application (v dávce canvas-plan parent = ref sektoru aplikace)")
            key = (parent["id"], route)
            if key in pages:
                raise ValueError(f"{label}: cesta {site['path']} už v aplikaci patří stránce {pages[key]}.")
            pages[key] = label
        else:
            raise invalid(label, "site.kind", f"site.kind {site.get('kind')!r} není známý.",
                          "application (sektor aplikace) nebo page (stránka)", APPLICATION_EXAMPLE)
