"""Application hosts and page routes annotate the existing graph, never a second tree.

Hosts describe environments only; validation neither resolves DNS nor deploys anything.
Pages share their application's structure across environments and retain ordinary IDs.
"""

import ipaddress
import re
from urllib.parse import unquote, urlsplit

DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)
# Stejný tvar jako `graph.valid_id`; graph importuje tento modul, proto vlastní kopie bez cyklu.
SECTION_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
# Stránka nese záměr člověka (goal, feel, navLabel) a sekce, které navrhuje agent. Vše nepovinné, bez výchozích hodnot.
PAGE_KEYS = {"kind", "path", "goal", "feel", "navLabel", "sections"}
PAGE_TEXT_LIMITS = {"goal": ("cíl stránky", 200), "feel": ("působení stránky", 120), "navLabel": ("popisek v menu", 40)}
SECTION_KEYS = {"id", "role", "name", "intent"}
SECTION_ROLES = ("hero", "cta", "form", "content", "gallery", "proof", "faq", "footer", "custom")
# Aplikace nese cesty zákazníka jako trychtýř stránek, který zadává člověk: kroky jsou stránky s rolí, zážitkem
# a počtem lidí; vazby mezi nimi (kudy zákazník jde po mapě) se neukládají, odvodí je stroj (§6).
APPLICATION_KEYS = {"kind", "environments", "healthPath", "journeys"}
JOURNEY_KEYS = {"id", "name", "steps"}
JOURNEY_OPTIONAL_KEYS = {"purpose"}
STEP_KEYS = {"id", "page"}
STEP_OPTIONAL_KEYS = {"label", "experience", "count", "after"}
STEP_TEXT_LIMITS = {"label": ("role kroku", 60), "experience": ("zážitek kroku", 400)}
JOURNEY_FROM_NAV = "nav"


def _text(value, minimum, maximum):
    """Krátký text bez řídicích znaků; prázdný ani jen z mezer se neukládá, pole se má vynechat."""
    return (isinstance(value, str) and minimum <= len(value) <= maximum
            and (minimum == 0 or bool(value.strip()))
            and not any(ord(char) < 32 or ord(char) == 127 for char in value))


def validate_page_fields(label, site):
    for key, (title, maximum) in PAGE_TEXT_LIMITS.items():
        if key in site and not _text(site[key], 1, maximum):
            raise ValueError(f"{label}: {title} ({key}) musí mít 1–{maximum} znaků bez řídicích znaků; prázdné pole vynechte.")
    if "sections" not in site:
        return
    sections = site["sections"]
    if not isinstance(sections, list) or not 1 <= len(sections) <= 20:
        raise ValueError(f"{label}: stránka má 1–20 sekcí; bez sekcí pole vynechte.")
    seen = set()
    for section in sections:
        if not isinstance(section, dict) or set(section) != SECTION_KEYS:
            raise ValueError(f"{label}: sekce vyžaduje přesně id, role, name a intent.")
        section_id = section["id"]
        if not isinstance(section_id, str) or not SECTION_ID.fullmatch(section_id):
            raise ValueError(f"{label}: id sekce musí mít tvar id uzlu (písmena, číslice, _ a -, nejvýše 80 znaků).")
        if section_id in seen:
            raise ValueError(f"{label}: id sekce {section_id} se ve stránce opakuje.")
        seen.add(section_id)
        if section["role"] not in SECTION_ROLES:
            raise ValueError(f"{label}: role sekce musí být jedna z {', '.join(SECTION_ROLES)}.")
        if not _text(section["name"], 1, 60):
            raise ValueError(f"{label}: název sekce musí mít 1–60 znaků bez řídicích znaků.")
        if not _text(section["intent"], 0, 200):
            raise ValueError(f"{label}: záměr sekce musí mít nejvýše 200 znaků bez řídicích znaků.")


