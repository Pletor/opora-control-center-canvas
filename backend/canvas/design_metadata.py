"""References to design artifacts. Never fetch remote content on the server.

`previewUrl` se v UI vykreslí jako obrázek, tedy prohlížeč ho sám stáhne. Proto smí být jen
https na veřejný host (ne localhost, ne privátní ani loopback IP) a UI ho načte až po kliknutí
(upgrade-opora #42): agent jím jinak vloží beacon nebo GET do vnitřní sítě.
"""

import ipaddress
from urllib.parse import urlsplit


def _public_https(value):
    url = urlsplit(value)
    host = (url.hostname or "").lower()
    if url.scheme != "https" or not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." in host
    return address.is_global


def validate_design(design):
    if not isinstance(design, dict) or not {"artifactUrl", "version"} <= set(design) or set(design) - {"artifactUrl", "version", "previewUrl"}:
        raise ValueError("Návrh musí obsahovat artifactUrl, version a případně previewUrl.")
    version = design["version"]
    if not isinstance(version, str) or not version.strip() or len(version) > 200 or any(ord(c) < 32 for c in version):
        raise ValueError("Verze návrhu musí být neprázdný text do 200 znaků.")
    for key in ("artifactUrl", "previewUrl"):
        if key not in design:
            continue
        value = design[key]
        try:
            if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 or c == "\\" for c in value):
                raise ValueError()
            url = urlsplit(value)
            if url.scheme not in ("https", "http") or not url.hostname or url.username is not None or url.password is not None:
                raise ValueError()
            _ = url.port
        except (ValueError, TypeError):
            raise ValueError(f"{key} musí být úplný HTTP(S) odkaz bez přihlašovacích údajů.") from None
        if key == "previewUrl" and not _public_https(value):
            raise ValueError("previewUrl musí být https odkaz na veřejný host (ne localhost ani privátní IP).")
