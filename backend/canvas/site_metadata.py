"""Application hosts and page routes annotate the existing graph, never a second tree.

Hosts describe environments only; validation neither resolves DNS nor deploys anything.
Pages share their application's structure across environments and retain ordinary IDs.
"""

import ipaddress
import re
from urllib.parse import unquote, urlsplit

DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)


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
            if node["kind"] != "sector" or set(site) != {"kind", "environments"}:
                raise ValueError(f"{label}: aplikace je sektor se site.kind a environments.")
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
            if node["kind"] != "node" or set(site) != {"kind", "path"}:
                raise ValueError(f"{label}: stránka je uzel se site.kind a path.")
            route = route_key(site["path"])
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
