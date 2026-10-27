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
            if node["kind"] != "sector" or set(site) not in ({"kind", "environments"}, {"kind", "environments", "healthPath"}):
                raise ValueError(f"{label}: aplikace je sektor se site.kind, environments a volitelným healthPath.")
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
