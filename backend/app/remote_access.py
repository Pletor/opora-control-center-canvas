"""Vzdálený přístup přes tunel: kdo smí mluvit s API, když Host není loopback.

Aplikace zůstává na tomto počítači (SQLite, data na disku, Hook control, lokální modely).
Ven ji pouští jen tunel — Cloudflare quick tunnel míří na `http://127.0.0.1:8740` a dává
náhodnou adresu `https://<jméno>.trycloudflare.com`. Tenhle modul je jediné místo, které
rozhoduje, jestli je takový požadavek povolený, a drží i malý router `/api/access/*`,
protože přihlášení je součást hranice, ne prostředí aplikace.

Režim je aktivní jen když jsou nastavené **obě** proměnné prostředí
`OPORA_PUBLIC_HOSTS` a `OPORA_ACCESS_TOKEN`; jinak se aplikace chová přesně jako dosud.
"""

from __future__ import annotations

import hmac
import os

COOKIE_NAME = "opora_access"
MIN_TOKEN_LENGTH = 24
TOKEN_REQUIRED = "Přístup vyžaduje token."
# Hooky běží na tomto počítači: událost i ACK mluví do živého agenta tady a rozhodují,
# jestli smí sáhnout na soubory. Z veřejného hosta je nepustíme ani s platným tokenem —
# token otevírá aplikaci, ne řízení procesů na tomto stroji.
LOOPBACK_ONLY_PATHS = frozenset({"/api/agent-hooks/event", "/api/agent-hooks/ack"})
# Asistent spouští Claude Code na tomto počítači; kdo má URL tunelu, nesmí ho ovládat.
ASSISTANT_PREFIX = "/api/assistant"
# Bez těchhle tří by se přihlašovací obrazovka neměla jak zeptat ani přihlásit.
OPEN_PATHS = frozenset({"/api/access/status", "/api/access/login", "/api/access/logout"})


def parse_hosts(value):
    """`"a.example, *.trycloudflare.com"` → `("a.example", "*.trycloudflare.com")`."""
    if not isinstance(value, str):
        return ()
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


def hostname_of(host_header):
    """Z hlavičky Host udělá čisté jméno: bez portu, malými písmeny, bez hranatých závorek."""
    host = (host_header or "").strip().lower()
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else host
    return host.split(":")[0]


def host_matches(patterns, host_header):
    """Shoda na přesné jméno, nebo na příponu u vzoru `*.doména`; prázdné jméno nikdy."""
    host = hostname_of(host_header)
    if not host:
        return False
    for pattern in patterns:
        if pattern.startswith("*."):
            suffix = pattern[1:]
            if host.endswith(suffix) and len(host) > len(suffix):
                return True
        elif host == pattern:
            return True
    return False


def token_is_strong(token):
    return isinstance(token, str) and len(token) >= MIN_TOKEN_LENGTH


def tokens_equal(expected, given):
    """Porovnání v konstantním čase; cokoli jiného než dva neprázdné řetězce je nesouhlas."""
    if not isinstance(expected, str) or not isinstance(given, str) or not expected or not given:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), given.encode("utf-8"))


def bearer_token(authorization):
    if not isinstance(authorization, str) or len(authorization) > 4096:
        return None
    if not authorization.startswith("Bearer "):
        return None
    return authorization[7:].strip() or None


def is_loopback_only(path):
    return path in LOOPBACK_ONLY_PATHS or path == ASSISTANT_PREFIX or path.startswith(ASSISTANT_PREFIX + "/")


def requires_token(path):
    """Token chce každé `/api/*` kromě přihlašovacích rout; statika se servíruje volně."""
    return path.startswith("/api") and path not in OPEN_PATHS


def scheme_from(forwarded_proto):
    """Tunel končí u Cloudflare, k nám jde plain HTTP; skutečné schéma říká X-Forwarded-Proto."""
    value = (forwarded_proto or "").split(",")[0].strip().lower()
    return value if value in ("http", "https") else "https"


class RemoteAccess:
    """Hranice pro veřejné hosty. Neaktivní instance se chová, jako by nic nepřibylo."""

    def __init__(self, hosts=(), token=""):
        self.hosts = tuple(hosts)
        self.token = token if isinstance(token, str) else ""
        self.active = bool(self.hosts) and token_is_strong(self.token)

    @classmethod
    def from_env(cls, env=None):
        environ = os.environ if env is None else env
        return cls(parse_hosts(environ.get("OPORA_PUBLIC_HOSTS", "")), environ.get("OPORA_ACCESS_TOKEN", ""))

    def is_public_host(self, host_header):
        return self.active and host_matches(self.hosts, host_header)

    def origin_for(self, host_header, forwarded_proto=None):
        return scheme_from(forwarded_proto) + "://" + (host_header or "")

    def authorized(self, authorization=None, cookie=None):
        if not self.active:
            return False
        presented = bearer_token(authorization)
        if presented is not None and tokens_equal(self.token, presented):
            return True
        return tokens_equal(self.token, cookie)


def set_access_cookie(response, token):
    """Cookie drží prohlížeč: HttpOnly (JS na ni nesáhne), Secure (jen tunel), SameSite=Strict."""
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=True, samesite="strict", path="/", max_age=60 * 60 * 24 * 30
    )