def _validate_steps(label, journey_id, steps):
    if not isinstance(steps, list) or not 2 <= len(steps) <= 30:
        raise ValueError(f"{label}: cesta {journey_id} má 2–30 kroků.")
    seen = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not STEP_KEYS <= set(step) <= STEP_KEYS | STEP_OPTIONAL_KEYS:
            raise ValueError(f"{label}: krok cesty {journey_id} vyžaduje id a page, volitelně label, experience, count a after.")
        step_id, page = step["id"], step["page"]
        if not isinstance(step_id, str) or not SECTION_ID.fullmatch(step_id):
            raise ValueError(f"{label}: id kroku cesty {journey_id} musí mít tvar id uzlu.")
        if step_id in seen:
            raise ValueError(f"{label}: id kroku {step_id} se v cestě {journey_id} opakuje.")
        if not isinstance(page, str) or not SECTION_ID.fullmatch(page) or (index > 0 and page == JOURNEY_FROM_NAV):
            raise ValueError(f"{label}: krok {step_id} cesty {journey_id} potřebuje page jako id stránky"
                             + (" nebo nav (vstup z menu)." if index == 0 else "; menu (nav) smí být jen první krok."))
        for key, (title, maximum) in STEP_TEXT_LIMITS.items():
            if key in step and not _text(step[key], 1, maximum):
                raise ValueError(f"{label}: {title} ({key}) musí mít 1–{maximum} znaků bez řídicích znaků; prázdné pole vynechte.")
        count = step.get("count", 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{label}: počet lidí v kroku {step_id} (count) musí být celé číslo ≥ 0.")
        if "after" in step and (index == 0 or step["after"] not in seen):
            raise ValueError(f"{label}: krok {step_id} cesty {journey_id} smí navazovat (after) jen na dřívější krok;"
                             " první krok after nemá.")
        seen.append(step_id)


def validate_journeys(label, site):
    """Tvar cest aplikace. Odkaz na stránku se tu neověřuje: smazání stránky nesmí zablokovat uložení mapy,
    krok s chybějící stránkou ohlásí kontrola mapy jako `journey.broken`. Stará podoba `{from, to}` se nepřijímá."""
    if "journeys" not in site:
        return
    journeys = site["journeys"]
    if not isinstance(journeys, list) or not 1 <= len(journeys) <= 20:
        raise ValueError(f"{label}: aplikace má 1–20 cest zákazníka; bez cest pole vynechte.")
    seen = set()
    for journey in journeys:
        if not isinstance(journey, dict) or not JOURNEY_KEYS <= set(journey) <= JOURNEY_KEYS | JOURNEY_OPTIONAL_KEYS:
            raise ValueError(f"{label}: cesta vyžaduje id, name a steps, volitelně purpose.")
        journey_id = journey["id"]
        if not isinstance(journey_id, str) or not SECTION_ID.fullmatch(journey_id):
            raise ValueError(f"{label}: id cesty musí mít tvar id uzlu (písmena, číslice, _ a -, nejvýše 80 znaků).")
        if journey_id in seen:
            raise ValueError(f"{label}: id cesty {journey_id} se v aplikaci opakuje.")
        seen.add(journey_id)
        if not _text(journey["name"], 1, 80):
            raise ValueError(f"{label}: název cesty musí mít 1–80 znaků bez řídicích znaků.")
        if "purpose" in journey and not _text(journey["purpose"], 1, 200):
            raise ValueError(f"{label}: účel cesty (purpose) musí mít 1–200 znaků bez řídicích znaků; prázdné pole vynechte.")
        _validate_steps(label, journey_id, journey["steps"])


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


def validate_sites(nodes):
    """Validate metadata and uniqueness after the graph has validated its parent tree."""
    by_id = {node["id"]: node for node in nodes}
    hosts, pages = {}, {}
    for node in nodes:
        if "site" not in node:
            continue
        site = node["site"]
        label = node["name"] or node["id"]
        if not isinstance(site, dict):
            raise ValueError(f"{label}: site musí být objekt aplikace nebo stránky.")
        if site.get("kind") == "application":
            if node["kind"] != "sector" or not {"kind", "environments"} <= set(site) <= APPLICATION_KEYS:
                raise ValueError(f"{label}: aplikace je sektor se site.kind, environments a volitelným healthPath a journeys.")
            validate_journeys(label, site)
            if "healthPath" in site:
                # Cesta, na které web hlásí zdraví (např. /api/v1/health); stejná pravidla jako cesta stránky.
                route_key(site["healthPath"])
            environments = site["environments"]
            if not isinstance(environments, list) or len(environments) > 20:
                raise ValueError(f"{label}: aplikace má nejvýše 20 prostředí.")
            names = set()
            for environment in environments:
                if not isinstance(environment, dict) or set(environment) != {"name", "host"}:
                    raise ValueError(f"{label}: prostředí vyžaduje name a host.")
                name = environment["name"]
                if not isinstance(name, str) or not name.strip() or len(name) > 80 or "\0" in name:
                    raise ValueError(f"{label}: prostředí musí mít název do 80 znaků.")
                key = name.strip().casefold()
                if key in names:
                    raise ValueError(f"{label}: název prostředí {name} se opakuje.")
                names.add(key)
                host = host_key(environment["host"])
                if host in hosts:
                    raise ValueError(f"{label}: host {environment['host']} už patří prostředí {hosts[host]}.")
                hosts[host] = f"{label} / {name}"
        elif site.get("kind") == "page":
            if node["kind"] != "node" or not {"kind", "path"} <= set(site) <= PAGE_KEYS:
                raise ValueError(f"{label}: stránka je uzel se site.kind, path a volitelným goal, feel, navLabel, sections.")
            route = route_key(site["path"])
            validate_page_fields(label, site)
            parent = by_id.get(node["parentId"])
            while parent is not None and not (
                isinstance(parent.get("site"), dict) and parent["site"].get("kind") == "application"
            ):
                parent = by_id.get(parent["parentId"])
            if parent is None:
                raise ValueError(f"{label}: stránka musí patřit pod aplikaci.")
            key = (parent["id"], route)
            if key in pages:
                raise ValueError(f"{label}: cesta {site['path']} už v aplikaci patří stránce {pages[key]}.")
            pages[key] = label
        else:
            raise ValueError(f"{label}: site.kind musí být application nebo page.")
